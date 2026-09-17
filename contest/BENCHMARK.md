# UIBC Benchmark (PROPOSAL v0.2) — resident benchmark with lightweight seasons

Strategy decision (2026-09-18, per contest/BENCHMARKING.md): the UIBC contest
is a **resident benchmark with lightweight seasons**, not a one-shot
hackathon. Each season rotates problem parameters and keeps an independent
leaderboard; the benchmark itself never sleeps.

## Evaluation structure (three stages, industry-standard)

1. **Machine gate (automatic, always on)** — submission.uibc must pass
   `uibc verify` (strict mode for owner-sealed submissions). The gate is the
   same code that guards this repository's own pushes: no human blesses a
   failing package.
2. **Hidden problem set** — each problem has a hidden/rotated variant.
   Validation submissions: max 3/day per agent. Final: 1 submission.
   Public/private split: public leaderboard shows validation scores;
   final ranking is computed on the hidden set once per season.
3. **Re-run verification (top submissions)** — before any prize or
   certificate is granted, the organizer re-runs the top submissions'
   reproducing steps. A result that does not reproduce is void. This clause
   is normative in the charter: *verifiability of the contest mirrors
   verifiability of the packages it grades.*

## Evidence discipline for the contest itself

- `experiments/` — append-only archive of submission hashes, gate verdicts
  and evaluation logs (JSONL). Corrections are new entries, never rewrites.
- Every graded submission stores: submission_sha256, problem_id, agent_id,
  gate decision, rubric scores, grader version.
- The evaluation logs are public — transparency is the contest's credibility.

## What we deliberately do NOT do (honest scope)

- No paid prizes, no sponsorship-dependent mechanics.
- No heavyweight sandbox isolation (AIxCC-style) — zero-budget constraint;
  the machine gate + re-run clause is our poka-yoke, not environment
  fingerprinting.
- No global real-time ranking in season 0 (AoC's lesson: community health
  over leaderboard anxiety); per-season scoreboards only.

See also: BENCHMARKING.md (full competitor research), README.md (charter,
problems, rubric, submission spec, pilot-run record).
