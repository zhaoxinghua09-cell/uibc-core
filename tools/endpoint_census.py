"""endpoint_census.py -- 282 条 DID 方法：公开解析端点普查（只读，并发版）

与 registry_census.py 的分工：
  registry_census 回答“登记册里写了什么”；
  endpoint_census 回答“按登记项给的规范，能不能找到一个外人能打的解析地址”。

四档结论，缺一不可：
  ENDPOINT_OK                 规范给了地址，实测 2xx
  ENDPOINT_NOT_OK             规范给了地址，实测非 2xx（记状态码）
  NO_PUBLIC_ENDPOINT_IN_SPEC  规范里没有可打地址（相对路径 / SDK / 私有网关）
  SPEC_UNAVAILABLE            规范取不到（403/404/超时/非文本）

“未找到”不等于“不存在”，故 NO_PUBLIC_ENDPOINT_IN_SPEC 单列，绝不并入 NOT_OK。
并发 16，单请求 6s，不对主机设黑名单（黑名单会把偶发超时放大成整片假结论）。
"""
import json, os, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CENSUS = os.path.join(ROOT, "docs", "REGISTRY-CENSUS.json")
OUT = os.path.join(ROOT, "docs", "ENDPOINT-CENSUS.json")
UA = {"User-Agent": "uibc-core-endpoint-census/0.2 (public read-only census)"}
TMO = 6

CAND = [
    re.compile(r"https?://[^\s\)\]\"'<>`]+?/1\.0/identifiers/[^\s\)\]\"'<>`]+"),
    re.compile(r"https?://[^\s\)\]\"'<>`]+?/resolve/[^\s\)\]\"'<>`]+", re.I),
    re.compile(r"https?://[^\s\)\]\"'<>`]+?(?:didservice|did/resolve|resolve-verify)[^\s\)\]\"'<>`]*"),
    re.compile(r"https?://[^\s\)\]\"'<>`]+?/api/[^\s\)\]\"'<>`]*(?:resolve|did)[^\s\)\]\"'<>`]*", re.I),
]

DEAD_HOSTS = {}


def host_of(u):
    m = re.match(r"https?://([^/]+)", u or "")
    return m.group(1).lower() if m else ""


def to_raw(u):
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)", u)
    if m:
        return "https://raw.githubusercontent.com/%s/%s/%s/%s" % m.groups()
    return u


def get(u, n=250000):
    """取规范正文。两次尝试，不设主机黑名单——黑名单会把偶发超时放大成整片假结论。"""
    for attempt in range(2):
        try:
            r = urllib.request.Request(u, headers=UA)
            with urllib.request.urlopen(r, timeout=TMO) as f:
                return f.status, f.read(n).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:
                return e.code, ""          # 4xx 是真结论，不必重试
            if attempt == 1:
                return e.code, ""
        except Exception:
            if attempt == 1:
                return 0, ""
            time.sleep(0.5)
    return 0, ""


def probe(u):
    try:
        r = urllib.request.Request(u, headers=UA, method="GET")
        with urllib.request.urlopen(r, timeout=TMO) as f:
            return f.status, len(f.read(2048))
    except urllib.error.HTTPError as e:
        return e.code, 0
    except Exception:
        return 0, 0


def one(m):
    name, spec = m.get("method"), (m.get("specification") or "").strip()
    rec = {"method": name, "spec": spec, "candidates": [], "verdict": "", "status": None, "bytes": None, "note": ""}
    if not spec:
        rec.update(verdict="NO_PUBLIC_ENDPOINT_IN_SPEC", note="登记项没有规范地址")
        return rec
    st, txt = get(to_raw(spec))
    if st != 200 or not txt:
        rec.update(verdict="SPEC_UNAVAILABLE",
                   note="规范取不到 HTTP %s%s" % (st, "（该主机两次超时后跳过）" if st == 0 else ""))
        return rec
    cands = []
    for rx in CAND:
        for c in rx.findall(txt):
            c = c.rstrip(".,;:)")
            if c not in cands:
                cands.append(c)
    rec["candidates"] = cands[:3]
    if not cands:
        rec.update(verdict="NO_PUBLIC_ENDPOINT_IN_SPEC", note="规范里没有可打地址（相对路径 / SDK / 私有网关）")
        return rec
    best = (cands[0], 0, 0)
    for c in cands[:3]:
        code, n = probe(c)
        if 200 <= code < 300:
            best = (c, code, n)
            break
        if code and best[1] == 0:
            best = (c, code, 0)
    rec["status"], rec["bytes"] = best[1], best[2]
    rec["verdict"] = "ENDPOINT_OK" if 200 <= (best[1] or 0) < 300 else "ENDPOINT_NOT_OK"
    rec["note"] = "探测 %s" % best[0]
    return rec


def run():
    census = json.load(open(CENSUS, encoding="utf-8"))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(one, census["methods"]))
    stats = {k: 0 for k in ("ENDPOINT_OK", "ENDPOINT_NOT_OK", "NO_PUBLIC_ENDPOINT_IN_SPEC", "SPEC_UNAVAILABLE")}
    for r in rows:
        stats[r["verdict"]] += 1
    doc = {"registry": census.get("registry"), "universe": len(census["methods"]),
           "denominator": len(rows), "total": stats,
           "rule": "只读 GET；并发 8；单请求 6s，取规范两次尝试；每条最多 3 个候选，首个 2xx 即止",
           "elapsed_s": round(time.time() - t0, 1), "methods": rows,
           "reading": "分母=登记册全量；NO_PUBLIC_ENDPOINT_IN_SPEC 单列，不与 NOT_OK 混计"}
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False), "elapsed", doc["elapsed_s"], "s ->", OUT)


def check():
    d = json.load(open(OUT, encoding="utf-8"))
    assert d["universe"] == 282 and d["denominator"] == len(d["methods"]) == 282
    assert sum(d["total"].values()) == 282
    ok = {"ENDPOINT_OK", "ENDPOINT_NOT_OK", "NO_PUBLIC_ENDPOINT_IN_SPEC", "SPEC_UNAVAILABLE"}
    assert not [m["method"] for m in d["methods"] if m["verdict"] not in ok]
    okr = [m for m in d["methods"] if m["verdict"] == "ENDPOINT_OK"]
    assert all(isinstance(m["status"], int) and 200 <= m["status"] < 300 for m in okr)
    print("ENDPOINT-CENSUS OK  282/282  " + json.dumps(d["total"], ensure_ascii=False))


if __name__ == "__main__":
    (check() if "--check" in sys.argv else run())

