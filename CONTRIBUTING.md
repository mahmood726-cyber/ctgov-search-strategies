# Contributing to ClinicalTrials.gov Search Strategies

Welcome! Thank you for your interest in contributing to this project. This repository contains tools and utilities for building, validating, and optimizing search strategies for ClinicalTrials.gov. Your contributions help researchers conduct more effective systematic reviews and meta-analyses.

## How to Contribute

### 1. Fork the Repository

1. Navigate to the repository on GitHub
2. Click the "Fork" button in the top-right corner
3. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/ctgov-search-strategies.git
   cd ctgov-search-strategies
   ```

### 2. Create a Feature Branch

Always create a new branch for your work:

```bash
git checkout -b feature/your-feature-name
```

Use descriptive branch names:
- `feature/add-mesh-term-expansion`
- `fix/query-parsing-error`
- `docs/update-api-examples`

### 3. Make Your Changes

- Follow the code style guidelines below
- Write tests for new functionality
- Update documentation as needed

### 4. Run Tests

Before submitting, ensure all tests pass:

```bash
pytest
```

### 5. Submit a Pull Request

1. Push your branch to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
2. Open a pull request against the main repository
3. Provide a clear description of your changes
4. Link any related issues

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/YOUR-USERNAME/ctgov-search-strategies.git
   cd ctgov-search-strategies
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv

   # On Windows
   venv\Scripts\activate

   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

4. Verify the installation by running tests:
   ```bash
   pytest
   ```

## Code Style Guidelines

### General Principles

- **Follow PEP 8**: Use a linter like `flake8` or `ruff` to check compliance
- **Use type hints**: All function signatures should include type annotations
- **Keep functions focused**: Each function should do one thing well
- **Write readable code**: Prioritize clarity over cleverness

### Type Hints

```python
def build_query(terms: list[str], operator: str = "OR") -> str:
    """Build a search query from a list of terms."""
    ...
```

### Docstrings

Use Google-style docstrings for all public functions:

```python
def validate_search_strategy(query: str, api_key: str | None = None) -> dict:
    """Validate a ClinicalTrials.gov search strategy.

    Args:
        query: The search query string to validate.
        api_key: Optional API key for authenticated requests.

    Returns:
        A dictionary containing validation results with keys:
        - 'valid': Boolean indicating if the query is valid
        - 'errors': List of any syntax errors found
        - 'warnings': List of potential issues

    Raises:
        ValueError: If the query is empty.
        ConnectionError: If the API is unreachable.
    """
    ...
```

### Imports

Organize imports in the following order:
1. Standard library imports
2. Third-party imports
3. Local application imports

```python
import json
from pathlib import Path

import requests
from pydantic import BaseModel

from ctgov_search.parsers import QueryParser
```

## Testing Requirements

### Write Tests for New Features

- Every new feature should have corresponding tests
- Place tests in the `tests/` directory
- Follow the naming convention `test_<module_name>.py`

### Maintain Test Coverage

- Aim for at least 80% code coverage
- Run coverage reports:
  ```bash
  pytest --cov=ctgov_search --cov-report=html
  ```

### Mock External API Calls

Do not make real API calls in tests. Use mocking:

```python
from unittest.mock import patch, Mock

def test_search_query():
    mock_response = Mock()
    mock_response.json.return_value = {"studies": []}
    mock_response.status_code = 200

    with patch("requests.get", return_value=mock_response):
        result = search_clinicaltrials("diabetes")
        assert result == {"studies": []}
```

## Pull Request Checklist

Before submitting your pull request, ensure:

- [ ] All tests pass (`pytest`)
- [ ] Linting passes (`flake8` or `ruff check .`)
- [ ] Code is formatted (`black .` or `ruff format .`)
- [ ] Type checking passes (`mypy .`)
- [ ] Documentation is updated for any new features
- [ ] Docstrings are added for new functions
- [ ] Commit messages are clear and descriptive
- [ ] Branch is up to date with main

## Reporting Issues

### Bug Reports

When reporting a bug, please include:

1. **Description**: Clear summary of the issue
2. **Steps to reproduce**: Minimal code or steps to trigger the bug
3. **Expected behavior**: What you expected to happen
4. **Actual behavior**: What actually happened
5. **Environment**: Python version, OS, package version
6. **Error messages**: Full traceback if applicable

### Feature Requests

For new features, please describe:

1. **Use case**: Why is this feature needed?
2. **Proposed solution**: How should it work?
3. **Alternatives considered**: Other approaches you thought of
4. **Additional context**: Examples, mockups, or references

### Search Strategy Improvements

If you have suggestions for improving search strategies:

1. **Current strategy**: The existing approach
2. **Proposed improvement**: Your suggested changes
3. **Evidence**: Any validation data or references supporting the change
4. **Impact**: Expected effect on sensitivity/specificity

## Code of Conduct

We are committed to providing a welcoming and professional environment for all contributors.

### Expected Behavior

- Be respectful and considerate in all interactions
- Provide constructive feedback
- Accept constructive criticism gracefully
- Focus on what is best for the project and community

### Unacceptable Behavior

- Harassment, discrimination, or offensive comments
- Personal attacks or trolling
- Publishing others' private information
- Other conduct that would be inappropriate in a professional setting

### Enforcement

Violations of this code of conduct may result in temporary or permanent exclusion from the project. Report concerns to the project maintainers.

---

Thank you for contributing to better clinical trial search strategies!
