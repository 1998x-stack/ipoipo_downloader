<div align="center">
  <h1>IPO IPO Downloader 📈</h1>
  
  <p><b>Automated IPO Research Reports Downloader</b></p>
  <p>Intelligent scraper with proxy support, resumable downloads, and smart deduplication</p>
  
  ![Python](https://img.shields.io/badge/python-3.8%2B-blue)
  ![License](https://img.shields.io/badge/license-MIT-green)
  ![Status](https://img.shields.io/badge/status-active-success)
  
  <br>
  <br>
  <div>
    <img src="https://img.shields.io/badge/Anti--Bot_Evasion-Enabled-critical" alt="Anti-Bot Evasion" />
    <img src="https://img.shields.io/badge/Proxy_Support-Enabled-informational" alt="Proxy Support" />
    <img src="https://img.shields.io/badge/Resumable_Downloads-Enabled-success" alt="Resumable Downloads" />
    <img src="https://img.shields.io/badge/Smart_Caching-Enabled-yellow" alt="Smart Caching" />
  </div>
</div>

---

## 🚀 Features

| Feature | Description |
|--------|-------------|
| 🌐 **Proxy Support** | Automatic Clash proxy configuration with node selection |
| 🔄 **Resumable Downloads** | Continue interrupted downloads seamlessly |
| 🚫 **Smart Deduplication** | Skip already downloaded files automatically |
| 📊 **State Management** | SQLite database tracks download status |
| 🎭 **Anti-Detection** | Fake headers + random delays to avoid blocking |
| 📦 **Auto Extract** | ZIP files extracted automatically after download |
| 🗂️ **Structured Storage** | Organized by category and report name |
| 📈 **Progress Tracking** | Real-time download progress display |
| ⚡ **Concurrent Download** | Optional multi-threaded downloads |

## 📁 Project Structure

```
ipoipo_downloader/
├── src/                    # Source code
│   ├── api/                # API interfaces
│   ├── config/             # Configuration files
│   ├── downloader/         # Download management
│   ├── model/              # Data models & database
│   ├── scraper/            # Scraping logic
│   └── utils/              # Utility functions
├── data/                   # Downloaded reports & database
│   └── downloads/          # Organized by category
├── docs/                   # Documentation
├── logs/                   # Application logs
├── tests/                  # Test suite
├── config/                 # Legacy config (moved to src/config)
├── core/                   # Legacy core (moved to src/model)
├── download/               # Legacy download (moved to src/downloader)
├── scrapers/               # Legacy scrapers (moved to src/scraper)
├── utils/                  # Legacy utils (moved to src/utils)
├── main.py                 # Entry point
├── pyproject.toml          # Project metadata
└── requirements.txt        # Dependencies
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Pip package manager
- (Optional) Running Clash proxy for enhanced anonymity

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ipoipo-downloader.git
cd ipoipo-downloader

# Install dependencies
pip install -r requirements.txt

# Or install as a package
pip install .
```

### Configuration

#### 1. Proxy Configuration (Optional)
Place your Clash configuration in `src/config/clash_config.yaml` or skip this step to run without proxy.

#### 2. Custom Settings
Review and modify settings in `src/config/settings.py`.

### Usage

#### View Help
```bash
python main.py --help
```

#### Full Pipeline (Recommended for first run)
```bash
# Test run: 2 pages per category, max 10 reports
python main.py --full --max-pages 2 --max-reports 10

# Production run: All categories, more extensive scraping
python main.py --full --max-pages 10 --max-reports 100
```

#### Stage-by-Stage Execution
```bash
# Stage 1: Scrape all categories
python main.py --stage1

# Stage 2: Scrape report lists (first 5 pages per category)
python main.py --stage2 --max-pages 5

# Stage 3: Get download links for first 100 pending reports
python main.py --stage3 --limit 100

# Stage 4: Download reports (up to 20, with concurrency)
python main.py --stage4 --max-reports 20 --concurrent
```

#### Specific Category Downloads
```bash
# Download specific categories only (e.g., Economic Reports: 34, AI: 85)
python main.py --stage2 --categories 34 85 --max-pages 5
python main.py --stage3 --limit 100
python main.py --stage4 --max-reports 20

# Retry failed downloads
python main.py --retry --max-reports 10
```

#### Without Proxy
```bash
python main.py --full --no-proxy --max-pages 2 --max-reports 10
```

#### Extract Downloaded Archives
```bash
# Extract all ZIP files
python main.py --extract

# Extract from specific category
python main.py --extract --category 34 --max-reports 50
```

## 📊 Supported Categories

| ID | Category Name |
|----|---------------|
| 34 | Economic Reports |
| 85 | Artificial Intelligence & AI |
| 69 | New Energy & Power |
| 53 | Medical & Healthcare |
| 59 | Financial Industry |
| 70 | TMT Industry |
| 14 | Electronics Industry |
| 10 | Smart Manufacturing |

*See full list in `src/config/settings.py` under `CATEGORY_NAMES`*

## ⚙️ Configuration Options

### Core Settings (`src/config/settings.py`)
```python
# Proxy Configuration
USE_PROXY = True                    # Enable/disable proxy usage
PROXY_TEST_TIMEOUT = 3              # Proxy testing timeout (seconds)
MAX_CONCURRENT_DOWNLOADS = 3        # Maximum concurrent downloads

# Download Configuration
DOWNLOAD_DIR = "data/downloads"     # Download destination folder
CHUNK_SIZE = 8192                   # Download chunk size (bytes)
DOWNLOAD_TIMEOUT = 60               # Download timeout (seconds)

# Rate Limiting
REQUEST_DELAY = (1, 3)              # Random delay range between requests
MAX_RETRIES = 3                     # Maximum retry attempts
RETRY_DELAY = 1.5                   # Delay between retries (seconds)
```

## 📁 File Organization

Downloaded reports are organized by category:
```
data/downloads/
├── Economic Reports/
│   ├── China Local Public Data Report/
│   │   ├── 2025_China_Local_Public_Data_Report.zip
│   │   └── [extracted files]
│   └── Another Report/
├── Artificial Intelligence/
│   └── ...
└── Other Categories/
```

## 🗄️ Database Schema

The application uses SQLite to track state:

- `categories`: Category information (ID, name, URL)
- `reports`: Report details (title, URL, category, status)
- `downloads`: Download records (file path, size, timestamp)
- `extractions`: Archive extraction logs

Report Status Values:
- `pending`: Awaiting download link retrieval
- `ready`: Download link available
- `downloaded`: Successfully downloaded
- `failed`: Download attempt failed
- `no_download_url`: No download URL found

## 🔧 Advanced Features

### Resumable Downloads
Interrupted downloads automatically resume from where they left off:
```bash
python main.py --stage4 --max-reports 100  # Will skip completed downloads
```

### Force Redownload
```bash
python main.py --stage4 --max-reports 10 --force  # Re-download existing files
```

### Concurrent Downloads
```bash
python main.py --stage4 --concurrent  # Use multiple threads
```

### Statistics
```bash
python main.py --stats  # Display current download statistics
```

## 🛡️ Anti-Detection Measures

- **Fake Headers**: Browser-like headers prevent bot detection
- **Random Delays**: Natural-looking request timing
- **Session Management**: Proper cookie handling
- **Proxy Rotation**: Automatic node switching on failures
- **Referrer Handling**: Correct referer headers for anti-hotlinking

## 📈 Monitoring & Logging

Log files are maintained in the `logs/` directory:
- `app_YYYY-MM-DD.log`: General application logs
- `error_YYYY-MM-DD.log`: Error-specific logs

Monitor in real-time:
```bash
tail -f logs/app_*.log
tail -f logs/error_*.log
```

## 🐛 Troubleshooting

### Common Issues

#### Proxy Connection Failures
```bash
# Verify proxy configuration
ls src/config/clash_config.yaml

# Run without proxy
python main.py --full --no-proxy
```

#### Slow Downloads
```bash
# Enable concurrent downloads
python main.py --stage4 --concurrent

# Adjust concurrent download count in settings
```

#### Reports Failing to Download
```bash
# Check error logs
tail -f logs/error_*.log

# Retry failed downloads
python main.py --retry
```

#### Database Corruption
```bash
# Reset database (WARNING: Loses all progress)
rm data/downloads.db
python main.py --full
```

## 💡 Best Practices

1. **Start Small**: Begin with limited pages/reports for testing
2. **Monitor Logs**: Watch logs during initial runs
3. **Proxy Health**: Ensure Clash is running and nodes are responsive
4. **Disk Space**: Monitor available space during large downloads
5. **Rate Limits**: Respect delays to avoid being blocked
6. **Resume Capability**: Interrupted runs can be resumed safely

## 📋 Roadmap

- [ ] Web-based GUI interface
- [ ] Docker containerization
- [ ] Enhanced scheduling capabilities
- [ ] Notification system
- [ ] More download sources
- [ ] Improved error recovery

## 🤝 Contributing

Contributions are welcome! Please submit issues and pull requests.

### Development Setup
```bash
# Fork and clone your repository
git clone https://github.com/yourusername/ipoipo-downloader.git
cd ipoipo-downloader

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This tool is designed for educational and personal use only. Users are responsible for ensuring compliance with:
- Website terms of service
- Copyright laws
- Local regulations regarding data scraping
- Fair use principles

Use responsibly and ethically.

---

<div align="center">

**Made with ❤️ for financial research enthusiasts**

⭐ Star this repository if it helped you!

</div>