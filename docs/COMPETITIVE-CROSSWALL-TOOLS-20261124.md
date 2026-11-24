# Where a crosswalk is done best, and the one cell they all leave empty

Status date: 2026-11-24. Scope: tools that map a regulatory or security text to
something machine-checkable. Four families were read; each is quoted from its own
documentation rather than summarised from memory.

## 1. Chef InSpec — the strongest executor, two states only

InSpec treats a control as a block with `impact`, `title`, `desc`, `ref`, `tag`
and one or more `describe` assertions, run against servers, containers and cloud
APIs. Two mechanics matter here:

- `inspec check` "verify the metadata ... and define that all controls have
  visible tests" - a control with no test does not survive the check.
- `only_applicable_if` marks a control N/A "if the results ... evaluates to
  false", and `--distinct-exit` exits 101 on failures, 100 when anything was
  skipped.

So InSpec has *has-a-test* and *not-applicable*. It has no state for "this clause
applies to the product, we cover part of it, and here is exactly which part". A
medical-device crosswalk needs that state for most rows: IEC 62304 process
requirements, ISO 14971 risk-management requirements and QMS document control are
all applicable and all partly outside a record layer.

Source: https://docs.chef.io/inspec/7.2/profiles/controls/ ,
https://docs.chef.io/inspec/cli/

## 2. NIST OSCAL + compliance-trestle — the strongest structure, no executor

OSCAL carries catalog, profile, component definition, SSP, assessment plan,
assessment results, POA&M and (in recent versions) a mapping model, in JSON/YAML/XML.
Trestle manages those documents in git, validates schemas, splits and assembles
them, and provides detached signing and verification for JSON artifacts.

What it does not do: run anything. Trestle "passes the generated artifacts onto
tools that orchestrate the enforcement, measurement, and reporting" - in practice
Auditree or a human reviewer. The structure is excellent; the verdict is
somebody else's job.

Source: https://github.com/oscal-compass/compliance-trestle

## 3. Medical-device traceability vendors — a human in the loop, by design

Ketryx assembles GSPR traceability and the technical file from Jira, Git and test
tools; Matrix Req's Compliance Checker imports a standard held as PDF, turns it
into a checklist and "evaluates each requirement against your actual project
evidence", with every result going "through your review before anything is
documented"; Greenlight Guru keeps design controls beside its own QMS. The
regulatory reading is right: Annex II 4(d) asks for "the precise identity of the
controlled documents offering evidence of conformity" with a cross-reference to
where the evidence sits. These tools answer that with linked, versioned documents.

The cell they leave empty: the result is a reviewed artifact, not a verdict that
re-runs. Change one byte of evidence and nothing turns red until a person looks.

Source: https://matrixone.health/blog/best-eu-mdr-technical-documentation-software

## 4. Our own prior art, and why it did not cover this

`tools/aer1_crosswalk.py` already uses three states - COVERED, TO-ADD, N_A - for
the AER-1 corpus. Its docstring is explicit: "the mapping is authored - the script
never guesses". That is the right honesty for a hand mapping, and it also means
no row can be contradicted by a machine.

## Correction, 2026-11-25: the empty cell was not empty

The first version of this note said no tool carried a declared-gap state whose
verdict came from real tool output. **That was wrong.** A fifth family does:

**PayloadGuard Evidence** (`payloadguard-evidence`, GitHub). Its own description:
each requirement is bound to "a specific run of a specific verification tool,
with the tool's verbatim output committed alongside the claim"; strength "is
derived only from what a verification tool actually reported in a real, recorded
run"; the vocabulary is PROVEN / BOUNDED_CHECKED / TESTED / EXAMPLE_CHECKED /
DECLARED / GAP; and generation "fails rather than emit a PROVEN label not backed
by a real, completed proof". It carries an ISO 14971 risk-management plan and
hazard register per example, and runs the same engine, unmodified, against NHTSA
FMVSS No. 127 - so it is the cross-domain example as well.

The state is therefore not ours, and saying so is more useful than the earlier
claim was. What is actually different:

| | PayloadGuard Evidence | this repo |
|---|---|---|
| what is mapped | software requirements | regulatory clauses |
| question answered | is this requirement established, and how strongly | what part of this clause can this package carry at all |
| source handling | verbatim archive per source; numeric-constant citation gate | a `verbatim` flag per clause: text not read -> never carried |
| how a domain is added | per-example specs and sources | crosswalk files are data; no engine change |
| object of the verdict | a proof or test run | a package's identity, seal, state and revocation |

Read plainly: they map evidence to requirements, we map clauses to carrying
capacity. Neither replaces the other, and "we are ahead" is not available to
either side. The one rule this repo adds that they do not state is the
`verbatim` gate below - and that is a narrow rule, not a moat.

Source: https://github.com/PayloadGuard-PLG/payloadguard-evidence

## The states, as this repo runs them

`tools/crosswalk_probe.py` decides a clause from three inputs - what was
claimed, what the reason says, what the probe did:

| State | Meaning | Effect on exit code |
|---|---|---|
| COVERED | strength=carried, clause text quoted verbatim, declared probe passed | - |
| PARTIAL | strength=partial, reason states what is missing | - |
| GAP | strength=gap, reason states why this layer cannot carry it | - |
| OVERCLAIM | strength=carried but no probe, a failing probe, or no verbatim quote | 1 |
| UNDECLARED | partial or gap with an empty reason | 1 |
| UNRUN | `--no-probe`; carried clauses were not executed | - |

A declared gap stays green and is counted. That is deliberate: in a
medical-device crosswalk, process and organisational requirements legitimately
outnumber record-layer ones, so a tool that reddens on every gap would be turned
off within a week. A claim that cannot be demonstrated turns the run red - that is
the only reason the other two states mean anything.

The `verbatim` gate is the narrow addition: a row whose clause text was never
read (a paid standard quoted only by clause title, or a summary quoted instead of
the standard) may be PARTIAL or GAP, never carried. It is one boolean, not a
mechanism, and PayloadGuard's per-source verbatim archive is the stronger version
of the same instinct.

Four crosswalks ship:

- `crosswalk/eu-mdr-2017-745.json` - Annex I 17.1, 17.2, 17.4, 18.8 and Annex II
  4(d), text quoted verbatim from EUR-Lex. Four partial, one gap, no carried row.
- `crosswalk/iec-62304-2006-a1.json` - five clauses, **titles only** (the standard
  is CHF 1,150 and the full text is not public): three partial, two gaps.
- `crosswalk/iso-14971-2019.json` - five clauses, **titles only**: two partial,
  three gaps.
- `crosswalk/tool-contract.json` - the tool's own contract, three carried rows
  with real probes plus one gap, kept separate so a regulatory crosswalk is not
  padded with self-tests.

Twelve medical-device clauses mapped, **zero carried**. That is the finding, and
two tests pin it: promoting a row to carried without a verbatim quote, or without
a passing probe, turns the run red.

The manifest digest over the clause set is the identity of the mapping: change a
quoted clause, a strength or a reason and it changes; change only a probe's
runtime and it does not. That is the same shape Annex II 4(d) asks for when it
demands a precise identity for each piece of evidence.
