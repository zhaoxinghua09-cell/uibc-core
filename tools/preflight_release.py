"""Before you upload: does the artifact you are about to publish carry the checks you claim?

The comparison that matters is not "how many lines" but "feed the same package
to both and see what each reports". This builds the full-feature package and
runs the verifier that would be shipped -- the package directory alone, on an
import path that contains nothing else -- then reports which checks it emitted.

    python3 tools/preflight_release.py
    python3 tools/preflight_release.py --json

Exit 1 means the publishable artifact reports fewer checks than the tree
declares. That is not a warning to be read past: it is the exact distance
between a claim and a download.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_TOOLS = os.path.join(_REPO, "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

RUNNER = """
import json, sys
from uibc_core.verify import verify
pin = sys.argv[2] if len(sys.argv) > 2 else None
r = verify(sys.argv[1], expect_head=pin)
print(json.dumps({"result": r["result"],
                  "checks": sorted([c["id"] for c in r["checks"]],
                                   key=lambda x: int(x[1:]))}))
"""


def full_feature_package():
    """A package that exercises every check, built with the repository's own builder."""
    import outsider_audit as oa
    tmp = tempfile.mkdtemp(prefix="uibc-preflight-")
    pkg = oa._prepare(os.path.join(_REPO, "fixtures", "clean.uibc"), tmp)
    for fn in ("build_v11", "build_ext", "build_s16", "build_ckpt"):
        getattr(oa, fn)(pkg)
    return pkg, tmp


def run_isolated(package, import_dir, pin=None):
    """Run the verifier with only the package directory importable."""
    env = dict(os.environ)
    env["PYTHONPATH"] = import_dir
    env.pop("PYTHONHOME", None)
    argv = [sys.executable, "-c", RUNNER, package] + ([pin] if pin else [])
    out = subprocess.run(argv,
                         capture_output=True, text=True, env=env, timeout=120)
    if out.returncode != 0:
        raise RuntimeError((out.stderr or out.stdout)[-400:])
    return json.loads(out.stdout.strip().splitlines()[-1])


def build():
    import build_evidence_index as bei
    declared = sorted(bei.checks_declared(), key=lambda c: int(c[1:]))
    pkg, tmp = full_feature_package()
    stage = tempfile.mkdtemp(prefix="uibc-release-")
    try:
        # what a wheel contains: the package directory and nothing else
        shutil.copytree(os.path.join(_REPO, "uibc_core"),
                        os.path.join(stage, "uibc_core"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shipped = run_isolated(pkg, stage)
        # S9 only exists when someone supplies a value from outside, so the
        # artifact is also tried the way a holder of a pin would use it
        with open(os.path.join(pkg, "manifest.json"), encoding="utf-8") as f:
            pin = json.load(f).get("checkpoint_head")
        pinned = run_isolated(pkg, stage, pin) if pin else None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(stage, ignore_errors=True)
    seen = set(shipped["checks"])
    if pinned:
        seen |= set(pinned["checks"])
    missing = [c for c in declared if c not in seen and c != "S0"]
    return {
        "declared": declared,
        "shipped_reports": shipped["checks"],
        "shipped_verdict": shipped["result"],
        "pinned_run_checks": (pinned or {}).get("checks"),
        "missing_from_the_artifact": missing,
        "note": "the artifact is the package directory alone, which is what a "
                "wheel installs; S0 is the crash fallback and is not expected "
                "on a well-formed package",
    }


def render(r):
    lines = []
    lines.append("仓库声明 %d 项；安装后会报出 %d 项（判定 %s）。"
                 % (len(r["declared"]), len(r["shipped_reports"]),
                    r["shipped_verdict"]))
    lines.append("")
    lines.append("会报：%s" % ", ".join(r["shipped_reports"]))
    if r["pinned_run_checks"]:
        lines.append("给一个外部 pin 后再报：%s"
                     % ", ".join(sorted(set(r["pinned_run_checks"]) -
                                        set(r["shipped_reports"])) or ["（无新增）"]))
    if r["missing_from_the_artifact"]:
        lines.append("")
        lines.append("**不会报**：%s" % ", ".join(r["missing_from_the_artifact"]))
        lines.append("")
        lines.append("发布这样的包，等于发出一份不包含那些能力的声明。")
    else:
        lines.append("")
        lines.append("包与仓库一致，可以发布。")
    return "\n".join(lines) + "\n"


def main():
    r = build()
    if "--json" in sys.argv:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(render(r))
    return 1 if r["missing_from_the_artifact"] else 0


if __name__ == "__main__":
    sys.exit(main())
