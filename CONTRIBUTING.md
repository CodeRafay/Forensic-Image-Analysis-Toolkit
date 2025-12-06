# Contributing to Veritas Forensic Image Analysis Toolkit

Thank you for considering contributing to Veritas! This document provides guidelines and instructions for contributing.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [Development Workflow](#development-workflow)
5. [Testing Guidelines](#testing-guidelines)
6. [Code Style](#code-style)
7. [Commit Messages](#commit-messages)
8. [Pull Request Process](#pull-request-process)
9. [Adding New Features](#adding-new-features)
10. [Reporting Bugs](#reporting-bugs)

---

## Code of Conduct

This project follows a standard code of conduct:

- **Be respectful**: Treat all contributors with respect
- **Be collaborative**: Work together to improve the project
- **Be open**: Accept constructive feedback
- **Be professional**: Keep discussions focused and productive

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- GitHub account

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork:

   ```bash
   git clone https://github.com/YOUR_USERNAME/Forensic-Image-Analysis-Toolkit.git
   cd Forensic-Image-Analysis-Toolkit
   ```

3. Add upstream remote:
   ```bash
   git remote add upstream https://github.com/CodeRafay/Forensic-Image-Analysis-Toolkit.git
   ```

---

## Development Setup

### 1. Create Virtual Environment

```bash
python -m venv venv

# Activate
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
# Production dependencies
pip install -r requirements.txt

# Development dependencies
pip install -r requirements-dev.txt
```

### 3. Install Pre-commit Hooks

```bash
pre-commit install
```

This ensures code quality checks run automatically before each commit.

---

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

Branch naming conventions:

- `feature/` - New features
- `bugfix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Adding tests

### 2. Make Changes

- Write clean, readable code
- Follow existing code style
- Add comments for complex logic
- Update documentation as needed

### 3. Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_ela.py

# Run with coverage
pytest --cov=analysis

# Run integration tests only
pytest -m integration
```

### 4. Format Code

```bash
# Auto-format with black
black .

# Sort imports
isort .

# Check with flake8
flake8 analysis/ tests/
```

### 5. Commit Changes

```bash
git add .
git commit -m "feat: add new forensic technique"
```

See [Commit Messages](#commit-messages) for guidelines.

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

---

## Testing Guidelines

### Writing Tests

- Place tests in `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use descriptive test names

**Example**:

```python
def test_ela_detects_manipulated_region():
    """Test that ELA highlights edited areas"""
    # Arrange
    img_path = create_test_image_with_edit()

    # Act
    result = perform_ela(img_path)

    # Assert
    assert result['metrics']['mean_error'] > threshold
```

### Test Categories

Mark tests with pytest markers:

```python
@pytest.mark.slow
def test_large_image_processing():
    pass

@pytest.mark.integration
def test_full_workflow():
    pass
```

Run specific categories:

```bash
pytest -m "not slow"  # Skip slow tests
pytest -m integration  # Run only integration tests
```

### Coverage Requirements

- Minimum 70% code coverage
- All new features must include tests
- Critical functions should have >90% coverage

---

## Code Style

### Python Style Guide

Follow **PEP 8** with these specifics:

- **Line length**: 100 characters
- **Indentation**: 4 spaces
- **Quotes**: Single quotes for strings (unless avoiding escapes)
- **Naming**:
  - Functions: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`

### Docstrings

Use Google-style docstrings:

```python
def analyze_image(image_path: str, threshold: float = 0.5) -> dict:
    """
    Perform forensic analysis on an image.

    Args:
        image_path (str): Path to the image file
        threshold (float): Detection threshold (0.0-1.0)

    Returns:
        dict: Analysis results containing:
            - detected (bool): Whether forgery detected
            - confidence (float): Confidence score
            - regions (list): List of suspicious regions

    Raises:
        FileNotFoundError: If image file doesn't exist
        ValueError: If threshold out of range

    Example:
        >>> result = analyze_image("photo.jpg", threshold=0.7)
        >>> print(result['confidence'])
        0.85
    """
    pass
```

### Type Hints

Use type hints for function signatures:

```python
from typing import List, Tuple, Optional

def process_images(
    paths: List[str],
    quality: int = 90
) -> Tuple[List[str], Optional[str]]:
    pass
```

---

## Commit Messages

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples

```
feat(ela): add multi-quality comparison mode

Implement multi_quality_ela() function to analyze images at
multiple compression levels simultaneously. This helps detect
forgeries that may only be visible at specific quality settings.

Closes #42
```

```
fix(metadata): handle images without EXIF data

Previously crashed when processing images without EXIF metadata.
Now returns empty dict with appropriate warning message.

Fixes #58
```

---

## Pull Request Process

### Before Submitting

- [ ] All tests pass (`pytest`)
- [ ] Code coverage >70% (`pytest --cov`)
- [ ] Code formatted (`black .`)
- [ ] Imports sorted (`isort .`)
- [ ] No linting errors (`flake8`)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if applicable)

### PR Description Template

```markdown
## Description

Brief description of changes

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring

## Testing

How was this tested?

## Screenshots (if applicable)

Add screenshots for UI changes

## Checklist

- [ ] Tests pass
- [ ] Documentation updated
- [ ] Code follows style guidelines
```

### Review Process

1. Automated checks must pass (CI/CD)
2. At least one maintainer approval required
3. Address review feedback
4. Squash commits if needed
5. Maintainer will merge

---

## Adding New Features

### New Forensic Technique

1. **Create module** in `analysis/`:

   ```python
   # analysis/new_technique.py
   def analyze_new_technique(image_path: str) -> dict:
       """
       Your technique implementation
       """
       pass
   ```

2. **Add tests** in `tests/`:

   ```python
   # tests/test_new_technique.py
   def test_new_technique_basic():
       pass
   ```

3. **Update app.py**:

   - Add import
   - Create new tab
   - Add UI controls

4. **Update documentation**:

   - Add to README.md feature list
   - Document in docs/API.md
   - Explain in docs/TECHNIQUES.md

5. **Update requirements.txt** if new dependencies added

### Example PR Checklist

- [ ] Module created in `analysis/`
- [ ] Tests added in `tests/`
- [ ] Integration with `app.py`
- [ ] README.md updated
- [ ] API.md documentation added
- [ ] TECHNIQUES.md explanation added
- [ ] Example usage provided
- [ ] Performance considerations documented

---

## Reporting Bugs

### Bug Report Template

```markdown
**Describe the bug**
Clear description of the bug

**To Reproduce**
Steps to reproduce:

1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What should happen

**Screenshots**
If applicable

**Environment**

- OS: [e.g., Windows 11]
- Python version: [e.g., 3.9.7]
- Veritas version: [e.g., 1.0.0]

**Additional context**
Any other relevant information
```

### Where to Report

- **GitHub Issues**: https://github.com/CodeRafay/Forensic-Image-Analysis-Toolkit/issues
- **Security Issues**: Email [rafayadeel1999@gmail.com] (do not post publicly)

---

## Project Structure

```
VeritasForensics/
├── analysis/           # Core analysis modules
│   ├── ela.py
│   ├── metadata_analysis.py
│   └── ...
├── tests/              # Test suite
│   ├── test_ela.py
│   ├── test_metadata.py
│   └── test_integration.py
├── docs/               # Documentation
│   ├── API.md
│   ├── TECHNIQUES.md
│   └── DEPLOYMENT.md
├── .streamlit/         # Streamlit configuration
├── app.py              # Main application
├── requirements.txt    # Production dependencies
├── requirements-dev.txt # Development dependencies
├── pytest.ini          # Pytest configuration
└── README.md
```

---

## Getting Help

- **Documentation**: Read docs/ folder
- **GitHub Discussions**: Ask questions
- **Issues**: Search existing issues
- **Email**: [rafayadeel1999@gmail.com]

---

## Recognition

Contributors will be:

- Listed in CONTRIBUTORS.md
- Credited in release notes
- Acknowledged in README.md (for significant contributions)

---

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (BSD License).

---

**Thank you for contributing to Veritas! 🎉**
