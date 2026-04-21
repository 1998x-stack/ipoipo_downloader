#!/bin/bash
# Quick stats from JSONL files
echo "=== ipoipo Downloader Stats ==="
echo ""
echo "Categories: $(wc -l < data/categories.jsonl 2>/dev/null || echo 0)"
echo "Reports (events): $(wc -l < data/reports.jsonl 2>/dev/null || echo 0)"
echo "Downloads (events): $(wc -l < data/downloads.jsonl 2>/dev/null || echo 0)"
echo ""
echo "Reports by status:"
python -c "
from storage import Storage
s = Storage('data')
stats = s.get_stats()
for status, count in sorted(stats['by_status'].items()):
    print(f'  {status}: {count}')
s.close()
"
echo ""
echo "Downloaded files: $(find data/downloads -type f ! -name '*.zip' 2>/dev/null | wc -l)"
