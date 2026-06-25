#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
desk.py — runctl 的薄封装/统一入口。

它本身不实现任何桌面操作：真正干活的是 `runctl` 这个单文件二进制。
本封装只负责三件事：
  1) 定位 runctl（PATH / ~/.cargo/bin / /usr/local/bin / 本技能 bin/）；
  2) 缺失时用 `./desk setup` 自动安装（cargo 或 macOS install.sh）；
  3) 把其余子命令【原样转发】给 runctl，并【保留 runctl 的退出码】。

⚠ 与 agnes/web 技能不同：runctl 的退出码是有语义的（0 成功 / 1 错误 /
   2 参数错 / 124 watch 超时未变化），所以这里【不】强制 exit 0、【不】包裹它的
   stdout——runctl 自己会打印人类摘要或 `--json` 的机器可读结果，直接透传。

用法：
  ./desk setup                 # 确保 runctl 已安装，并打印权限检查
  ./desk which                 # 打印解析到的 runctl 路径
  ./desk <runctl 子命令> ...   # 等价于 README 里的 `runctl <子命令> ...`
    例：./desk --json list
        ./desk shot --window 微信 --out wx.png
        ./desk watch --window 微信 --until-change --duration 60
"""
import os
import sys
import json
import shutil
import platform
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
IS_WIN = os.name == "nt"
EXE = "runctl.exe" if IS_WIN else "runctl"
INSTALL_SH_URL = "https://raw.githubusercontent.com/runify-dev/runctl/main/install.sh"
CARGO_GIT = "https://github.com/runify-dev/runctl"

# 安装相关可选 env（见 README install.sh 的旋钮）
RUNCTL_VERSION = os.environ.get("RUNCTL_VERSION", "").strip()
RUNCTL_INSTALL_DIR = os.environ.get("RUNCTL_INSTALL_DIR", "").strip()


def _out(obj, code=0):
    """封装层自身的结构化输出（仅用于 setup/which/未找到等元操作；转发时不用）。"""
    print("RESULT_JSON: " + json.dumps(obj, ensure_ascii=False), flush=True)
    sys.exit(code)


def find_runctl():
    cands = []
    p = shutil.which("runctl")
    if p:
        cands.append(p)
    home = os.path.expanduser("~")
    cands += [
        os.path.join(home, ".cargo", "bin", EXE),
        os.path.join("/usr/local/bin", EXE),
        os.path.join("/opt/homebrew/bin", EXE),
        os.path.join(HERE, "bin", EXE),
    ]
    if RUNCTL_INSTALL_DIR:
        cands.insert(0, os.path.join(RUNCTL_INSTALL_DIR, EXE))
    seen = set()
    for c in cands:
        if not c or c in seen:
            continue
        seen.add(c)
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def do_check(rc):
    """跑一遍 runctl check（macOS 上报告权限），结果直接透传给调用方。"""
    try:
        subprocess.run([rc, "check"])
    except Exception as e:
        print(f"  ⚠ 运行 `runctl check` 失败：{e}", file=sys.stderr)


def do_setup():
    rc = find_runctl()
    if rc:
        print(f"  ✓ runctl 已安装：{rc}", file=sys.stderr)
        do_check(rc)
        _out({"status": "ok", "action": "setup", "runctl": rc,
              "note": "已就绪。macOS 首次使用前请按 check 结果授予 屏幕录制 + 辅助功能 权限。"})

    sysname = platform.system().lower()
    # 1) 优先 cargo（任意平台都能装；从源码编译，稍慢但最稳）
    if shutil.which("cargo"):
        cmd = ["cargo", "install", "--git", CARGO_GIT]
        if RUNCTL_VERSION:
            cmd += ["--tag", RUNCTL_VERSION]
        print(f"  ▶ 用 cargo 安装：{' '.join(cmd)}", file=sys.stderr)
        r = subprocess.run(cmd)
        if r.returncode == 0:
            rc = find_runctl()
            if rc:
                do_check(rc)
                _out({"status": "ok", "action": "setup", "via": "cargo", "runctl": rc})
        print("  ⚠ cargo 安装未成功，尝试其它方式…", file=sys.stderr)

    # 2) macOS 无 cargo：走官方 install.sh（下载预编译二进制 + 校验 SHA-256）
    if sysname == "darwin" and shutil.which("curl") and shutil.which("sh"):
        env = os.environ.copy()
        if RUNCTL_VERSION:
            env["RUNCTL_VERSION"] = RUNCTL_VERSION
        if RUNCTL_INSTALL_DIR:
            env["RUNCTL_INSTALL_DIR"] = RUNCTL_INSTALL_DIR
        print(f"  ▶ 用官方 install.sh 安装（{INSTALL_SH_URL}）", file=sys.stderr)
        r = subprocess.run(f"curl -fsSL {INSTALL_SH_URL} | sh", shell=True, env=env)
        if r.returncode == 0:
            rc = find_runctl()
            if rc:
                do_check(rc)
                _out({"status": "ok", "action": "setup", "via": "install.sh", "runctl": rc})

    # 3) 都不行：把可行的安装方式指引回去
    _out({
        "status": "needs_config", "action": "setup",
        "message": "未能自动安装 runctl。",
        "how_to_install": [
            "安装 Rust 后：cargo install --git " + CARGO_GIT,
            "macOS（无 cargo）：curl -fsSL " + INSTALL_SH_URL + " | sh",
            "Windows：cargo install --git " + CARGO_GIT + "，或从 GitHub Releases 下载 runctl.exe 放进 PATH",
        ],
        "where": "需要在运行本技能的机器上安装一次 runctl（它是单文件二进制，无运行时依赖）。",
    }, code=0)


def forward(args):
    rc = find_runctl()
    if not rc:
        # 退出码 127：约定为「runctl 不存在，请先 ./desk setup」，与 runctl 自身的 0/1/2/124 区分开
        _out({"status": "needs_setup", "error": "未找到 runctl 二进制",
              "fix": "先运行 `./desk setup` 安装，或手动安装后重试（见 ./desk setup 的指引）"},
             code=127)
    # 原样转发：继承 stdout/stderr，保留 runctl 的退出码（0/1/2/124 等都有语义）
    proc = subprocess.run([rc] + args)
    sys.exit(proc.returncode)


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd = args[0]
    if cmd in ("setup", "install"):
        do_setup()
    if cmd in ("which", "doctor", "ensure"):
        rc = find_runctl()
        if rc:
            if cmd == "doctor":
                do_check(rc)
            _out({"status": "ok", "runctl": rc})
        _out({"status": "needs_setup", "error": "未找到 runctl",
              "fix": "运行 `./desk setup`"}, code=127)
    # 其余一律转发给 runctl
    forward(args)


if __name__ == "__main__":
    sys.exit(main())
