# vaultlab bootstrap — Windows / PowerShell
#
# Run once on a fresh machine before invoking any vaultlab slash command.
# Verifies the package is importable; installs from PyPI if not.
#
# Source: metabolism run 2026-05-05 friction-findings; harness-feedback doc at
# G:/My Drive/Knowledge/vaultlab/Sources/Notes/friction-findings-from-metabolism-run-2026-05-05.md
#
# Usage:
#   pwsh scripts/bootstrap.ps1
#   pwsh scripts/bootstrap.ps1 -Editable    # dev install from this checkout
#
# Exit codes:
#   0 — vaultlab importable + KB root configured (or first-run prompt warned)
#   1 — pip install failed
#   2 — Python not found
#   3 — KB-root resolver raised after install (genuine config gap)

[CmdletBinding()]
param(
    [switch]$Editable
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "→ $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "✓ $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "! $msg" -ForegroundColor Yellow }

# ─────────────────────────────────────────────────────────────────
# 1. Python presence
# ─────────────────────────────────────────────────────────────────
Write-Step "Checking Python..."
try {
    $pyver = & python --version 2>&1
} catch {
    Write-Warn2 "Python not found on PATH. Install from https://www.python.org/ (3.10+) and re-run."
    exit 2
}
Write-Ok "Python present: $pyver"

# ─────────────────────────────────────────────────────────────────
# 2. vaultlab importable?
# ─────────────────────────────────────────────────────────────────
Write-Step "Checking vaultlab importability..."
$importCheck = & python -c "import vaultlab; print(vaultlab.__version__)" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Ok "vaultlab already installed: $importCheck"
} else {
    Write-Warn2 "vaultlab not importable. Installing..."
    if ($Editable) {
        $repoRoot = Split-Path -Parent $PSScriptRoot
        Write-Step "Editable install from $repoRoot"
        & python -m pip install -e $repoRoot
    } else {
        Write-Step "pip install vaultlab from PyPI"
        & python -m pip install vaultlab
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Warn2 "pip install failed. See error above."
        exit 1
    }
    $importCheck = & python -c "import vaultlab; print(vaultlab.__version__)" 2>&1
    Write-Ok "vaultlab installed: $importCheck"
}

# ─────────────────────────────────────────────────────────────────
# 3. KB root resolution
# ─────────────────────────────────────────────────────────────────
Write-Step "Checking KB root configuration..."
$kbcheck = & python -c @"
from vaultlab.context import resolve_kb_root, KbRootNotConfigured
try:
    root = resolve_kb_root()
    print('OK', root)
except KbRootNotConfigured as exc:
    print('NEEDS_CONFIG', exc.suggested_default)
"@ 2>&1

if ($kbcheck -like "OK*") {
    $root = $kbcheck -replace "^OK ", ""
    Write-Ok "KB root configured: $root"
} elseif ($kbcheck -like "NEEDS_CONFIG*") {
    $default = $kbcheck -replace "^NEEDS_CONFIG ", ""
    Write-Warn2 "KB root not yet configured."
    Write-Host ""
    Write-Host "  Next step: run 'vaultlab init' (default would be: $default)" -ForegroundColor White
    Write-Host "  Or set `$env:VAULTLAB_KB_ROOT explicitly for this session." -ForegroundColor White
    Write-Host ""
    exit 3
} else {
    Write-Warn2 "Unexpected resolver response: $kbcheck"
    exit 3
}

# ─────────────────────────────────────────────────────────────────
# 4. Done
# ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Ok "Bootstrap complete. Next:"
Write-Host "  • /onboard-me     — natural-language project onboarding (recommended for first-time users)"
Write-Host "  • /onboard-project — structured onboarding for an existing folder"
Write-Host "  • /start-project  — quick topic-only scaffold"
Write-Host "  • /lit-arc <topic> — once a project is onboarded"
Write-Host ""
