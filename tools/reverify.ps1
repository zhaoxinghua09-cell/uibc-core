#!/usr/bin/env pwsh
# One command to re-check everything this repository claims.
#
# Why: every conclusion in this repo is supposed to be re-runnable, but "re-runnable"
# usually means "read the docs, find eight commands, run them in the right order".
# A claim nobody runs is not evidence. This script runs them in the right order and
# fails if any one of them fails.
#
#   ./tools/reverify.ps1                 # offline checks only, ~10 s
#   ./tools/reverify.ps1 -Network        # also take a fresh read-only reading of the platform
#
# Read-only: the offline path never writes. -Network rewrites docs/didcn-probe.json and
# docs/didcn-uniqueness.json, which is re-taking evidence, not changing conclusions.

param(
    [switch]$Network
)

$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"

$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $Repo

$steps = @(
    @{ Name = "platform record is self-consistent"; Cmd = "python tools/probe_didcn_platform.py --check" },
    @{ Name = "one code, one agent";                Cmd = "python tools/probe_didcn_platform.py --check-uniqueness" },
    @{ Name = "real runs vs the pinned snapshot";   Cmd = "python tools/parity_realrun.py --check" },
    @{ Name = "receipt vs this commit";             Cmd = "python tools/outsider_rerun.py --check" },
    @{ Name = "board vs the receipt";               Cmd = "python tools/render_outsider_board.py --check" },
    @{ Name = "evidence index";                     Cmd = "python tools/build_evidence_index.py --check" },
    @{ Name = "doc numbers vs the records";         Cmd = "python tools/check_doc_facts.py" },
    @{ Name = "AITB card is honest";                Cmd = "python tools/aitb_evaluate.py --check --report docs/aitb-example-report.json" },
    @{ Name = "AITB no-endpoint card is honest";    Cmd = "python tools/aitb_evaluate.py --check --report docs/aitb-example-no-endpoint.json" },
    @{ Name = "national methods census";            Cmd = "python tools/national_methods_snapshot.py --check" },
    @{ Name = "whole-registry census";              Cmd = "python tools/registry_census.py --check" }
)

if ($Network) {
    $steps = @(
        @{ Name = "fresh platform reading (11 probes)"; Cmd = "python tools/probe_didcn_platform.py --run" },
        @{ Name = "fresh one-code-one-agent reading";   Cmd = "python tools/probe_didcn_platform.py --uniqueness" }
    ) + $steps
}

$results = @()
foreach ($s in $steps) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $out = & cmd /c "$($s.Cmd) 2>&1"
    $code = $LASTEXITCODE
    $sw.Stop()
    $results += [pscustomobject]@{
        Step    = $s.Name
        Exit    = $code
        Sec     = [int]$sw.Elapsed.TotalSeconds
        Verdict = if ($code -eq 0) { "PASS" } else { "FAIL" }
        Last    = ($out | Select-Object -Last 1)
    }
}

$results | Format-Table -AutoSize Step, Verdict, Exit, Sec

$failed = @($results | Where-Object { $_.Verdict -eq "FAIL" })
if ($failed.Count -eq 0) {
    Write-Host ""
    Write-Host "All $($results.Count) checks passed. The records match this commit." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "$($failed.Count) failed: $($failed.Step -join ', ')" -ForegroundColor Red
    Write-Host "A failure is not a wrong conclusion: read the PROBLEM line it printed -- it says which observation no longer supports which sentence."
}

Pop-Location
if ($failed.Count -eq 0) { exit 0 } else { exit 1 }
