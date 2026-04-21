#!/bin/bash
# Run a single stage
# Usage: bash run_stage.sh <stage_number> [additional args]
STAGE=$1
shift
case $STAGE in
    1) python main.py --stage1 "$@" ;;
    2) python main.py --stage2 "$@" ;;
    3) python main.py --stage3 "$@" ;;
    4) python main.py --stage4 "$@" ;;
    *) echo "Usage: $0 <1|2|3|4> [args]"; exit 1 ;;
esac
