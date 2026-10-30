#!/usr/bin/env bash
# No-province-code ablation (group abl_no_city_embedding): 2 runs, global, MC-Dropout,
# city_embedding_dim=0, seeds 42 and 43, compared with final_s42 / final_s43.
# See outputs/ablation/ABLATION_PLAN.md.
#
# Runs next to the abl_scope_dropout shards and abl_daylight_loss, or after them; the ledger
# write is file-locked, so the processes can finish in any order. It does not commit: commit
# once, after every ablation process has finished (Section 6 of the plan).
#
#     bash scripts/run_abl_no_city_embedding.sh
set -euo pipefail
cd "$(dirname "$0")/.."

uv run python scripts/run_all_experiments.py --group abl_no_city_embedding --list
uv run python scripts/run_all_experiments.py --group abl_no_city_embedding --skip-existing --continue-on-error
uv run python scripts/check_outputs.py --group abl_no_city_embedding
