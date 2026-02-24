#!/usr/bin/env python3
"""
test_local.py - Test the running Docker container end-to-end
Run AFTER the container is up: docker run -p 8080:8080 iris-ml-api

Usage:
    python test_local.py
    python test_local.py --base-url http://localhost:8080
"""

import json
import sys
import time
import argparse
import urllib.request
import urllib.error
from typing import Dict, Any

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_URL = "http://localhost:8080"

COLORS = {
    "green":  "\033[92m",
    "red":    "\033[91m",
    "yellow": "\033[93m",
    "cyan":   "\033[96m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
}

def c(text, color):
    return f"{COLORS[color]}{text}{COLORS['reset']}"

def section(title):
    print(f"\n{c('─' * 55, 'cyan')}")
    print(c(f"  {title}", "bold"))
    print(c('─' * 55, 'cyan'))

# ── HTTP helpers ──────────────────────────────────────────────────────────────
def get(url: str) -> tuple[int, Dict]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def post(url: str, body: Dict) -> tuple[int, Dict]:
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

# ── Test runner ───────────────────────────────────────────────────────────────
passed = 0
failed = 0

def run_test(name: str, status: int, body: Dict, expected_status: int, checks: Dict[str, Any] = None):
    global passed, failed
    ok = True

    status_ok = status == expected_status
    if not status_ok:
        ok = False

    check_results = {}
    if checks and status_ok:
        for key_path, expected in checks.items():
            keys = key_path.split(".")
            val  = body
            try:
                for k in keys:
                    val = val[k]
                check_results[key_path] = (val == expected, val, expected)
                if val != expected:
                    ok = False
            except (KeyError, TypeError):
                check_results[key_path] = (False, "MISSING", expected)
                ok = False

    icon = c("✅ PASS", "green") if ok else c("❌ FAIL", "red")
    print(f"\n  {icon}  {name}")
    print(f"         Status: {status} (expected {expected_status})")

    for key_path, (chk_ok, got, exp) in check_results.items():
        chk_icon = c("✓", "green") if chk_ok else c("✗", "red")
        print(f"         {chk_icon}  {key_path}: got={got!r}  expected={exp!r}")

    if ok:
        passed += 1
    else:
        failed += 1
        print(f"         {c('Response:', 'yellow')} {json.dumps(body, indent=2)[:300]}")

    return ok, body


# ── Tests ─────────────────────────────────────────────────────────────────────
def wait_for_server(base_url: str, retries: int = 10):
    print(c(f"\nWaiting for server at {base_url}...", "yellow"))
    for i in range(retries):
        try:
            status, _ = get(f"{base_url}/health")
            if status == 200:
                print(c("Server is up! ✅\n", "green"))
                return True
        except Exception:
            pass
        print(f"  Retry {i+1}/{retries}...")
        time.sleep(2)
    print(c("❌ Server did not respond in time.", "red"))
    return False


def test_root(base_url):
    section("1. Root Endpoint")
    status, body = get(f"{base_url}/")
    run_test("GET /", status, body, 200)


def test_health(base_url):
    section("2. Health Endpoint")
    status, body = get(f"{base_url}/health")
    run_test(
        "GET /health",
        status, body, 200,
        checks={
            "status":       "healthy",
            "model_loaded": True,
            "num_features": 4,
        }
    )
    if status == 200:
        print(f"\n         {c('Model info:', 'cyan')}")
        print(f"           type      : {body.get('model_type')}")
        print(f"           classes   : {body.get('class_names')}")
        print(f"           accuracy  : {body.get('test_accuracy')}")


def test_ready(base_url):
    section("3. Readiness Endpoint")
    status, body = get(f"{base_url}/ready")
    run_test("GET /ready", status, body, 200, checks={"status": "ready"})


def test_single_predictions(base_url):
    section("4. Single Predictions")

    cases = [
        {
            "name":     "Setosa sample",
            "features": [5.1, 3.5, 1.4, 0.2],
            "expected_class": "setosa",
        },
        {
            "name":     "Versicolor sample",
            "features": [5.8, 2.7, 4.1, 1.0],
            "expected_class": "versicolor",
        },
        {
            "name":     "Virginica sample",
            "features": [6.7, 3.0, 5.2, 2.3],
            "expected_class": "virginica",
        },
    ]

    for case in cases:
        status, body = post(f"{base_url}/predict", {"features": case["features"]})
        ok, _ = run_test(
            f"POST /predict — {case['name']}",
            status, body, 200,
            checks={"predicted_class": case["expected_class"]}
        )
        if ok:
            probs = body.get("probabilities", {})
            probs_str = "  |  ".join(f"{k}: {v:.4f}" for k, v in probs.items())
            print(f"         {c('Probs:', 'cyan')} {probs_str}")


def test_batch_prediction(base_url):
    section("5. Batch Prediction")
    payload = {
        "features": [
            [5.1, 3.5, 1.4, 0.2],
            [6.7, 3.0, 5.2, 2.3],
            [5.8, 2.7, 4.1, 1.0],
        ]
    }
    status, body = post(f"{base_url}/predict/batch", payload)
    ok, _ = run_test(
        "POST /predict/batch — 3 samples",
        status, body, 200,
        checks={"total": 3}
    )
    if ok:
        print(f"         {c('Results:', 'cyan')}")
        for i, pred in enumerate(body.get("predictions", [])):
            print(f"           [{i}] {pred['predicted_class']:12s} | "
                  f"{max(pred['probabilities'].values()):.4f} confidence")


def test_validation_errors(base_url):
    section("6. Input Validation (expect 422 errors)")

    bad_cases = [
        {
            "name":    "Too few features",
            "payload": {"features": [5.1, 3.5]},
        },
        {
            "name":    "Too many features",
            "payload": {"features": [5.1, 3.5, 1.4, 0.2, 99.0]},
        },
        {
            "name":    "Negative value",
            "payload": {"features": [5.1, -3.5, 1.4, 0.2]},
        },
        {
            "name":    "Empty features",
            "payload": {"features": []},
        },
    ]

    for case in bad_cases:
        status, body = post(f"{base_url}/predict", case["payload"])
        run_test(f"POST /predict — {case['name']}", status, body, 422)


def test_404(base_url):
    section("7. 404 on Unknown Route")
    status, body = get(f"{base_url}/not-a-real-route")
    run_test("GET /nonexistent", status, body, 404)


def print_summary():
    section("Test Summary")
    total = passed + failed
    print(f"\n  Total : {total}")
    print(f"  {c(f'Passed: {passed}', 'green')}")
    print(f"  {c(f'Failed: {failed}', 'red') if failed else c(f'Failed: {failed}', 'green')}")
    print()
    if failed == 0:
        print(c("  🎉 All tests passed! Container is healthy.", "green"))
    else:
        print(c(f"  ⚠️  {failed} test(s) failed. Check logs above.", "red"))
    print()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Test the Iris ML API container")
    parser.add_argument("--base-url", default=DEFAULT_URL, help="Base URL of the API")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    print(c("\n🐳 Iris ML API — Docker Container Test Suite", "bold"))
    print(c(f"   Target: {base_url}", "cyan"))

    if not wait_for_server(base_url):
        sys.exit(1)

    test_root(base_url)
    test_health(base_url)
    test_ready(base_url)
    test_single_predictions(base_url)
    test_batch_prediction(base_url)
    test_validation_errors(base_url)
    test_404(base_url)

    print_summary()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()