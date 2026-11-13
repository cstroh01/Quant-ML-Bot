#!/usr/bin/env bash
# Spec 055 F02b: commit and push the ops-state checkout. Non-zero on any failure, so the runner
# never starts the broker command on state that is not durable. Usage: persist_state.sh DIR MESSAGE...
# Spec 057 D-12: the push is tried 3 times, waiting 5 s and then 15 s. Pushing the same commit again
# is a no-op, so a retry cannot duplicate state. Exit 3: the config, add or commit step failed.
# Exit 4: every push attempt failed.
set -euo pipefail
cd "$1"
shift
git config user.name qmb-ops || exit 3
git config user.email qmb-ops@users.noreply.github.com || exit 3
git add -A || exit 3
git diff --cached --quiet || git commit -q -m "ops state: $*" || exit 3
for wait in 0 5 15; do
  if [ "$wait" -gt 0 ]; then sleep "$wait"; fi
  if git push -q origin HEAD:ops-state; then exit 0; fi
done
exit 4
