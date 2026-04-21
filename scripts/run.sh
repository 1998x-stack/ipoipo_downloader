#!/bin/bash
# Run full pipeline in background
nohup python main.py --full > logs/output.log 2>&1 &
echo "Started in background (PID: $!)"
echo "Logs: logs/output.log"
