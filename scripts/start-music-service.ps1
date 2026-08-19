$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $projectRoot
$serviceRoot = Join-Path $workspaceRoot "ACE-Step-1.5"
$serviceExecutable = Join-Path $serviceRoot ".venv\Scripts\acestep-api.exe"
$checkpointRoot = Join-Path $serviceRoot "checkpoints"

if (-not (Test-Path -LiteralPath $serviceExecutable)) {
    throw "Local music service is not fully installed."
}

$listener = Get-NetTCPConnection -State Listen -LocalPort 8001 -ErrorAction SilentlyContinue
if ($listener) { return }

$env:ACESTEP_CONFIG_PATH = "acestep-v15-turbo"
$env:ACESTEP_DEVICE = "cuda"
$env:ACESTEP_INIT_LLM = "false"
$env:ACESTEP_LM_BACKEND = "pt"
$env:ACESTEP_CHECKPOINTS_DIR = $checkpointRoot
$env:ACESTEP_DOWNLOAD_SOURCE = "modelscope"
$env:ACESTEP_NO_INIT = "true"
$env:ACESTEP_OFFLOAD_TO_CPU = "true"
$env:ACESTEP_OFFLOAD_DIT_TO_CPU = "false"
$env:ACESTEP_USE_FLASH_ATTENTION = "false"
$env:ACESTEP_COMPILE_MODEL = "false"
$env:ACESTEP_QUANTIZATION = "int8_weight_only"
$env:ACESTEP_VAE_MIN_FREE_GB = "0"
$env:HF_HOME = Join-Path $workspaceRoot ".cache\huggingface"
$env:HUGGINGFACE_HUB_CACHE = Join-Path $env:HF_HOME "hub"
$env:MODELSCOPE_CACHE = Join-Path $workspaceRoot ".cache\modelscope"
$env:TEMP = Join-Path $workspaceRoot ".tmp"
$env:TMP = $env:TEMP

Start-Process -FilePath $serviceExecutable `
    -ArgumentList "--host", "127.0.0.1", "--port", "8001", "--download-source", "modelscope", "--no-init" `
    -WorkingDirectory $serviceRoot -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $workspaceRoot "ace-step-api.log") `
    -RedirectStandardError (Join-Path $workspaceRoot "ace-step-api-error.log")

$deadline = (Get-Date).AddSeconds(45)
do {
    Start-Sleep -Milliseconds 500
    $listener = Get-NetTCPConnection -State Listen -LocalPort 8001 -ErrorAction SilentlyContinue
} while (-not $listener -and (Get-Date) -lt $deadline)

if (-not $listener) { throw "Local music service startup timed out; check ace-step-api-error.log." }
