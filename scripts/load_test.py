#!/usr/bin/env python3
"""Simulate N concurrent teachers starting, autosaving, and submitting a
pre-test attempt against a running ceequiz instance.

Usage:
    python scripts/load_test.py --base-url http://localhost:8000 --code <quiz_code> --concurrency 50
"""
import argparse
import concurrent.futures
import random
import statistics
import time

import requests


def run_one(base_url, code, idx):
    session = requests.Session()
    timings = []

    def timed(method, url, **kwargs):
        start = time.monotonic()
        resp = session.request(method, url, timeout=20, **kwargs)
        timings.append(time.monotonic() - start)
        return resp

    entry_url = f"{base_url}/q/{code}/"
    resp = timed("GET", entry_url)
    csrftoken = session.cookies.get("csrftoken")

    mobile = f"9{random.randint(100000000, 999999999)}"
    resp = timed(
        "POST",
        f"{base_url}/q/{code}/start/",
        data={
            "csrfmiddlewaretoken": csrftoken,
            "name": f"Load Test Teacher {idx}",
            "district": "1",
            "mobile": mobile,
            "school_name": "Load Test School",
            "designation": "Teacher",
        },
        allow_redirects=True,
    )
    ok_start = resp.status_code == 200

    order = 1
    ok_answers = True
    while True:
        resp = timed("GET", f"{base_url}/q/{code}/question/{order}/")
        if resp.status_code != 200:
            ok_answers = False
            break
        resp = timed(
            "POST",
            f"{base_url}/q/{code}/answer/{order}/",
            data={"csrfmiddlewaretoken": session.cookies.get("csrftoken"), "option": "A"},
        )
        ok_answers = ok_answers and resp.status_code == 200
        if "has_next" not in resp.text and order >= 10:
            break
        order += 1
        if order > 50:
            break

    resp = timed(
        "POST",
        f"{base_url}/q/{code}/submit/",
        data={"csrfmiddlewaretoken": session.cookies.get("csrftoken")},
    )
    ok_submit = resp.status_code == 200

    return {"ok": ok_start and ok_answers and ok_submit, "timings": timings}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--code", required=True, help="Quiz code with pre-test currently open")
    parser.add_argument("--concurrency", type=int, default=50)
    args = parser.parse_args()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(run_one, args.base_url, args.code, i) for i in range(args.concurrency)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    all_timings = [t for r in results for t in r["timings"]]
    errors = sum(1 for r in results if not r["ok"])
    all_timings.sort()
    p95 = all_timings[int(len(all_timings) * 0.95)] if all_timings else 0

    print(f"Participants: {len(results)}  Errors: {errors}")
    print(f"Requests: {len(all_timings)}  p95: {p95*1000:.0f}ms  max: {max(all_timings)*1000:.0f}ms")


if __name__ == "__main__":
    main()
