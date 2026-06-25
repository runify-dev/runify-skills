#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch — 抓取一个网页并抽取正文（去掉脚本/导航/页脚等噪声）。
纯 HTTP 抓取 + 标准库解析，不渲染 JavaScript；强 JS 站点可能取不到正文。

用法：
  web fetch --url https://example.com [--format text|markdown] [--max-chars 0]
"""
import argparse
from _common import fetch_extract, emit, fail, log


def main():
    ap = argparse.ArgumentParser(prog="web fetch", description="抓取网页并抽取正文")
    ap.add_argument("--url", "-u", required=True, help="要抓取的网页 URL")
    ap.add_argument("--format", "-f", choices=["text", "markdown"], default="text",
                    help="输出格式：text（默认，纯文本）或 markdown（保留标题/链接/列表）")
    ap.add_argument("--max-chars", "-m", type=int, default=0,
                    help="正文最多保留多少字符，0=不限制（默认）")
    args = ap.parse_args()

    if not args.url.lower().startswith(("http://", "https://")):
        fail("fetch", f"url 必须以 http(s):// 开头：{args.url}")

    try:
        log(f"  ▶ 抓取：{args.url}")
        page = fetch_extract(args.url, markdown=(args.format == "markdown"),
                             max_chars=max(0, args.max_chars))
    except Exception as e:
        fail("fetch", f"抓取失败：{e}")

    log(f"  ✓ 正文 {page.get('length', 0)} 字{'（已截断）' if page.get('truncated') else ''}")
    page["format"] = args.format
    emit(page)


if __name__ == "__main__":
    main()
