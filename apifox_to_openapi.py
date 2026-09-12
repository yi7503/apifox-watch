#!/usr/bin/env python3
"""
把 apifox_scrape.py 抓下来的接口转成单个 OpenAPI 3.0 YAML。

用法:
    python3 apifox_to_openapi.py /home/ubuntu/apifox-dump/2393904
    python3 apifox_to_openapi.py /home/ubuntu/apifox-dump/2393904 --out openapi.yaml --title "七翔云开放平台"
"""
import os
import sys
import json
import argparse
import yaml
from collections import OrderedDict


def to_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() == "true"
    return bool(v)


def normalize_schema(s):
    """Pass through; Apifox jsonSchema is already OpenAPI-compatible (incl. x-apifox-* extensions)."""
    return s or {"type": "object"}


def media_type(content_type, fallback):
    """Apifox uses 'json' / 'xml' / 'plain' shorthand on responses; requestBody uses full mime."""
    if not content_type:
        return fallback or "application/json"
    if "/" in content_type:
        return content_type
    return {
        "json": "application/json",
        "xml": "application/xml",
        "plain": "text/plain",
        "html": "text/html",
        "raw": "text/plain",
        "msgpack": "application/x-msgpack",
        "binary": "application/octet-stream",
    }.get(content_type.lower(), "application/json")


def convert_parameter(p, in_):
    name = p.get("name")
    if not name:
        return None
    out = {
        "name": name,
        "in": in_,
        "required": to_bool(p.get("required")),
    }
    if p.get("description"):
        out["description"] = p["description"]
    schema = {"type": p.get("type") or "string"}
    if "enum" in p and p["enum"]:
        schema["enum"] = p["enum"]
    if "format" in p:
        schema["format"] = p["format"]
    out["schema"] = schema
    if p.get("sampleValue") not in (None, ""):
        out["example"] = p["sampleValue"]
    # path params must be required
    if in_ == "path":
        out["required"] = True
    return out


def collect_parameters(api):
    out = []
    params = api.get("parameters") or {}
    for loc in ("path", "query", "header", "cookie"):
        for p in params.get(loc) or []:
            cp = convert_parameter(p, loc)
            if cp:
                out.append(cp)
    # common parameters (project-level defaults attached to this api)
    cp = api.get("commonParameters") or {}
    for loc in ("path", "query", "header", "cookie"):
        for p in cp.get(loc) or []:
            cv = convert_parameter(p, loc)
            if cv:
                # de-dupe by (name, in)
                if not any(x["name"] == cv["name"] and x["in"] == cv["in"] for x in out):
                    out.append(cv)
    return out


def convert_request_body(api):
    rb = api.get("requestBody") or {}
    schema = rb.get("jsonSchema")
    if not schema:
        # form-data / form-urlencoded / parameters style
        params = rb.get("parameters") or []
        if not params:
            return None
        props = {}
        required = []
        for p in params:
            n = p.get("name")
            if not n:
                continue
            props[n] = {"type": p.get("type") or "string"}
            if p.get("description"):
                props[n]["description"] = p["description"]
            if to_bool(p.get("required")):
                required.append(n)
        schema = {"type": "object", "properties": props}
        if required:
            schema["required"] = required

    mt = media_type(rb.get("type") or rb.get("mediaType"), "application/json")
    body = {
        "required": to_bool(rb.get("required")),
        "content": {mt: {"schema": normalize_schema(schema)}},
    }
    # examples
    examples = rb.get("examples") or []
    if examples:
        body["content"][mt]["examples"] = {
            (ex.get("name") or f"example_{i}"): {
                "summary": ex.get("name") or "",
                "value": _try_parse_json(ex.get("data")),
            }
            for i, ex in enumerate(examples)
        }
    return body


def _try_parse_json(s):
    if s is None:
        return None
    if not isinstance(s, str):
        return s
    s = s.strip()
    if not s:
        return s
    try:
        return json.loads(s)
    except Exception:
        return s


def convert_responses(api):
    out = OrderedDict()
    response_examples = api.get("responseExamples") or []
    # group examples by responseId
    by_resp = {}
    for ex in response_examples:
        by_resp.setdefault(ex.get("responseId"), []).append(ex)

    for resp in api.get("responses") or []:
        code = str(resp.get("code") or "default")
        mt = media_type(resp.get("contentType"), "application/json")
        entry = {
            "description": resp.get("name") or resp.get("description") or "",
        }
        schema = resp.get("jsonSchema")
        if schema:
            entry["content"] = {mt: {"schema": normalize_schema(schema)}}
        # examples for this response
        examples = by_resp.get(resp.get("id")) or []
        if examples:
            entry.setdefault("content", {}).setdefault(mt, {"schema": {"type": "object"}})
            entry["content"][mt]["examples"] = {
                (ex.get("name") or f"example_{i}"): {
                    "summary": ex.get("name") or "",
                    "value": _try_parse_json(ex.get("data")),
                }
                for i, ex in enumerate(examples)
            }
        headers = resp.get("headers") or []
        if headers:
            entry["headers"] = {
                h["name"]: {
                    "description": h.get("description", ""),
                    "schema": {"type": h.get("type") or "string"},
                }
                for h in headers if h.get("name")
            }
        out[code] = entry

    if not out:
        out["200"] = {"description": "OK"}
    return out


