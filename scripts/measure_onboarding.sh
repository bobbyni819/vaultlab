#!/usr/bin/env bash
# Time the cold-start onboarding flow.
# Success criterion: vaultlab demo completes in <1800 s (30 min).
# Real-world target: <60s in CI.

set -euo pipefail

START_TS=$(date +%s)

echo "[onboarding] step 1: vaultlab --version"
vaultlab --version || (echo "[onboarding] FAILED: vaultlab not on PATH" && exit 1)

echo "[onboarding] step 2: vaultlab demo"
vaultlab demo --out-dir /tmp/vaultlab-onboarding-out

echo "[onboarding] step 3: verify artifact"
test -f /tmp/vaultlab-onboarding-out/deck.pptx || (echo "[onboarding] FAILED: deck.pptx missing" && exit 1)
test -f /tmp/vaultlab-onboarding-out/deck.pptx.provenance.json || (echo "[onboarding] FAILED: provenance sidecar missing" && exit 1)

END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))

echo "[onboarding] elapsed: ${ELAPSED}s"

if [ "$ELAPSED" -ge 1800 ]; then
  echo "[onboarding] FAILED: elapsed ${ELAPSED}s exceeds the 30-min bar"
  exit 1
fi

echo "[onboarding] PASSED — first artifact in ${ELAPSED}s (well under 30-min bar)"
