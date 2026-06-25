#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search — 网络搜索：给一句话，返回若干条结果（标题/链接/摘要）。
不抓正文；要读页面正文用 fetch，要"搜了就读"用 search_read。

用法：
  web search --query "claude code 是什么" [--max 8] [--json]
"""
import argparse
from _common import web_search, emit, fail, log, PROVIDER


def main():
    ap = argparse.ArgumentParser(prog="web search", description="网络搜索，返回结果列表")
    ap.add_argument("--query", "-q", required=True, help="搜索关键词/问题")
    ap.add_argument("--max", "-n", type=int, default=8, help="返回结果条数（默认 8）")
    args = ap.parse_args()

    try:
        log(f"  ▶ 搜索（后端={PROVIDER}）：{args.query}")
        results = web_search(args.query, max_results=max(1, args.max))
    except Exception as e:
        fail("search", f"搜索失败：{e}")

    log(f"  ✓ 命中 {len(results)} 条")
    emit({"query": args.query, "provider": PROVIDER,
          "count": len(results), "results": results,
          "next": "用 `web fetch --url <某条url>` 读取正文，或 `web search_read` 一步到位"})


if __name__ == "__main__":
    main()
