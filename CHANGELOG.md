# Changelog

All notable changes to IPO IPO Downloader will be documented in this file.

## [Unreleased]

### Added
- Project reorganization with standardized directory structure
- Comprehensive documentation and usage guides
- Development and contribution guidelines

### Changed
- Moved all source code to `src/` directory
- Restructured modules by functionality (scraper, downloader, model, utils, config)
- Updated import paths to reflect new structure
- Enhanced README with modern formatting and comprehensive information

## [1.0.0] - 2024-02-12

### Added
- Initial release of IPO IPO Downloader
- Automated scraping of IPO research reports
- Proxy support with automatic node selection
- Resumable downloads with intelligent deduplication
- SQLite database for state management
- Anti-detection measures (fake headers, random delays)
- Auto-extraction of downloaded archives
- Multi-stage processing pipeline

### Features
- Complete web scraping pipeline from category discovery to file download
- Proxy management with Clash configuration support
- Resumable downloads with checkpoint capability
- Smart deduplication to avoid re-downloading
- Structured file organization by category
- Real-time progress tracking
- Concurrent download support
- Anti-bot evasion techniques

### Architecture
- Modular design with separation of concerns
- Database-driven state management
- Configurable settings system
- Comprehensive logging
- Error handling and retry mechanisms