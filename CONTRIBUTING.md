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

- Python 3.10 (see `.python-version`)
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
python -m venv .venv

# Activate
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
# Runtime dependencies (enough to run the app and the full test suite)
pip install -r requirements.txt

# Optional: linters/formatters
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

The suite uses the standard-library `unittest` runner; pytest is not needed.

```bash
# All 142 tests (a few minutes)
python -m unittest discover -s tests -t .

# One module
python -m unittest tests.test_ela

# One test
python -m unittest tests.test_contract.TestResultContract.test_all_entry_points_all_inputs
```

`pytest.ini` is kept for anyone who prefers pytest, but its `addopts` require
`pytest-cov`; install `requirements-dev.txt` first or run `pytest -o addopts=""`.

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

### The result contract

Every public analysis function takes an image path (plus keyword options) and
returns `analysis.util.make_result(...)`:

```python
{
    "status": "ok" | "insufficient_data" | "not_applicable" | "error",
    "summary": str,                  # one neutral sentence: what was measured
    "findings": [{"level": "info" | "notice" | "warning", "text": str}],
    "metrics": {label: number | str},    # headline numbers shown in the UI
    "images": {caption: uint8 ndarray},  # (H, W) or (H, W, 3), in memory
    "tables": {title: list[dict] | dict},
    "limitations": [str],            # always shown
    "details": {...},                # raw JSON-serialisable values for tests
}
```

Rules (the first four are checked by `tests/test_contract.py`):

- Never raise. Wrap the body and return `util.error_result(e, LIMITATIONS)`.
- Too little data (tiny or flat image) must be `insufficient_data` or
  `not_applicable`, never an `ok` that looks clean.
- Float metrics must be finite; images must be uint8 arrays.
- Never claim authenticity. Summaries and findings must not say "authentic",
  "admissible", "no manipulation" or "proves"; say "no inconsistency found at
  this sensitivity" instead.
- Write nothing to disk; return images as arrays.
- Decode with `util.load_array` (no re-encode, EXIF orientation not applied).
  Only analyses that do not depend on compression traces may use its
  in-memory `max_px` downscale.

The app renders every result with one function (`render` in `app.py`), so a
module can add metrics, images or tables without touching the UI.

### Writing tests

- Each module has `tests/test_<module>.py` (`unittest.TestCase`).
- **Add every new entry point to `ENTRY_POINTS` in `tests/test_contract.py`.**
  It is then run on JPEG, PNG, grayscale, RGBA, palette, 16×16, 1×1 and flat
  inputs.
- **Calibrate thresholds on a seeded benchmark.** Generate positives and
  negatives synthetically with `np.random.default_rng(<seed>)` (no downloads):
  e.g. splices at several JPEG qualities, clean JPEGs q20–100, crops, PNGs.
  Measure the detection rate and the false-alarm rate, set the module
  constant to a stated false-alarm rate, cite the measurement in a comment
  next to the constant and in `Descriptions/<Technique>.md`, and add a test
  asserting both rates (see `test_splice_benchmark` in `tests/test_ela.py`).
- A metric must vary with what it measures: check it on a clean image, a
  manipulated one and a synthetic extreme before relying on it.

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
def analyze_thing(image_path, window=16):
    """
    One-line description of what is measured, then the published method:
    Author, "Title", Venue Year.

    Args:
        image_path: image file (read as stored, never re-encoded)
        window: smoothing window in px

    Returns:
        util.make_result(...). Metrics: <labels>. Images: <captions>.
        details: <raw keys used by tests>.
    """
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
feat(ela): report error relative to the image median

The high-error mask and percentage now use K x the image's own median
error, so they no longer depend on brightness or resave quality.
Calibrated on a seeded splice benchmark (see ela.py).

Closes #42
```

```
fix(metadata): handle images without EXIF data

Previously crashed when processing images without EXIF metadata.
Now returns an info finding ("No EXIF") in the result contract.

Fixes #58
```

---

## Pull Request Process

### Before Submitting

- [ ] All tests pass (`python -m unittest discover -s tests -t .`)
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

1. **Module** `analysis/<technique>.py` with an entry point returning the
   result contract. Cite the published method in the module docstring and
   keep calibrated thresholds as module constants with their measurement.
   Add the module name to `_MODULE_NAMES` in `analysis/__init__.py`.
2. **Tests**: `tests/test_<technique>.py` with a seeded benchmark, and an
   `ENTRY_POINTS` row in `tests/test_contract.py`.
3. **App**: add a tab in `app.py` that calls
   `run_panel(key, label, analysis.<module>.<fn>, file_path, ...)` and
   `describe("<Technique>")`.
4. **Docs**: `Descriptions/<Technique>.md` (method, what the output means,
   measured benchmark numbers, limitations), a row in the README technique
   table, an entry in `docs/API.md`, and a CHANGELOG entry.
5. **Dependencies**: pin any new package in `requirements.txt`.

### Example PR Checklist

- [ ] Entry point returns `make_result`, never raises
- [ ] Added to `tests/test_contract.py` `ENTRY_POINTS`
- [ ] Thresholds calibrated on a seeded benchmark; rates asserted in a test
- [ ] Tab added in `app.py`
- [ ] `Descriptions/<Technique>.md`, README, `docs/API.md`, CHANGELOG updated
- [ ] No wording that claims an image is authentic

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
- Python version: [e.g., 3.10.11]
- Veritas version: [e.g., 3.0.0]

**Additional context**
Any other relevant information
```

### Where to Report

- **GitHub Issues**: https://github.com/CodeRafay/Forensic-Image-Analysis-Toolkit/issues
- **Security Issues**: Email [rafayadeel1999@gmail.com] (do not post publicly)

---

## Project Structure

```
Forensic-Image-Analysis-Toolkit/
├── analysis/           # One module per technique + util.py (result contract)
├── tests/              # test_<module>.py per module + test_contract.py
├── Descriptions/       # Per-technique guides shown in the app
├── docs/               # API, deployment, project report
├── .streamlit/         # Streamlit configuration
├── app.py              # Streamlit app (13 tabs, one renderer)
├── requirements.txt    # Pinned runtime dependencies
├── requirements-dev.txt # Optional dev tools
└── README.md
```

See the README for the full tree.

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
