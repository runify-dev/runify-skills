#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web.py — 跨平台统一启动器（与 bash 版 web / web.cmd 等价）。
两个平台都用同一种写法：
    python3 web.py <command> [args...]
    py -3   web.py <command> [args...]   (Windows 没有 python3 时)

例:
    python3 web.py search --query "claude code"
    python3 web.py fetch --url https://example.com --format markdown
    python3 web.py                # 列出所有命令
"""
import os
import sys
import json
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(HERE, "scripts")
if not os.path.isdir(SCRIPTS_DIR) and os.path.exists(os.path.join(HERE, "_common.py")):
    SCRIPTS_DIR = HERE


def _err(msg):
    print("RESULT_JSON: " + json.dumps(
        {"status": "error", "stage": "web", "error": msg}, ensure_ascii=False),
        flush=True)


def list_commands(stream=sys.stdout):
    print("web — 可用命令（用法: python3 web.py <command> [args...]）\n", file=stream)
    if os.path.isdir(SCRIPTS_DIR):
        for fn in sorted(os.listdir(SCRIPTS_DIR)):
            if fn.endswith(".py") and not fn.startswith("_"):
                print("  web " + fn[:-3], file=stream)
    print("\n查看某命令的参数：python3 web.py <command> --help", file=stream)


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help", "list"):
        list_commands()
        return 0

    cmd = args[0]
    rest = args[1:]
    target = os.path.join(SCRIPTS_DIR, cmd + ".py")
    if not os.path.isfile(target):
        _err("未知命令: " + cmd)
        list_commands(sys.stderr)
        return 0

    proc = subprocess.run([sys.executable, target] + rest)
    if proc.returncode != 0:
        print("RESULT_JSON: " + json.dumps(
            {"status": "error", "stage": cmd,
             "error": "命令异常退出（exit %d），详见 stderr" % proc.returncode},
            ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
