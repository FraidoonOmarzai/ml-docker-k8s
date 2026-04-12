#!/usr/bin/env python3
"""
ops/load_test.py
Sends concurrent requests to stress the API and trigger HPA autoscaling.
Pure stdlib — no external dependencies needed.

Usage:
    python ops/load_test.py                         # default settings
    python ops/load_test.py --url http://localhost:8080
    python ops/load_test.py --rps 50 --duration 60  # 50 req/s for 60s
    python ops/load_test.py --workers 20 --duration 120
"""

import json
import sys
import time
import argparse
import threading
import urllib.request
import urllib.error
from datetime import datetime
from collections import defaultdict

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_URL = "http://localhost:8080"
DEFAULT_DURATION = 30  # seconds
DEFAULT_WORKERS = 10  # concurrent threads
DEFAULT_RPS = 20  # target requests per second

# Rotating test payloads
PAYLOADS = [
    {"features": [5.1, 3.5, 1.4, 0.2]},
    {"features": [6.7, 3.0, 5.2, 2.3]},
    {"features": [5.8, 2.7, 4.1, 1.0]},
    {"features": [4.9, 3.0, 1.4, 0.2]},
    {"features": [7.0, 3.2, 4.7, 1.4]},
]

# ── Shared stats (thread-safe via lock) ───────────────────────────────────────
lock = threading.Lock()
stats = defaultdict(int)  # status_code → count
latencies = []
errors = []
stop_event = threading.Event()


def record(status, latency_ms, error=None):
    with lock:
        stats[status] += 1
        latencies.append(latency_ms)
        if error:
            errors.append(error)


# ── Worker thread ─────────────────────────────────────────────────────────────
def worker(base_url: str, worker_id: int, rps_per_worker: float):
    url = f"{base_url}/predict"
    delay = 1.0 / rps_per_worker if rps_per_worker > 0 else 0.1
    payload = PAYLOADS[worker_id % len(PAYLOADS)]
    data = json.dumps(payload).encode()

    while not stop_event.is_set():
        req = urllib.request.Request(
            url, data=data, method="POST", headers={"Content-Type": "application/json"}
        )
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        except Exception as ex:
            status = 0
            record(status, (time.perf_counter() - t0) * 1000, str(ex))
            time.sleep(delay)
            continue

        record(status, (time.perf_counter() - t0) * 1000)
        # Throttle to target RPS
        elapsed = time.perf_counter() - t0
        sleep_for = max(0, delay - elapsed)
        time.sleep(sleep_for)


# ── Progress printer ──────────────────────────────────────────────────────────
def print_progress(duration: int):
    start = time.time()
    while not stop_event.is_set():
        elapsed = time.time() - start
        remain = max(0, duration - elapsed)
        with lock:
            total = sum(stats.values())
            ok = stats.get(200, 0)
            errs = total - ok
            lats = latencies[:]
        avg_lat = (sum(lats) / len(lats)) if lats else 0
        actual_rps = total / elapsed if elapsed > 0 else 0

        bar_len = 30
        filled = int(bar_len * elapsed / duration)
        bar = "█" * filled + "░" * (bar_len - filled)

        print(
            f"\r  [{bar}] {elapsed:5.1f}s/{duration}s | "
            f"reqs={total:5d} | ok={ok:5d} | err={errs:3d} | "
            f"rps={actual_rps:5.1f} | avg={avg_lat:5.1f}ms",
            end="",
            flush=True,
        )
        time.sleep(0.5)
    print()  # newline after progress bar


# ── Final report ──────────────────────────────────────────────────────────────
def print_report(duration_actual: float, num_workers: int, target_rps: int):
    with lock:
        total = sum(stats.values())
        ok = stats.get(200, 0)
        lats_copy = latencies[:]
        errs_copy = errors[:]
        status_map = dict(stats)

    if not lats_copy:
        print("No requests completed.")
        return

    lats_sorted = sorted(lats_copy)
    n = len(lats_sorted)
    avg = sum(lats_sorted) / n
    p50 = lats_sorted[int(n * 0.50)]
    p95 = lats_sorted[int(n * 0.95)]
    p99 = lats_sorted[int(n * 0.99)]
    mn = lats_sorted[0]
    mx = lats_sorted[-1]
    actual_rps = total / duration_actual
    error_rate = ((total - ok) / total * 100) if total else 0
    success_rate = (ok / total * 100) if total else 0

    print("\n" + "═" * 60)
    print("  LOAD TEST REPORT")
    print("═" * 60)
    print(f"  Duration       : {duration_actual:.1f}s")
    print(f"  Workers        : {num_workers}")
    print(f"  Target RPS     : {target_rps}")
    print(f"  Actual RPS     : {actual_rps:.1f}")
    print()
    print(f"  Total requests : {total}")
    print(f"  Successful     : {ok}  ({success_rate:.1f}%)")
    print(f"  Failed         : {total - ok}  ({error_rate:.1f}%)")
    print()
    print(f"  Status codes   : {status_map}")
    print()
    print("  Latency (ms):")
    print(f"    min  : {mn:.1f}")
    print(f"    avg  : {avg:.1f}")
    print(f"    p50  : {p50:.1f}")
    print(f"    p95  : {p95:.1f}")
    print(f"    p99  : {p99:.1f}")
    print(f"    max  : {mx:.1f}")

    if errs_copy:
        print(f"\n  Sample errors ({min(3, len(errs_copy))} of {len(errs_copy)}):")
        for e in errs_copy[:3]:
            print(f"    - {e}")

    print("═" * 60)

    # Grade the result
    if error_rate < 1 and p95 < 500:
        print("  🟢 RESULT: Excellent — low error rate, fast latency")
    elif error_rate < 5 and p95 < 1000:
        print("  🟡 RESULT: Acceptable — some degradation under load")
    else:
        print("  🔴 RESULT: Poor — high errors or slow latency")
    print()

    # HPA tip
    print("  💡 Watch HPA scale up in real-time (run in another terminal):")
    print("     kubectl get hpa -n dock8s-namespace -w")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Load test the Docker + k8s Inference API"
    )
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--rps", type=float, default=DEFAULT_RPS)
    args = parser.parse_args()

    rps_per_worker = args.rps / args.workers

    print(f"\n🔥 Load Test — Docker + k8s Inference API")
    print(f"   URL          : {args.url}")
    print(f"   Duration     : {args.duration}s")
    print(f"   Workers      : {args.workers}")
    print(f"   Target RPS   : {args.rps}")
    print(f"   Started      : {datetime.now().strftime('%H:%M:%S')}\n")
    print("  Tip: in another terminal run:")
    print("       kubectl get hpa -n dock8s-namespace -w")
    print("       kubectl get pods -n dock8s-namespace -w\n")

    # Warm up
    print("  Warming up (3s)...")
    time.sleep(3)

    # Start workers
    threads = []
    for i in range(args.workers):
        t = threading.Thread(
            target=worker, args=(args.url, i, rps_per_worker), daemon=True
        )
        t.start()
        threads.append(t)

    # Progress display
    prog = threading.Thread(target=print_progress, args=(args.duration,), daemon=True)
    prog.start()

    start = time.time()
    time.sleep(args.duration)
    stop_event.set()

    # Wait for threads
    for t in threads:
        t.join(timeout=5)
    prog.join(timeout=2)

    duration_actual = time.time() - start
    print_report(duration_actual, args.workers, args.rps)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        stop_event.set()
        print("\n\n  Load test interrupted by user.")
        sys.exit(0)
