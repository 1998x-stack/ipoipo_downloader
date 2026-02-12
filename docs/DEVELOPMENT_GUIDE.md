# IPO IPO Downloader - Development Guide

Welcome to the development guide for the IPO IPO Downloader. This document covers the architecture, code structure, and contribution guidelines.

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Module Details](#module-details)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Style](#code-style)
- [Troubleshooting](#troubleshooting)

## Architecture Overview

The application follows a modular architecture with clear separation of concerns:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Scraper       │────│   Downloader    │────│   Model/DB      │
│   Module        │    │   Module        │    │   Module        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   HTTP Client   │    │   File Manager  │    │   Database      │
│   & Proxy       │    │   Operations    │    │   Operations    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                        ┌─────────────────┐
                        │   Main App      │
                        │   Orchestrator  │
                        └─────────────────┘
```

### Key Components

1. **Scraper Module**: Handles web scraping for categories, reports, and download links
2. **Downloader Module**: Manages file downloads with resume capability
3. **Model Module**: Contains database operations and HTTP client
4. **Utils Module**: Provides logging and helper functions
5. **Config Module**: Centralizes all configuration settings

## Module Details

### Scraper Module (`src/scraper/`)

#### Category Scraper
- Discovers all available report categories
- Updates database with category information
- Handles pagination for category listings

#### List Scraper  
- Scrapes individual report titles and URLs
- Extracts report metadata
- Tracks progress in database

#### Download Scraper
- Extracts actual download URLs from protected links
- Handles anti-hotlinking mechanisms
- Updates download status in database

### Downloader Module (`src/downloader/`)

#### Downloader Class
- Manages download queue and progress
- Implements resumable downloads
- Handles proxy rotation on failures
- Provides progress reporting

#### File Manager Class
- Organizes files by category and report
- Handles archive extraction
- Manages file naming and deduplication

### Model Module (`src/model/`)

#### HTTP Client
- Maintains sessions with proper headers
- Implements retry logic
- Handles proxy configuration
- Manages cookies and referers

#### Proxy Manager
- Reads Clash configuration
- Tests proxy nodes for connectivity
- Selects fastest/working nodes
- Rotates nodes on failures

#### Database
- SQLite-backed persistence
- Tracks categories, reports, downloads
- Manages state transitions
- Provides statistics queries

## Development Workflow

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/ipoipo-downloader.git
cd ipoipo-downloader

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install in editable mode for development
pip install -e .
```

### Making Changes

1. Create a new branch for your feature/bug fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following the [Code Style](#code-style) guidelines

3. Test your changes thoroughly

4. Update documentation if necessary

5. Commit your changes with clear, descriptive messages

### Running the Application During Development

```bash
# Run specific stages for testing
python main.py --stage1  # Test category scraping
python main.py --stage2 --max-pages 1  # Test report scraping
python main.py --stage3 --limit 5  # Test download link extraction
python main.py --stage4 --max-reports 2  # Test downloading

# Run with debug logging
python main.py --full --max-pages 1 --max-reports 5
```

## Testing

### Unit Tests
Create unit tests in the `tests/` directory following the pattern:
```
tests/
├── test_scraper.py
├── test_downloader.py
├── test_model.py
└── test_utils.py
```

Run all tests:
```bash
pytest tests/
```

### Integration Tests
Test the full pipeline with small datasets:
```bash
python main.py --full --max-pages 1 --max-reports 5 --no-proxy
```

### Manual Testing Checklist
- [ ] Category scraping works correctly
- [ ] Report scraping handles pagination
- [ ] Download link extraction works
- [ ] Actual downloads complete successfully
- [ ] Resume functionality works
- [ ] Proxy rotation handles failures
- [ ] Error handling is robust
- [ ] Database updates correctly

## Code Style

### Python Style
- Follow PEP 8 guidelines
- Use 4 spaces for indentation
- Use descriptive variable and function names
- Keep functions focused on single responsibilities
- Add type hints where beneficial
- Document public methods with docstrings

### Import Organization
```python
# Standard library imports
import os
import sys
from pathlib import Path

# Third-party imports
import requests
from loguru import logger

# Local imports
from src.config.settings import BASE_URL
from src.utils.logger import get_logger
```

### Naming Conventions
- Classes: `PascalCase`
- Functions: `snake_case`
- Variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_private_snake_case`

### Example Class Structure
```python
class ExampleClass:
    """Brief description of the class."""
    
    def __init__(self, param1: str, param2: int = 0):
        """Initialize the class.
        
        Args:
            param1: Description of param1
            param2: Description of param2 (optional)
        """
        self.param1 = param1
        self.param2 = param2
    
    def example_method(self) -> bool:
        """Perform example operation.
        
        Returns:
            True if successful, False otherwise
        """
        # Implementation here
        return True
```

## Troubleshooting

### Common Development Issues

#### Import Errors
- Ensure `src` is in your Python path
- Verify all `__init__.py` files exist
- Check that imports use correct module paths

#### Database Issues
- Verify database schema matches expected structure
- Check permissions on database file
- Clear database if corrupted: `rm data/downloads.db`

#### Proxy Problems
- Confirm Clash is running and accessible
- Verify proxy configuration file format
- Test proxy connectivity independently

#### Anti-Hotlinking Bypass
- Ensure referer headers are properly set
- Check session management
- Verify cookies are maintained across requests

### Debugging Tips

1. **Enable verbose logging**:
   ```python
   logger.level("DEBUG")  # In your debugging code
   ```

2. **Use the stats command**:
   ```bash
   python main.py --stats  # Check current state
   ```

3. **Test with limited scope**:
   ```bash
   # Test with minimal data
   python main.py --stage2 --max-pages 1
   ```

4. **Check logs**:
   ```bash
   tail -f logs/error_*.log  # Monitor error logs
   ```

### Performance Considerations
- Be mindful of rate limiting
- Use appropriate delays between requests
- Monitor memory usage with large datasets
- Consider database indexing for large tables

## Contribution Guidelines

### Pull Request Process
1. Ensure your code follows the style guidelines
2. Add/update tests as needed
3. Update documentation if applicable
4. Verify all tests pass
5. Submit PR with clear description of changes

### Code Review Checklist
- [ ] Code follows established patterns
- [ ] Error handling is comprehensive
- [ ] Performance considerations addressed
- [ ] Security implications evaluated
- [ ] Documentation updated appropriately

### Versioning
- Follow semantic versioning (MAJOR.MINOR.PATCH)
- Update version in `pyproject.toml`
- Update changelog with notable changes

---