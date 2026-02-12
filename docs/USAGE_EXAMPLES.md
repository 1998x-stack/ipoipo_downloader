# Usage Examples

Here are detailed usage examples for the IPO IPO Downloader.

## Basic Usage

### Full Pipeline Execution
```bash
# Run the complete pipeline with limited scope (recommended first run)
python main.py --full --max-pages 2 --max-reports 10

# Run with higher limits for full dataset
python main.py --full --max-pages 10 --max-reports 100
```

### Stage-by-Stage Execution
```bash
# Stage 1: Scrape all categories
python main.py --stage1

# Stage 2: Scrape reports (first 5 pages of each category)
python main.py --stage2 --max-pages 5

# Stage 3: Extract download URLs (first 100 pending reports)
python main.py --stage3 --limit 100

# Stage 4: Download reports (up to 20 with concurrency)
python main.py --stage4 --max-reports 20 --concurrent
```

## Proxy Configuration

### Using Proxy (Default)
```bash
# With Clash configuration at config/clash_config.yaml
python main.py --full --max-pages 2 --max-reports 10
```

### Without Proxy
```bash
# Skip proxy usage
python main.py --full --no-proxy --max-pages 2 --max-reports 10
```

## Targeted Downloads

### Specific Categories
```bash
# Download from specific categories only
python main.py --stage2 --categories 34 85 --max-pages 5  # IDs: Economic Reports, AI
python main.py --stage3 --limit 100
python main.py --stage4 --max-reports 20
```

### Single Category
```bash
# Focus on economic reports (ID: 34)
python main.py --stage4 --category 34 --max-reports 10
```

## Advanced Options

### Concurrent Downloads
```bash
# Enable parallel downloading
python main.py --stage4 --concurrent --max-reports 30
```

### Force Re-download
```bash
# Re-download files that already exist
python main.py --stage4 --max-reports 10 --force
```

### Retry Failed Downloads
```bash
# Retry previously failed downloads
python main.py --retry --max-reports 20
```

### Extract Archives
```bash
# Extract all downloaded ZIP files
python main.py --extract

# Extract from specific category
python main.py --extract --category 34 --max-reports 50
```

## Monitoring and Statistics

### View Current Stats
```bash
# Show download statistics
python main.py --stats
```

### Monitor Logs
```bash
# Follow application logs
tail -f logs/app_*.log

# Follow error logs
tail -f logs/error_*.log
```

## Error Handling

### Handle Interrupted Downloads
```bash
# If interrupted, simply run again - it will resume
python main.py --stage4 --max-reports 100
```

### Proxy Node Failures
The system automatically rotates proxy nodes when failures occur. No manual intervention needed.

### Network Issues
Automatic retry mechanisms handle temporary network issues. Configure retry settings in `src/config/settings.py`.

## Performance Optimization

### Increase Concurrent Downloads
Modify `MAX_CONCURRENT_DOWNLOADS` in `src/config/settings.py` to increase parallelism (careful not to overload).

### Adjust Rate Limits
Modify `REQUEST_DELAY` in `src/config/settings.py` to change the delay between requests.

## Configuration

### Settings Location
Configuration is stored in `src/config/settings.py`:
- `USE_PROXY`: Enable/disable proxy usage
- `MAX_CONCURRENT_DOWNLOADS`: Number of simultaneous downloads
- `REQUEST_DELAY`: Range for random delays between requests
- `DOWNLOAD_DIR`: Destination for downloaded files

### Available Categories
Full list in `src/config/settings.py` under `CATEGORY_NAMES` mapping.

## Tips for Success

1. **Start Small**: Begin with `--max-pages 1 --max-reports 5` to test functionality
2. **Monitor Resources**: Watch disk space and network usage during large downloads
3. **Proxy Health**: Ensure proxy configuration is valid and nodes are responsive
4. **Rate Limits**: Respect delays to avoid being blocked by the target site
5. **Resume Capability**: Downloads can be safely interrupted and resumed
6. **Regular Cleanup**: Periodically check logs and clean old log files

## Troubleshooting

### Common Issues
- **403 Forbidden**: Usually resolved by proxy configuration or referer handling
- **Connection Timeouts**: May indicate proxy issues or network problems
- **Database Locks**: Generally resolve automatically; restart if persistent
- **Slow Downloads**: Try reducing concurrent downloads or switching proxy nodes

### Debug Mode
Add debug logging by modifying the logger level in individual modules during development.