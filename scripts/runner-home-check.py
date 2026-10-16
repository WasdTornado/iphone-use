#!/usr/bin/env python3
"""真机 Home 回归：必须进入 SpringBoard，不能只检查请求是否返回 200。

运行前需解锁手机、启动运行器，并确保没有其他会话使用手机。
脚本只在计算器和桌面之间切换，不输入内容，也不终止应用。

    python3 scripts/runner-home-check.py [--base http://127.0.0.1:8100]
"""

import argparse
import json
import time
import urllib.request

import runner_auth


SPRINGBOARD = "com.apple.springboard"
CALCULATOR = "com.apple.calculator"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8100")
    args = parser.parse_args()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(args.base.rstrip("/") + path, data=data, method=method)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        runner_auth.sign(request)
        with opener.open(request, timeout=10) as response:
            result = json.load(response)
        value = result["value"]
        if isinstance(value, dict) and "error" in value:
            raise RuntimeError(value)
        return value

    def wait_for_app(bundle):
        deadline = time.monotonic() + 4
        while True:
            active = call("GET", "/apps/active")
            if active.get("bundleId") == bundle:
                return active
            if time.monotonic() >= deadline:
                raise AssertionError(f"expected {bundle}, got {active.get('bundleId')}")
            time.sleep(0.1)

    # 覆盖三个公开入口，并检查在 SpringBoard 前台时再次调用仍能保持前台状态。
    failures = []
    routes = [
        ("/home", {}),
        ("/wda/homescreen", {}),
        ("/wda/pressButton", {"name": "home"}),
    ]
    for path, body in routes:
        try:
            call("POST", "/launch", {"bundle": CALCULATOR})
            before = wait_for_app(CALCULATOR)
            call("POST", path, body)
            wait_for_app(SPRINGBOARD)
            call("POST", path, body)
            wait_for_app(SPRINGBOARD)
            call("POST", "/launch", {"bundle": CALCULATOR})
            after = wait_for_app(CALCULATOR)
            assert after["pid"] == before["pid"], "Home terminated or restarted Calculator"
            print(f"PASS {path}: SpringBoard in foreground; Calculator process preserved", flush=True)
        except (AssertionError, OSError, RuntimeError) as error:
            failures.append(path)
            print(f"FAIL {path}: {error}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
