#!/usr/bin/env bash
# vaultlab bootstrap — Unix / bash
#
# Run once on a fresh machine before invoking any vaultlab slash command.
# Verifies the package is importable; installs from PyPI if not.
#
# Source: metabolism run 2026-05-05 friction-findings; harness-feedback doc at
# G:/My Drive/Knowledge/vaultlab/Sources/Notes/friction-findings-from-metabolism-run-2026-05-05.md
#
# Usage:
#   bash scripts/bootstrap.sh
#   bash scripts/bootstrap.sh --editable   # dev install from this checkout
#
# Exit codes:
#   0 — vaultlab importable + KB root configured (or first-run prompt warned)
#   1 — pip install failed
#   2 — Python not found
#   3 — KB-root resolver raised after install (genuine config gap)

set -euo pipefail

EDITABLE=0
for arg in "$@"; do
    case "$arg" in
        --editable|-e) EDITABLE=1 ;;
        *) ;;
    esac
done

step()  { printf '\033[36m→ %s\033[0m\n' "$1"; }
ok()    { printf '\033[32m✓ %s\033[0m\n' "$1"; }
warn()  { printf '\033[33m! %s\033[0m\n' "$1"; }

# ─────────────────────────────────────────────────────────────────
# 1. Python presence
# ─────────────────────────────────────────────────────────────────
step "Checking Python..."
if ! command -v python >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
    warn "Python not found. Install Python 3.10+ and re-run."
    exit 2
fi
PY=$(command -v python3 || command -v python)
ok "Python present: $($PY --version 2>&1)"

# ─────────────────────────────────────────────────────────────────
# 2. vaultlab importable?
# ─────────────────────────────────────────────────────────────────
step "Checking vaultlab importability..."
if VAULTLAB_VER=$($PY -c "import vaultlab; print(vaultlab.__version__)" 2>&1); then
    ok "vaultlab already installed: $VAULTLAB_VER"
else
    warn "vaultlab not importable. Installing..."
    REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
    if [ "$EDITABLE" -eq 1 ]; then
        step "Editable install from $REPO_ROOT"
        $PY -m pip install -e "$REPO_ROOT"
    else
        step "pip install vaultlab from PyPI"
        $PY -m pip install vaultlab
    fi
    VAULTLAB_VER=$($PY -c "import vaultlab; print(vaultlab.__version__)")
    ok "vaultlab installed: $VAULTLAB_VER"
fi

# ─────────────────────────────────────────────────────────────────
# 3. KB root resolution
# ─────────────────────────────────────────────────────────────────
step "Checking KB root configuration..."
KB_CHECK=$($PY -c "
from vaultlab.context import resolve_kb_root, KbRootNotConfigured
try:
    root = resolve_kb_root()
    print('OK', root)
except KbRootNotConfigured as exc:
    print('NEEDS_CONFIG', exc.suggested_default)
" 2>&1)

case "$KB_CHECK" in
    OK\ *)
        ROOT=${KB_CHECK#OK }
        ok "KB root configured: $ROOT"
        ;;
    NEEDS_CONFIG\ *)
        DEFAULT=${KB_CHECK#NEEDS_CONFIG }
        warn "KB root not yet configured."
        echo ""
        echo "  Next step: run 'vaultlab init' (default would be: $DEFAULT)"
        echo "  Or set VAULTLAB_KB_ROOT explicitly for this session."
        echo ""
        exit 3
        ;;
    *)
        warn "Unexpected resolver response: $KB_CHECK"
        exit 3
        ;;
esac

# ─────────────────────────────────────────────────────────────────
# 4. Wire vaultlab into Claude Code globally (slash commands + global CLAUDE.md)
# ─────────────────────────────────────────────────────────────────
step "Wiring vaultlab into Claude Code..."
if $PY -m vaultlab.cli claude-setup 2>/dev/null; then
    ok "Claude Code setup complete"
elif command -v vaultlab >/dev/null 2>&1; then
    vaultlab claude-setup
    ok "Claude Code setup complete"
else
    warn "Could not run 'vaultlab claude-setup' — slash commands may not be globally available."
    warn "Run manually:  vaultlab claude-setup"
fi

# ─────────────────────────────────────────────────────────────────
# 5. Done
# ─────────────────────────────────────────────────────────────────
echo ""
ok "Bootstrap complete. Next:"
echo "  • Open Claude Code in any project folder"
echo "  • /onboard-me     — natural-language project onboarding (recommended for first-time users)"
echo "  • /onboard-project — structured onboarding for an existing folder"
echo "  • /start-project  — quick topic-only scaffold"
echo "  • /lit-arc <topic> — once a project is onboarded"
echo ""
echo "Slash commands now available globally (~/.claude/commands/)."
echo "Global CLAUDE.md updated to point at READ_FIRST.md for dispatch routing."
echo ""
