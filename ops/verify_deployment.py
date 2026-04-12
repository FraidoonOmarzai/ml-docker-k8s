#!/usr/bin/env python3
"""
ops/verify_deployment.py
Runs a full health check against a live Kubernetes deployment.

Usage:
    # Via port-forward (run this first in another terminal):
    #   kubectl port-forward svc/dock8s-api-service 8080:80 -n dock8s-namespace
    python ops/verify_deployment.py

    # Against any URL:
    python ops/verify_deployment.py --url http://dock8s-api.local
    python ops/verify_deployment.py --url http://<minikube-ip>:30080
"""

import json
import sys
import time
import argparse
import subprocess
import urllib.request
import urllib.error
from datetime import datetime

DEFAULT_URL = "http://localhost:8080"
NAMESPACE = "dock8s-namespace"
DEPLOYMENT = "dock8s-api"

# ── Colours ───────────────────────────────────────────────────────────────────
C = {
    "green": "\033[92m",
    "red": "\033[91m",
    "yellow": "\033[93m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}


def c(text, col):
    return f"{C[col]}{text}{C['reset']}"


def section(t):
    print(f"\n{c('─'*58, 'cyan')}")
    print(c(f"  {t}", "bold"))
    print(c("─" * 58, "cyan"))


passed = failed = warnings = 0


def check(name, ok, detail="", warn_only=False):
    global passed, failed, warnings
    if ok:
        print(f"  {c('✅', 'green')} {name}")
        passed += 1
    elif warn_only:
        print(f"  {c('⚠️ ', 'yellow')} {name}")
        if detail:
            print(f"       {c(detail, 'yellow')}")
        warnings += 1
    else:
        print(f"  {c('❌', 'red')} {name}")
        if detail:
            print(f"       {c(detail, 'red')}")
        failed += 1


def http_get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def http_post(url, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def kubectl(cmd):
    try:
        result = subprocess.run(
            f"kubectl {cmd}", shell=True, capture_output=True, text=True, timeout=15
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)


# ── Check groups ──────────────────────────────────────────────────────────────


def check_kubectl(namespace, deployment):
    section("1. Kubernetes Cluster State")

    ok, out, _ = kubectl(f"get namespace {namespace}")
    check(f"Namespace '{namespace}' exists", ok)

    ok, out, _ = kubectl(f"get deployment {deployment} -n {namespace}")
    check(f"Deployment '{deployment}' exists", ok)

    ok, out, _ = kubectl(
        f"get deployment {deployment} -n {namespace} "
        f"-o jsonpath='{{.status.readyReplicas}}'"
    )
    ready = int(out.strip("'")) if ok and out.strip("'").isdigit() else 0
    check(f"Ready replicas ≥ 1 (got {ready})", ready >= 1, "No ready replicas found")

    ok, out, _ = kubectl(
        f"get deployment {deployment} -n {namespace} "
        f"-o jsonpath='{{.status.unavailableReplicas}}'"
    )
    unavail = int(out.strip("'")) if ok and out.strip("'").isdigit() else 0
    check(
        f"No unavailable replicas (got {unavail})",
        unavail == 0,
        f"{unavail} unavailable replicas",
        warn_only=(unavail > 0),
    )

    ok, out, _ = kubectl(f"get hpa -n {namespace}")
    check("HPA exists", ok and "dock8s-api" in out, warn_only=True)

    ok, out, _ = kubectl(f"get svc dock8s-api -n {namespace}")
    check("ClusterIP service exists", ok)


def check_api_health(base_url):
    section("2. API Health Endpoints")

    status, body = http_get(f"{base_url}/health")
    check(f"GET /health → 200", status == 200, f"Got {status}")
    if status == 200:
        check("model_loaded = True", body.get("model_loaded") is True)
        check("status = 'healthy'", body.get("status") == "healthy")
        check("num_features = 4", body.get("num_features") == 4)
        print(f"\n       {c('Model info:', 'cyan')}")
        print(f"         type     : {body.get('model_type')}")
        print(f"         classes  : {body.get('class_names')}")
        print(f"         accuracy : {body.get('test_accuracy')}")

    status, body = http_get(f"{base_url}/ready")
    check(f"GET /ready → 200", status == 200, f"Got {status}")


def check_inference(base_url):
    section("3. Inference Quality")

    cases = [
        ([5.1, 3.5, 1.4, 0.2], "setosa"),
        ([6.7, 3.0, 5.2, 2.3], "virginica"),
        ([5.8, 2.7, 4.1, 1.0], "versicolor"),
    ]
    for features, expected in cases:
        status, body = http_post(f"{base_url}/predict", {"features": features})
        got = body.get("predicted_class", "N/A")
        check(
            f"Predict {expected:12s} | features={features}",
            status == 200 and got == expected,
            f"Got '{got}' (status {status})",
        )

    # Batch
    status, body = http_post(
        f"{base_url}/predict/batch", {"features": [c[0] for c in cases]}
    )
    check("Batch predict → 3 results", status == 200 and body.get("total") == 3)


def check_latency(base_url):
    section("4. Latency Benchmarks")

    latencies = []
    for _ in range(10):
        t0 = time.perf_counter()
        http_post(f"{base_url}/predict", {"features": [5.1, 3.5, 1.4, 0.2]})
        latencies.append((time.perf_counter() - t0) * 1000)

    avg = sum(latencies) / len(latencies)
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    mn = min(latencies)
    mx = max(latencies)

    print(f"\n       10 sequential /predict calls:")
    print(f"         min  : {mn:.1f} ms")
    print(f"         avg  : {avg:.1f} ms")
    print(f"         p95  : {p95:.1f} ms")
    print(f"         max  : {mx:.1f} ms")

    check("Avg latency < 200ms", avg < 200, f"avg={avg:.1f}ms", warn_only=True)
    check("p95 latency < 500ms", p95 < 500, f"p95={p95:.1f}ms", warn_only=True)


def check_validation(base_url):
    section("5. Input Validation")

    bad_inputs = [
        ({"features": [5.1, 3.5]}, "Too few features → 422"),
        ({"features": [5.1, 3.5, 1.4, 0.2, 9]}, "Too many features → 422"),
        ({"features": [-1.0, 3.5, 1.4, 0.2]}, "Negative value → 422"),
        ({}, "Missing features → 422"),
    ]
    for body, name in bad_inputs:
        status, _ = http_post(f"{base_url}/predict", body)
        check(name, status == 422, f"Got {status}")


def check_rollout_history(deployment, namespace):
    section("6. Rollout History")
    ok, out, _ = kubectl(f"rollout history deployment/{deployment} -n {namespace}")
    if ok and out:
        print(f"\n{c(out, 'cyan')}")
        check("Rollout history available", True)
    else:
        check("Rollout history available", False, warn_only=True)


def print_summary():
    section("Summary")
    total = passed + failed + warnings
    print(f"\n  Total    : {total}")
    print(f"  {c(f'Passed   : {passed}', 'green')}")
    print(f"  {c(f'Warnings : {warnings}', 'yellow')}")
    color = "red" if failed else "green"
    print(f"  {c(f'Failed   : {failed}', color)}")
    print()
    if failed == 0:
        print(c("  🎉 Deployment is healthy and serving traffic!", "green"))
    else:
        print(c(f"  ⚠️  {failed} check(s) failed — review above.", "red"))
    print(f"\n  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument(
        "--skip-kubectl",
        action="store_true",
        help="Skip kubectl checks (useful if no cluster access)",
    )
    args = parser.parse_args()
    base_url = args.url.rstrip("/")

    print(c("\n🚀 Docker + k8s Inference API — Live Deployment Verification", "bold"))
    print(c(f"   Target: {base_url}", "cyan"))
    print(c(f"   Time  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "cyan"))

    if not args.skip_kubectl:
        check_kubectl(NAMESPACE, DEPLOYMENT)
        check_rollout_history(DEPLOYMENT, NAMESPACE)

    check_api_health(base_url)
    check_inference(base_url)
    check_latency(base_url)
    check_validation(base_url)

    print_summary()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