def build_tags_from_tree(tree, by_api_id):
    """Walk the tree and assign folder-path tags to each api id."""
    tags = OrderedDict()  # tag_name -> description

    def walk(nodes, parents):
        for n in nodes:
            t = n.get("type")
            name = n.get("name", "")
            if t == "apiDetail":
                api = n.get("api") or {}
                aid = api.get("id")
                tag = " / ".join(parents) if parents else "Default"
                tags.setdefault(tag, "")
                by_api_id[aid] = tag
            else:
                new_parents = parents + [name] if t == "apiDetailFolder" else parents
                walk(n.get("children") or [], new_parents)

    walk(tree, [])
    return tags


def convert_api(api, tag):
    op = {
        "summary": api.get("name") or "",
        "operationId": api.get("operationId") or f"api-{api.get('id')}",
        "tags": [tag] if tag else [],
    }
    if api.get("description"):
        op["description"] = api["description"]
    params = collect_parameters(api)
    if params:
        op["parameters"] = params
    rb = convert_request_body(api)
    if rb:
        op["requestBody"] = rb
    op["responses"] = convert_responses(api)
    if api.get("status") and api["status"] != 1:
        op["x-apifox-status"] = api["status"]
    return op


# ---------- yaml block style ----------
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump_dir", help="apifox-dump/<projectId> directory")
    ap.add_argument("--out", default=None, help="output yaml path (default: <dump_dir>/openapi.yaml)")
    ap.add_argument("--title", default=None)
    ap.add_argument("--version", default="latest")
    args = ap.parse_args()

    apis_dir = os.path.join(args.dump_dir, "apis")
    tree_path = os.path.join(args.dump_dir, "tree.json")
    meta_path = os.path.join(args.dump_dir, "meta.json")
    if not os.path.isdir(apis_dir):
        sys.exit(f"not found: {apis_dir}")

    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    if not os.path.exists(tree_path):
        sys.exit(f"not found: {tree_path}")
    tree = json.load(open(tree_path))
    if not isinstance(tree, list) or not tree:
        sys.exit(f"invalid or empty tree: {tree_path}")

    by_api_id = {}
    tag_map = build_tags_from_tree(tree, by_api_id)
    if not by_api_id:
        sys.exit(f"tree contains no API nodes: {tree_path}")

    paths = OrderedDict()
    n_total = 0
    n_conflict = 0

    api_ids = sorted(by_api_id, key=str)
    if any(isinstance(api_id, bool) or not isinstance(api_id, int) or api_id <= 0 for api_id in api_ids):
        sys.exit(f"tree contains an invalid API id: {tree_path}")
    for api_id in api_ids:
        api_path = os.path.join(apis_dir, f"{api_id}.json")
        if not os.path.exists(api_path):
            sys.exit(f"missing API detail for tree node {api_id}: {api_path}")
        api = json.load(open(api_path))
        if api.get("id") != api_id:
            sys.exit(f"API detail id mismatch for tree node {api_id}: {api_path}")
        method = (api.get("method") or "get").lower()
        path = api.get("path") or f"/_apifox/{api.get('id')}"
        tag = by_api_id.get(api.get("id"), "")
        op = convert_api(api, tag)

        path_item = paths.setdefault(path, OrderedDict())
        if method in path_item:
            # duplicate path+method; disambiguate by suffixing path
            n_conflict += 1
            alt_path = f"{path}#{api.get('id')}"
            paths.setdefault(alt_path, OrderedDict())[method] = op
        else:
            path_item[method] = op
        n_total += 1

    spec = OrderedDict()
    spec["openapi"] = "3.0.3"
    spec["info"] = OrderedDict([
        ("title", args.title or f"Apifox project {meta.get('projectId', '')}"),
        ("version", args.version),
        ("description", f"Auto-converted from Apifox shared docs (projectId={meta.get('projectId')})"),
    ])
    spec["servers"] = []
    spec["tags"] = [{"name": t} for t in tag_map.keys()]
    spec["paths"] = paths

    out_path = args.out or os.path.join(args.dump_dir, "openapi.yaml")
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(
            spec, f, Dumper=_Dumper,
            allow_unicode=True, sort_keys=False, width=1000,
        )

    size = os.path.getsize(out_path)
    print(f"[OK] wrote {out_path}  ({size/1024/1024:.1f} MB)")
    print(f"     {n_total} operations across {len(paths)} path entries; {n_conflict} conflicts disambiguated")


if __name__ == "__main__":
    main()
