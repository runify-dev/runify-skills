#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agnes.py — 跨平台统一启动器。
不依赖 PATH、不依赖后缀、不依赖 shell：两个平台都用同一种写法调用——
    python3 agnes.py <command> [args...]
    py -3   agnes.py <command> [args...]   (Windows 没有 python3 时)

例:
    python3 agnes.py text_to_image --prompt "一只猫"
    python3 agnes.py image_to_video --images a,b --keyframes --prompt "..."
    python3 agnes.py                # 列出所有命令

它只是把子命令分发到 scripts/<command>.py，并用「当前这个 Python 解释器」执行，
因此不会出现 "python 指向 py2" 之类问题（用什么解释器跑 agnes.py，就用什么跑子命令）。
"""
import os
import sys
import json
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(HERE, "scripts")
if not os.path.isdir(SCRIPTS_DIR) and os.path.exists(os.path.join(HERE, "_common.py")):
    SCRIPTS_DIR = HERE  # 兼容把 agnes.py 放进 scripts/ 内


def _err(msg):
    # 结果统一走 stdout（按 status 区分），便于调用方只读 stdout
    print("RESULT_JSON: " + json.dumps(
        {"status": "error", "stage": "agnes", "error": msg}, ensure_ascii=False),
        flush=True)


def list_commands(stream=sys.stdout):
    print("agnes — 可用命令（用法: python3 agnes.py <command> [args...]）\n", file=stream)
    if os.path.isdir(SCRIPTS_DIR):
        for fn in sorted(os.listdir(SCRIPTS_DIR)):
            if fn.endswith(".py") and not fn.startswith("_"):
                print("  agnes " + fn[:-3], file=stream)
    print("\n查看某命令的参数：python3 agnes.py <command> --help", file=stream)


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

    # 用「正在运行 agnes.py 的同一个解释器」执行子命令，参数原样透传。
    # 约定：退出码恒为 0；结果走 stdout（成功/失败/needs_config 都在 RESULT_JSON 里，按 status 区分）；
    # 进度走 stderr（不入调用方上下文）。子进程的 stdout/stderr 直接继承，不拦截。
    proc = subprocess.run([sys.executable, target] + rest)
    # 子进程若意外崩溃（非 0 且可能未输出 RESULT_JSON，例如未捕获异常的 traceback 只在 stderr），
    # 补一条 error 结果到 stdout，保证调用方总能从 stdout 读到结构化结果。
    if proc.returncode != 0:
        print("RESULT_JSON: " + json.dumps(
            {"status": "error", "stage": cmd,
             "error": "命令异常退出（exit %d），详见 stderr 进度/错误输出" % proc.returncode},
            ensure_ascii=False), flush=True)
    return 0   # 入口恒返回 0


if __name__ == "__main__":
    sys.exit(main())
