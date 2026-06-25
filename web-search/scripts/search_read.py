#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search_read — 一步到位：先搜索，再自动抓取并抽取前 N 条结果的正文。
适合"给我查一下 X 并把要点读出来"这类需求，省去手动逐条 fetch。

用法：
  web search_read --query "..." [--top 3] [--max 8] [--format text|markdown] [--max-chars 4000]
"""
import argparse
from _common import web_search, fetch_extract, emit, fail, log, PROVIDER


def main():
    ap = argparse.ArgumentParser(prog="web search_read",
                                 description="搜索并自动读取前 N 条结果正文")
    ap.add_argument("--query", "-q", required=True, help="搜索关键词/问题")
    ap.add_argument("--top", "-t", type=int, default=3, help="抓取前几条结果的正文（默认 3）")
    ap.add_argument("--max", "-n", type=int, default=8, help="搜索结果条数（默认 8）")
    ap.add_argument("--format", "-f", choices=["text", "markdown"], default="text",
                    help="正文输出格式（默认 text）")
    ap.add_argument("--max-chars", "-m", type=int, default=4000,
                    help="每篇正文最多保留字符数（默认 4000，0=不限制）")
    args = ap.parse_args()

    try:
        log(f"  ▶ 搜索（后端={PROVIDER}）：{args.query}")
        results = web_search(args.query, max_results=max(1, args.max))
    except Exception as e:
        fail("search_read", f"搜索失败：{e}")

    log(f"  ✓ 命中 {len(results)} 条，抓取前 {min(args.top, len(results))} 篇正文 …")
    pages = []
    for i, item in enumerate(results[:max(1, args.top)]):
        url = item.get("url")
        if not url:
            continue
        try:
            log(f"  ▶ ({i+1}) 抓取：{url}")
            page = fetch_extract(url, markdown=(args.format == "markdown"),
                                 max_chars=max(0, args.max_chars))
            page["snippet"] = item.get("snippet", "")
            pages.append(page)
        except Exception as e:
            log(f"  ⚠ ({i+1}) 抓取失败，跳过：{e}")
            pages.append({"url": url, "title": item.get("title", ""),
                          "content": "", "error": str(e),
                          "snippet": item.get("snippet", "")})

    emit({"query": args.query, "provider": PROVIDER, "format": args.format,
          "search_count": len(results), "results": results,
          "read_count": len(pages), "pages": pages})


if __name__ == "__main__":
    main()
