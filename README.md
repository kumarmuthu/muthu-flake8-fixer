# muthu-flake8-fixer

[![GitHub Repo](https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github)](https://github.com/kumarmuthu/muthu-flake8-fixer)
![GitHub License](https://img.shields.io/github/license/kumarmuthu/muthu-flake8-fixer?style=for-the-badge)
![GitHub Forks](https://img.shields.io/github/forks/kumarmuthu/muthu-flake8-fixer?style=for-the-badge)
![GitHub Stars](https://img.shields.io/github/stars/kumarmuthu/muthu-flake8-fixer?style=for-the-badge)
![GitHub Contributors](https://img.shields.io/github/contributors/kumarmuthu/muthu-flake8-fixer?style=for-the-badge)

[![Build Status](https://github.com/kumarmuthu/muthu-flake8-fixer/actions/workflows/python-app.yml/badge.svg)](https://github.com/kumarmuthu/muthu-flake8-fixer/actions/workflows/python-app.yml)
[![PyPI Version](https://img.shields.io/pypi/v/muthu-flake8-fixer?label=PyPI%20Version&color=brightgreen)](https://pypi.org/project/muthu-flake8-fixer/)
[![Test PyPI Version](https://img.shields.io/badge/dynamic/json?color=blue&label=Test%20PyPI&query=info.version&url=https://test.pypi.org/pypi/muthu-flake8-fixer/json&cacheSeconds=0)](https://test.pypi.org/project/muthu-flake8-fixer/)

![GitHub Image](https://avatars.githubusercontent.com/u/53684606?v=4&s=40)

Stop fixing flake8 errors by hand. **muthu-flake8-fixer** automatically detects and repairs
common PEP8 and flake8 violations — safely — using a 3-phase pipeline:
pycodestyle check → autopep8 formatting → AST-validated flake8 fixes.

Every fix is syntax-checked with Python's `ast` module. If a change breaks your code,
it is automatically reverted. Zero risk. Zero manual review for supported error codes.

**Author:** Muthukumar Subramanian  
**Version:** 0.1.0  
**Python:** 3.8+

---

## ✨ Features

- 🔄 3-phase workflow: pycodestyle check → autopep8 auto-fix → flake8 AST-safe fixer
- 🛡️ AST validation after every fix — reverts the file if syntax breaks
- 🧪 Safe dry-run mode by default (no files modified unless `--apply` is passed)
- 🪟 Windows path support (handles drive letter colons in flake8 output)
- 📄 BOM-aware file reading/writing (UTF-8 with BOM preserved)
- 💾 Optional `.bak` backup before modifying files
- 🎨 Colored terminal output (via `colorama`, gracefully degrades if not installed)

---

## 📁 File Structure

```
muthu-flake8-fixer/
├── muthu_flake8_fixer/
│   ├── __init__.py       ← exposes main(), __version__, __author__
│   └── fixer.py          ← full script logic (all fixers, phases, CLI)
├── pyproject.toml        ← build system declaration (setuptools + wheel)
├── setup.py              ← thin shim required for editable installs (pip install -e .)
├── MANIFEST.in           ← source distribution file inclusion rules
├── LICENSE               ← proprietary license
├── .gitignore            ← Python / packaging ignores
└── README.md             ← this file
```

### 🗂️ Key files explained

| File                             | Purpose                                                                                                        |
|----------------------------------|----------------------------------------------------------------------------------------------------------------|
| `muthu_flake8_fixer/__init__.py` | Python package marker; imports `main` so the package is importable                                             |
| `muthu_flake8_fixer/fixer.py`    | All logic: argument parsing, phase 1-2 (pyformatter), phase 3 (flake8 fixer), individual fixers per error code |
| `pyproject.toml`                 | Package metadata, build system declaration, dependencies, and CLI entry point                                  |
| `setup.py`                       | Minimal shim (`setup()`) needed for `pip install -e .` editable mode                                           |

---

## 📦 Installation

### 1️⃣ Install via PyPI (recommended)

```bash
pip install muthu-flake8-fixer
```

### 2️⃣ Clone the repository (optional / development)

```bash
git clone https://github.com/kumarmuthu/muthu-flake8-fixer
cd muthu-flake8-fixer
pip install -e .
```

---

## 🚀 Usage

After installation, the `muthu-flake8-fixer` command is available system-wide.

### ⚡ Quick start

```bash
# Dry-run (preview only, no files modified) — default mode
muthu-flake8-fixer --path ./myproject

# Apply all fixes
muthu-flake8-fixer --path ./myproject --apply
```

### 🛠️ All options

```bash
# Preview with detailed per-line diff output
muthu-flake8-fixer --path ./myproject --dry-run --verbose

# Apply fixes with .bak backup before modifying
muthu-flake8-fixer --path ./myproject --apply --backup

# Read errors from a saved flake8 output file
muthu-flake8-fixer --flake8-output errors.txt --apply

# Fix only specific error codes
muthu-flake8-fixer --path . --codes W291,W293,F541 --apply

# Fix all safe codes except specific ones
muthu-flake8-fixer --path . --exclude-codes F401,F541 --apply

# Exclude specific file patterns
muthu-flake8-fixer --path . --exclude-files "*.bak,test_*" --apply

# Use custom max line length
muthu-flake8-fixer --path . --max-line-length 100 --dry-run

# Skip muthu-pyformatter phase (run only flake8 fixer)
muthu-flake8-fixer --path . --skip-pyformatter --apply

# Run only muthu-pyformatter phase (skip flake8 fixer)
muthu-flake8-fixer --path . --only-pyformatter --apply

# Set autopep8 aggressiveness (0=safe, 1=aggressive default, 2=very aggressive)
muthu-flake8-fixer --path . --autopep8-level 2 --apply
```

> **Note:** Running with no arguments is equivalent to `muthu-flake8-fixer --path . --dry-run`.  
> It scans the current working directory and makes no changes.

---

## 🔁 Workflow (3 Phases)

```
Phase 1  →  pycodestyle check     (detect PEP8 violations, report count)
Phase 2  →  autopep8 auto-fix     (fix formatting: whitespace, indentation, line length)
Phase 3  →  flake8 AST-safe fix   (fix F-codes and remaining E/W codes safely)
```

Phases 1 and 2 can be skipped with `--skip-pyformatter`.  
Phase 3 can be skipped with `--only-pyformatter`.

---

## ✅ Error Codes Handled (Phase 3)

| Code   | Description                                                             |
|--------|-------------------------------------------------------------------------|
| `W291` | Trailing whitespace                                                     |
| `W292` | No newline at end of file                                               |
| `W293` | Blank line contains whitespace                                          |
| `W391` | Blank line at end of file                                               |
| `E265` | Block comment should start with `# `                                    |
| `E266` | Too many leading `#` for block comment                                  |
| `E231` | Missing whitespace after `,` or `;` (colon skipped — unsafe for slices) |
| `E261` | At least two spaces before inline comment                               |
| `E272` | Multiple spaces before keyword                                          |
| `E301` | Expected 1 blank line before method/nested class                        |
| `E302` | Expected 2 blank lines before top-level definition                      |
| `E303` | Too many blank lines                                                    |
| `E305` | Expected 2 blank lines after top-level definition                       |
| `F541` | f-string without placeholders (AST-confirmed safe)                      |
| `F401` | Unused import (with conservative grep double-check)                     |

## ⚠️ Error Codes NOT Handled (require manual review)

| Code            | Description                                    |
|-----------------|------------------------------------------------|
| `F403` / `F405` | Star imports                                   |
| `F841`          | Unused local variable                          |
| `F811`          | Redefinition of unused name                    |
| `E722`          | Bare `except`                                  |
| `E501`          | Line too long (handled by autopep8 in Phase 2) |
| `E127` / `E128` | Continuation line indent                       |
| `E225`          | Missing whitespace around operator             |

---

## 📦 Dependencies

| Package       | Required             | Purpose                   |
|---------------|----------------------|---------------------------|
| `flake8`      | Yes (runtime)        | Detects errors in Phase 3 |
| `pycodestyle` | Yes (auto-installed) | Phase 1 violation check   |
| `autopep8`    | Yes (auto-installed) | Phase 2 auto-formatting   |
| `colorama`    | Optional             | Colored terminal output   |

Missing `pycodestyle` and `autopep8` are auto-installed on first run.

---

## 🔒 Safety Guarantees

- 🧬 Every modified file is parsed with `ast.parse()` after fixes — if the result has a syntax error,
  **all changes to that file are reverted**
- 🔍 `F401` (unused import) uses a conservative grep: if the import name appears anywhere else in the file, it is kept
- 🚫 `F401` never removes imports from `__init__.py` (re-exports are intentional)
- ✂️ `E231` colon fixes are skipped to avoid breaking slice syntax (`a[1:2]`)
- ⚛️ Files are written atomically via a temp file + `os.replace()` to prevent corruption on failure

---

## 📜 License

Copyright © 2026 Muthukumar Subramanian. All rights reserved.