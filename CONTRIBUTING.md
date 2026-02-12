# Contributing to IPO IPO Downloader

We welcome contributions to the IPO IPO Downloader project! This document outlines the process for contributing code, reporting issues, and suggesting enhancements.

## Table of Contents
- [Getting Started](#getting-started)
- [Code of Conduct](#code-of-conduct)
- [Reporting Issues](#reporting-issues)
- [Feature Requests](#feature-requests)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)
- [Documentation](#documentation)

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a branch for your changes
4. Make your changes
5. Push your changes to your fork
6. Submit a pull request

## Code of Conduct

This project adheres to the Python Community Code of Conduct. By participating, you are expected to uphold this code.

## Reporting Issues

When reporting issues, please include:

- A clear title and description
- Steps to reproduce the problem
- Expected vs. actual behavior
- Your environment (OS, Python version, etc.)
- Any relevant logs or error messages

## Feature Requests

We welcome feature requests! When suggesting a new feature:

- Explain the problem the feature solves
- Describe the proposed solution
- Consider potential alternatives
- Note any compatibility concerns

## Development Setup

### Prerequisites
- Python 3.8+
- pip package manager

### Setup Instructions
```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/ipoipo_downloader.git
cd ipoipo_downloader

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

## Coding Standards

### Python Style
- Follow PEP 8 guidelines
- Use 4 spaces for indentation (no tabs)
- Maximum line length of 100 characters
- Descriptive variable and function names
- Type hints for function parameters and returns

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
- Functions and variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private attributes/methods: `_leading_underscore`

### Documentation
- Include docstrings for all public methods/classes
- Use Google-style docstrings
- Document complex algorithms or non-obvious code

## Pull Request Process

1. Ensure your code follows the standards outlined above
2. Add tests for new functionality (if applicable)
3. Update documentation as needed
4. Verify all tests pass
5. Submit your pull request with a clear description
6. Address any review comments

### PR Template Checklist
- [ ] Code follows established patterns and style
- [ ] Changes are documented (README, docstrings, etc.)
- [ ] Tests pass (run `python -m pytest tests/`)
- [ ] New functionality includes tests
- [ ] README updated if necessary

## Testing

### Running Tests
```bash
# Run all tests
python -m pytest tests/

# Run with verbose output
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_specific_file.py
```

### Writing Tests
- Place tests in the `tests/` directory
- Name test files as `test_*.py`
- Use descriptive test function names
- Follow pytest conventions

## Documentation

### README Updates
- Update the README when adding new features
- Include usage examples for new functionality
- Keep the project overview current

### Inline Documentation
- Add docstrings to all public functions/classes
- Comment complex algorithms
- Update type hints as needed

## Repository Structure

```
ipoipo_downloader/
├── src/                    # Source code
│   ├── api/                # API interfaces
│   ├── config/             # Configuration modules
│   ├── downloader/         # Download functionality
│   ├── model/              # Data models and database
│   ├── scraper/            # Web scraping logic
│   └── utils/              # Utility functions
├── data/                   # Runtime data and database
├── docs/                   # Documentation
├── logs/                   # Log files
├── tests/                  # Test suite
├── main.py                 # Entry point
├── README.md               # Main documentation
├── CONTRIBUTING.md         # This file
└── requirements.txt        # Dependencies
```

## Questions?

If you have questions about contributing, feel free to open an issue with the "question" label.

Thank you for contributing to IPO IPO Downloader!