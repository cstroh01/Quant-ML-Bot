#!/usr/bin/env bash
# Spec 055 F02b: commit and push the ops-state checkout. Non-zero on any failure, so the runner
# never starts the broker command on state that is not durable. Usage: persist_state.sh DIR MESSAGE...
set -euo pipefail
cd "$1"
shift
git config user.name qmb-ops
git config user.email qmb-ops@users.noreply.github.com
git add -A
git diff --cached --quiet || git commit -q -m "ops state: $*"
git push -q origin HEAD:ops-state
