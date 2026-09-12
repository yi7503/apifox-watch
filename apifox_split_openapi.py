#!/usr/bin/env python3
"""
把 apifox_to_openapi.py 生成的整份 openapi.yaml 按一级模块拆分。

输出:
    <dump_dir>/openapi-split/<module>.yaml      每个一级模块一份独立 OpenAPI 3.0
    <dump_dir>/openapi-split/INDEX.md           索引

用法:
    python3 apifox_split_openapi.py /home/ubuntu/apifox-dump/2393904
"""
import os
import re
import sys
import argparse
import yaml
from collections import OrderedDict


def represent_str(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def represent_dict(dumper, data):
    return dumper.represent_mapping("tag:yaml.org,2002:map", data.items())


class _Dumper(yaml.SafeDumper):
    pass


_Dumper.add_representer(str, represent_str)
_Dumper.add_representer(OrderedDict, represent_dict)


SAFE_NAME_RE = re.compile(r"[^\w一-鿿\-]+")


def slug(name: str) -> str:
    s = SAFE_NAME_RE.sub("_", name).strip("_")
    return s or "default"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump_dir")
    ap.add_argument("--in", dest="inp", default=None, help="path to combined openapi.yaml")
    ap.add_argument("--out", default=None, help="output directory (default: <dump_dir>/openapi-split)")
    args = ap.parse_args()

    inp = args.inp or os.path.join(args.dump_dir, "openapi.yaml")
    out_dir = args.out or os.path.join(args.dump_dir, "openapi-split")
    os.makedirs(out_dir, exist_ok=True)

    print(f"[+] loading {inp} ...")
    spec = yaml.safe_load(open(inp, encoding="utf-8"))

    base_info = spec.get("info") or {}
    base_servers = spec.get("servers") or []
    all_tags = {t["name"]: t for t in (spec.get("tags") or []) if isinstance(t, dict) and t.get("name")}

    # bucket paths by top-level tag
    buckets = OrderedDict()  # top -> {"paths": OrderedDict, "tags": set, "op_count": int}

    HTTP_METHODS = ("get", "post", "put", "delete", "patch", "head", "options", "trace")

    for path, item in spec["paths"].items():
        # determine top-level tag from first operation's first tag
        top = None
        for m in HTTP_METHODS:
            if m in item:
                tags = item[m].get("tags") or []
                if tags:
                    top = tags[0].split(" / ")[0]
                    break
        top = top or "_untagged"
        b = buckets.setdefault(top, {"paths": OrderedDict(), "tags": set(), "ops": 0})
        b["paths"][path] = item
        for m in HTTP_METHODS:
            if m in item:
                b["ops"] += 1
                for t in item[m].get("tags") or []:
                    b["tags"].add(t)

    # write per-bucket files
    index_lines = [
        f"# {base_info.get('title', 'Apifox export')} — Split OpenAPI",
        "",
        f"Source: `{os.path.relpath(inp, out_dir)}`  ({len(spec['paths'])} paths total)",
        "",
        "| Module | Operations | Tags | File |",
        "|---|---:|---:|---|",
    ]

    expected_files = set()
    for top, b in sorted(buckets.items(), key=lambda x: -x[1]["ops"]):
        sub = OrderedDict()
        sub["openapi"] = spec.get("openapi", "3.0.3")
        sub["info"] = OrderedDict([
            ("title", f"{base_info.get('title', '')} — {top}"),
            ("version", base_info.get("version", "latest")),
            ("description", f"Split from full spec, module: {top}"),
        ])
        if base_servers:
            sub["servers"] = base_servers
        sub["tags"] = [all_tags.get(t, {"name": t}) for t in sorted(b["tags"])]
        sub["paths"] = b["paths"]

        fname = f"{slug(top)}.yaml"
        if fname in expected_files:
            sys.exit(f"split filename collision for module {top}: {fname}")
        expected_files.add(fname)
        fpath = os.path.join(out_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            yaml.dump(sub, f, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=1000)
        size_kb = os.path.getsize(fpath) / 1024
        print(f"  {top:30s}  {b['ops']:4d} ops  {len(b['tags']):3d} tags  -> {fname}  ({size_kb:.0f} KB)")
        index_lines.append(f"| {top} | {b['ops']} | {len(b['tags'])} | [{fname}]({fname}) |")

    for filename in os.listdir(out_dir):
        if filename.endswith(".yaml") and filename not in expected_files:
            os.remove(os.path.join(out_dir, filename))

    with open(os.path.join(out_dir, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index_lines))

    print(f"[OK] wrote {len(buckets)} files to {out_dir}")


if __name__ == "__main__":
    main()
