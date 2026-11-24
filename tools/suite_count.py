# -*- coding: utf-8 -*-
"""测试套件规模：**静态计数**，跨平台一致。

为什么不用 `unittest.TestLoader().discover(...).countTestCases()`：
那个数是**跑在哪个平台就得哪个数**。2026-11-24 同一提交实测 Linux 1157、Windows 1156，
于是 `docs/EVIDENCE-INDEX.md` 里写死的那一个数字在另一个平台上必然"过期"，
`check_doc_facts` 与 `test_the_doc_in_the_repo_matches_a_fresh_build` 就报假失败——
外部实测台（uibc-bench 的 D1 组）第一次在 Linux 上跑就撞上了这条。

静态计数只做一件事：数 `tests/` 下 `def test_*`（含 async）的函数个数。
它不 import 任何模块，因此不受平台、可选依赖、跳过装饰器影响。
"""
import ast
import os

TESTS_DIR = "tests"


def count_test_functions(repo_root):
    """返回 tests/ 下 def test_* 的函数总数（递归，跳过 __pycache__）。"""
    base = os.path.join(repo_root, TESTS_DIR)
    total = 0
    for dirpath, dirnames, names in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in names:
            if not (name.startswith("test_") and name.endswith(".py")):
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=path)
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and node.name.startswith("test_"):
                    total += 1
    return total
