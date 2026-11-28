"""Print the five Section 7 verdicts for a package, one line per question.

Deliberately prints `EXPORT_REFUSED` or `EXPORTABLE` and never "OK": the whole
point of Section 7.1 is that a reader should see which of the five questions was
answered, not one grey word that could hide four unasked ones.

  python tools/report_dimensions.py examples/demo.uibc
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import dimensions, verify  # noqa: E402

LABEL = {
    "signature": "签名（seal 在该读者的密钥下验过吗）",
    "authority": "权限（这个 actor 有权说这句话吗）",
    "binding": "绑定（就是包里写的那个 actor 吗）",
    "status": "现状（还是当前状态吗）",
    "evidence": "证据（字节还哈希得到承诺值吗）",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("package")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    res = verify.verify(a.package)
    dims = dimensions.record(res["checks"])
    verdict = dimensions.aggregate(dims)

    if a.json:
        print(json.dumps({"verdict": verdict, "dimensions": dims,
                          "checks": res["checks"]}, ensure_ascii=False, indent=2))
        return 0

    print("package:", a.package)
    for d in dimensions.ORDER:
        v = dims[d]
        print("%-10s %-14s %s" % (d, v["verdict"], v["why"]))
        print("           %s" % LABEL[d])
    if dims.get("_unassigned"):
        print("unassigned checks:", dims["_unassigned"]["why"])
    print()
    print("导出判定:", verdict)
    print("说明: 五项全部 CHECKED_PASS 才 EXPORTABLE；任一项 NOT_CHECKED 也算拒绝——"
          "没问过的问题不能当通过。")
    return 0 if verdict == "EXPORTABLE" else 1


if __name__ == "__main__":
    sys.exit(main())
