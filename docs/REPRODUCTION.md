# Reproduction: from a public URL to a green suite, on a machine we did not author on

The claim this document supports is narrow: **a third party can get from one public URL to the same numbers we publish, without credentials, using only what the repository makes public.** It does not claim an outside organisation has done it.

## What was run

Machine: a Linux cloud host that is not the machine the change was authored on (authoring host: Windows). Date: 2026-11-24, same day as the probe in `COMPETITIVE-LANDSCAPE.md`. No GitHub token, no AtomGit account, no private network path.

```
curl -sSL -o main.tar.gz https://codeload.github.com/zhaoxinghua09-cell/uibc-core/tar.gz/refs/heads/main
tar xzf main.tar.gz -C tree --strip-components=1     # 2,568,257 bytes, 1,865 files
python3 -m venv venv                                  # Python 3.12.11
./venv/bin/pip install -e 'tree[verify]'
./venv/bin/pip install pytest
PYTHONPATH=tree ./venv/bin/python tree/tools/check_doc_facts.py
cd tree && PYTHONPATH=. ../venv/bin/python -m pytest tests -q
./venv/bin/python tree/tools/probe_reference_repos.py
```

## Observed

| Step | Result |
|---|---|
| Public tarball | 200, 2,568,257 bytes, 1,865 files |
| `check_doc_facts.py` | `measured {'tests': 1173, 'checks': 20, 'modules': 35, 'attacks': 37, ...}`, `all published numbers match`, **0 mismatch** |
| `pytest tests` | **1471 passed, 33 skipped, 105 subtests passed** in 426.73 s |
| `probe_reference_repos.py` | `ACPs-community` main → 0 files; the other eight → README.md only |

Two numbers that look inconsistent and are not: **1,173** is the count of test functions recorded in `docs/EVIDENCE-INDEX.md`; **1,471** is what pytest executes after parametrisation and subtests. Reporting either one as "the number of tests" without saying which is which is the kind of ambiguity this repository keeps having to correct.

## Limits of this document

- Run by us, on a second machine and a different operating system. That removes "it only works on the author's machine"; it does not remove "the author is judging the author".
- The 33 skips are platform-conditional and were not investigated here; a skip is not a pass.
- Row 6 of the eight "best" criteria stays **partial** until someone outside this project repeats exactly these steps and publishes what they got.
