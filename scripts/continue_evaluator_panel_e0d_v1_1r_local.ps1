param([string]$Root = ".")

$ErrorActionPreference = "Stop"
$resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
Set-Location -LiteralPath $resolvedRoot

$runner = "scripts/run_evaluator_panel_external_calibration_e0d_v1_1.py"
$contract = "configs/evaluator_panel/external_calibration_e0d_v1_1r.json"
$ministralSummary = "data/evaluator_panel_v2/e0d_ministral_judge_execution.safe.json"
$gaScreen = "data/evaluator_panel_v2/e0d_v1_1r_ga_screen.safe.json"

function Invoke-E0DStep {
    param([string[]]$Arguments)
    & python $runner --root . --contract $contract @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "E0D step failed with exit code $LASTEXITCODE`: $($Arguments -join ' ')"
    }
}

if (Test-Path -LiteralPath $ministralSummary) {
    $ministral = Get-Content -Raw -LiteralPath $ministralSummary | ConvertFrom-Json
}
if (
    (-not (Test-Path -LiteralPath $ministralSummary)) -or
    $ministral.status -ne "E0D_CALIBRATION_JUDGE_EXECUTION_COMPLETE"
) {
    Write-Output "E0D_ORCHESTRATOR starting_or_resuming_ministral"
    Invoke-E0DStep -Arguments @(
        "run-judge",
        "--judge-id",
        "ministral_3_3b_instruct_2512_q4_k_m"
    )
}

Write-Output "E0D_ORCHESTRATOR starting_phi"
Invoke-E0DStep -Arguments @(
    "run-judge",
    "--judge-id",
    "phi_4_mini_instruct_q4_k_m"
)

Write-Output "E0D_ORCHESTRATOR starting_ga_screen"
Invoke-E0DStep -Arguments @("ga-screen")
$screen = Get-Content -Raw -LiteralPath $gaScreen | ConvertFrom-Json

if ($screen.wildguard_required -eq $true) {
    Write-Output "E0D_ORCHESTRATOR starting_wildguard"
    Invoke-E0DStep -Arguments @("run-wildguard")
    Write-Output "E0D_ORCHESTRATOR starting_finalize"
    Invoke-E0DStep -Arguments @("finalize")
    Write-Output "E0D_ORCHESTRATOR complete_with_finalization"
}
else {
    Write-Output "E0D_ORCHESTRATOR terminal_ga_fail_fast_no_heldout_opened"
}
