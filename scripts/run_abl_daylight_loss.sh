#!/usr/bin/env bash
# Daylight-only training ablation (group abl_daylight_loss): 2 runs, global, MC-Dropout,
# seeds 42 and 43, compared with final_s42 / final_s43. See outputs/ablation/ABLATION_PLAN.md.
#
# Runs as a 4th process next to the three abl_scope_dropout shards; the ledger write is
# file-locked, so the processes can finish in any order. It does not commit: commit once,
# after this and all three shards have finished (Section 6 of the plan).
#
#     bash scripts/run_abl_daylight_loss.sh
set -euo pipefail
cd "$(dirname "$0")/.."

uv run python scripts/run_all_experiments.py --group abl_daylight_loss --list
uv run python scripts/run_all_experiments.py --group abl_daylight_loss --skip-existing --continue-on-error
uv run python scripts/check_outputs.py --group abl_daylight_loss
