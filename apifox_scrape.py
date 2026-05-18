#!/usr/bin/env python3
"""
Apifox 分享文档站爬虫
用法:
    python3 apifox_scrape.py https://openapi.qixiangyun.com/doc-2179520
    python3 apifox_scrape.py openapi.qixiangyun.com

输出目录: ./apifox-dump/<projectId>/
  - meta.json              域名信息 (projectId/branchId)
  - tree.json              接口/文档树
  - apis/<apiId>.json      每个接口的完整详情
  - docs/<docId>.json      每个文档节点的内容
  - index.md               可读的索引 (方法 / 路径 / 名称 / 文件链接)
"""
import sys
import os
import json
import time
import re
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

API_BASE = "https://api.apifox.com/api/v1"
CONCURRENCY = 8
RETRY = 3
TIMEOUT = 20


def session_for(domain: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (apifox-scraper)",
        "Accept": "application/json",
        "Origin": f"https://{domain}",
        "Referer": f"https://{domain}/",
    })
    return s


def get_json(s: requests.Session, url: str) -> dict:
    last = None
    for i in range(RETRY):
        try:
            r = s.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            j = r.json()
            if j.get("success") is False:
                raise RuntimeError(f"api error: {j}")
            return j["data"]
        except Exception as e:
            last = e
            time.sleep(0.5 * (i + 1))
    raise RuntimeError(f"GET {url} failed after {RETRY} retries: {last}")


def parse_input(arg: str) -> str:
    """Accept either full URL or bare domain. Return domain."""
    if "://" not in arg:
        arg = "https://" + arg
    return urlparse(arg).netloc


def walk_tree(nodes):
    """Yield (kind, id, name, path) for each leaf api/doc."""
    stack = [(n, []) for n in reversed(nodes)]
    while stack:
        node, parents = stack.pop()
        name = node.get("name", "")
        new_parents = parents + [name]
        t = node.get("type")
        if t == "apiDetail":
            api = node.get("api") or {}
            yield ("api", api.get("id"), name, "/".join(parents), api)
        elif t == "doc":
            doc = node.get("doc") or {}
            yield ("doc", doc.get("id"), name, "/".join(parents), doc)
        for c in reversed(node.get("children") or []):
            stack.append((c, new_parents))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    domain = parse_input(sys.argv[1])
    print(f"[+] domain = {domain}")

    s = session_for(domain)

    # 1. domain -> projectId/branchId
    meta = get_json(s, f"{API_BASE}/published-projects/domains/{domain}")
    project_id = meta["projectId"]
    versions = meta.get("versionSettings") or []
    default_branch = next((v for v in versions if v.get("isDefaultVersion")), versions[0] if versions else None)
    branch_id = default_branch["branchId"] if default_branch else None
    print(f"[+] projectId={project_id}  branchId={branch_id}")

    out_root = os.path.join(os.getcwd(), "apifox-dump", str(project_id))
    apis_dir = os.path.join(out_root, "apis")
    docs_dir = os.path.join(out_root, "docs")
    os.makedirs(apis_dir, exist_ok=True)
    os.makedirs(docs_dir, exist_ok=True)
    with open(os.path.join(out_root, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 2. tree
    tree_url = f"{API_BASE}/published-projects/{project_id}/http-api-tree"
    if branch_id:
        tree_url += f"?branchId={branch_id}"
    tree = get_json(s, tree_url)
    with open(os.path.join(out_root, "tree.json"), "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=2)

    leaves = list(walk_tree(tree))
    apis = [x for x in leaves if x[0] == "api"]
    docs = [x for x in leaves if x[0] == "doc"]
    print(f"[+] tree: {len(apis)} apis, {len(docs)} docs")

    # 3. fetch details in parallel
    def fetch_api(api_id):
        url = f"{API_BASE}/published-projects/{project_id}/http-apis/{api_id}"
        if branch_id:
            url += f"?branchId={branch_id}"
        return api_id, get_json(s, url)

    def fetch_doc(doc_id):
        url = f"{API_BASE}/published-projects/{project_id}/doc/{doc_id}"
        if branch_id:
            url += f"?branchId={branch_id}"
        return doc_id, get_json(s, url)

    failures = []
    print(f"[+] fetching {len(apis)} api details (concurrency={CONCURRENCY}) ...")
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(fetch_api, a[1]): a for a in apis if a[1]}
        done = 0
        for fut in as_completed(futs):
            a = futs[fut]
            try:
                aid, data = fut.result()
                with open(os.path.join(apis_dir, f"{aid}.json"), "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                failures.append(("api", a[1], a[2], str(e)))
            done += 1
            if done % 20 == 0 or done == len(futs):
                print(f"    api {done}/{len(futs)}")

    print(f"[+] fetching {len(docs)} doc details ...")
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(fetch_doc, d[1]): d for d in docs if d[1]}
        done = 0
        for fut in as_completed(futs):
            d = futs[fut]
            try:
                did, data = fut.result()
                with open(os.path.join(docs_dir, f"{did}.json"), "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                failures.append(("doc", d[1], d[2], str(e)))
            done += 1
            if done % 20 == 0 or done == len(futs):
                print(f"    doc {done}/{len(futs)}")

    # 4. index.md
    lines = [f"# Apifox dump — projectId {project_id}", ""]
    lines.append(f"- domain: `{domain}`")
    lines.append(f"- branchId: `{branch_id}`")
    lines.append(f"- apis: {len(apis)}  docs: {len(docs)}")
    lines.append("")
    lines.append("## APIs")
    lines.append("")
    lines.append("| Method | Path | Name | Folder | File |")
    lines.append("|---|---|---|---|---|")
    for kind, _id, name, parent, payload in apis:
        m = (payload.get("method") or "").upper()
        p = payload.get("path") or ""
        safe_name = (name or "").replace("|", "\\|")
        lines.append(f"| {m} | `{p}` | {safe_name} | {parent} | [apis/{_id}.json](apis/{_id}.json) |")
    lines.append("")
    lines.append("## Docs")
    lines.append("")
    lines.append("| Name | Folder | File |")
    lines.append("|---|---|---|")
    for kind, _id, name, parent, payload in docs:
        safe_name = (name or "").replace("|", "\\|")
        lines.append(f"| {safe_name} | {parent} | [docs/{_id}.json](docs/{_id}.json) |")
    with open(os.path.join(out_root, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    if failures:
        print(f"[!] {len(failures)} failures:")
        for kind, _id, name, err in failures[:20]:
            print(f"    {kind} {_id} ({name}): {err}")
        with open(os.path.join(out_root, "failures.json"), "w", encoding="utf-8") as f:
            json.dump(failures, f, ensure_ascii=False, indent=2)

    print(f"[OK] saved to {out_root}")


if __name__ == "__main__":
    main()
