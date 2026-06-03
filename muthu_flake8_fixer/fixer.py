"""
Flake8 Auto-Fixer — Safe, AST-aware automatic fixer for common flake8 errors.
Integrates muthu-pyformatter (pycodestyle + autopep8) for comprehensive code quality.
Copyright @2026 Muthukumar. All rights reserved.

WORKFLOW (3-Phase):
  Phase 1: pycodestyle check (detect PEP8 violations)
  Phase 2: autopep8 auto-fix (fix formatting: whitespace, indentation, line length)
  Phase 3: flake8 AST-safe fix (fix F-codes and remaining E/W codes safely)

SAFE CODES HANDLED (Phase 3 - flake8 fixer):
  W291  trailing whitespace
  W292  no newline at end of file
  W293  blank line contains whitespace
  W391  blank line at end of file
  E265  block comment should start with '# '
  E266  too many leading '#' for block comment
  E231  missing whitespace after ',' or ';' (colon skipped — unsafe for slices)
  E261  at least two spaces before inline comment
  E272  multiple spaces before keyword
  E301  expected 1 blank line before method/nested class
  E302  expected 2 blank lines before top-level definition
  E303  too many blank lines
  E305  expected 2 blank lines after top-level definition
  F541  f-string without placeholders (AST-based, safe)
  F401  unused import (with double-check grep)

CODES NOT HANDLED (need human review / handled by autopep8):
  F403/F405  star imports
  F841       unused local variable
  E722       bare except
  E501       line too long
  E203       whitespace before punctuation (handled by autopep8)
  E127/E128  continuation indent
  E225       missing whitespace around operator
  F811       redefinition of unused

Quick Start (auto-fix all flake8 errors in your project):
  muthu-flake8-fixer --path ./myproject --apply

Usage:
  # Preview all fixes (dry-run, default mode)
  muthu-flake8-fixer --path ./myproject --dry-run

  # Preview with detailed per-line diff output
  muthu-flake8-fixer --path ./myproject --dry-run --verbose

  # Apply all fixes to files
  muthu-flake8-fixer --path ./myproject --apply

  # Apply fixes with .bak backup before modifying
  muthu-flake8-fixer --path ./myproject --apply --backup

  # Read errors from a saved flake8 output file instead of running flake8
  muthu-flake8-fixer --flake8-output errors.txt --apply

  # Fix only specific error codes
  muthu-flake8-fixer --path . --codes W291,W293,F541 --apply

  # Fix all safe codes except specific ones
  muthu-flake8-fixer --path . --exclude-codes F401,F541 --apply

  # Exclude specific file patterns
  muthu-flake8-fixer --path . --exclude-files "*.bak,test_*" --apply

  # Use custom max line length
  muthu-flake8-fixer --path . --max-line-length 120 --dry-run

  # Skip muthu-pyformatter phase (run only flake8 fixer)
  muthu-flake8-fixer --path . --skip-pyformatter --apply

  # Run only muthu-pyformatter phase (skip flake8 fixer)
  muthu-flake8-fixer --path . --only-pyformatter --apply

HISTORY
- 2026.06.30.01 - Muthukumar Subramanian
    * Initial release with integrated muthu-pyformatter (pycodestyle + autopep8) and AST-based flake8 fixer
"""
__version__ = "2026.06.30.01"
__author__ = "Muthukumar Subramanian"

import os
import re
import ast
import sys
import shutil
import difflib
import fnmatch
import argparse
import tempfile
import subprocess
from collections import defaultdict

try:
    import colorama

    colorama.init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False


class Color:
    @staticmethod
    def _wrap(code, text):
        if not HAS_COLOR:
            return text
        return f"{code}{text}{colorama.Style.RESET_ALL}"

    @staticmethod
    def red(text):
        return Color._wrap(colorama.Fore.RED, text) if HAS_COLOR else text

    @staticmethod
    def green(text):
        return Color._wrap(colorama.Fore.GREEN, text) if HAS_COLOR else text

    @staticmethod
    def yellow(text):
        return Color._wrap(colorama.Fore.YELLOW, text) if HAS_COLOR else text

    @staticmethod
    def cyan(text):
        return Color._wrap(colorama.Fore.CYAN, text) if HAS_COLOR else text

    @staticmethod
    def magenta(text):
        return Color._wrap(colorama.Fore.MAGENTA, text) if HAS_COLOR else text

    @staticmethod
    def blue(text):
        return Color._wrap(colorama.Fore.BLUE, text) if HAS_COLOR else text


ALL_SAFE_CODES = [
    "W291", "W292", "W293", "W391",
    "E265", "E266",
    "E231", "E261", "E272",
    "E301", "E302", "E303", "E305",
    "F541", "F401",
]

DEFAULT_EXCLUDE_PATTERNS = [
    "*.yaml", "*.yml", "*.json", "*.md", "*.txt", "*.cfg", "*.ini",
    "*copy*", "*Copy*", "*COPY*",
    "__pycache__/*", ".git/*", "*.pyc",
]

PYTHON_KEYWORDS = {
    "and", "as", "assert", "async", "await", "break", "class", "continue",
    "def", "del", "elif", "else", "except", "finally", "for", "from",
    "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
    "or", "pass", "raise", "return", "try", "while", "with", "yield",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Safe, AST-aware auto-fixer for common flake8 errors",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--path", type=str, default=".",
        help="Target directory or file to fix (default: current dir)",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run", action="store_true",
        help="Show changes without writing (default behavior)",
    )
    mode_group.add_argument(
        "--apply", action="store_true",
        help="Actually write changes to files",
    )
    parser.add_argument(
        "--codes", type=str, default=None,
        help="Comma-separated error codes to fix (default: all safe codes)",
    )
    parser.add_argument(
        "--exclude-codes", type=str, default=None,
        help="Comma-separated error codes to skip",
    )
    parser.add_argument(
        "--exclude-files", type=str, default=None,
        help="Comma-separated glob patterns to exclude files",
    )
    parser.add_argument(
        "--flake8-output", type=str, default=None,
        help="Read flake8 errors from a file instead of running flake8",
    )
    parser.add_argument(
        "--backup", action="store_true", default=False,
        help="Create .bak backup before modifying files",
    )
    parser.add_argument(
        "--verbose", action="store_true", default=False,
        help="Show detailed per-line changes",
    )
    parser.add_argument(
        "--max-line-length", type=int, default=120,
        help="Max line length for pycodestyle, autopep8, and flake8 (default: 120)",
    )
    parser.add_argument(
        "--skip-pyformatter", action="store_true", default=False,
        help="Skip muthu-pyformatter phase (run only flake8 fixer)",
    )
    parser.add_argument(
        "--only-pyformatter", action="store_true", default=False,
        help="Run only muthu-pyformatter phase (skip flake8 fixer)",
    )
    parser.add_argument(
        "--autopep8-level", type=int, default=1, choices=[0, 1, 2],
        help="autopep8 aggressiveness level: 0=safe, 1=aggressive (default), 2=very aggressive",
    )
    return parser.parse_args()


def should_exclude_file(filepath, exclude_patterns):
    basename = os.path.basename(filepath)
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(basename, pattern):
            return True
        if fnmatch.fnmatch(filepath, pattern):
            return True
    if not filepath.endswith(".py"):
        return True
    return False


# ---------- muthu-pyformatter Integration (Phase 1-2) ----------

PYFORMATTER_SKIP_DIRS = {
    "venv", ".venv", "env", ".git", "__pycache__",
    ".tox", ".mypy_cache", ".pytest_cache",
    "build", "dist", "site-packages", "_internal",
}

FLAKE8_EXCLUDE_DIRS = ",".join(sorted(PYFORMATTER_SKIP_DIRS))


def get_python_files(base_path):
    if os.path.isfile(base_path):
        return [base_path] if base_path.endswith(".py") else []

    python_files = []
    for root, dirs, files in os.walk(base_path):
        dirs[:] = [d for d in dirs if d not in PYFORMATTER_SKIP_DIRS]
        for f in files:
            if f.endswith(".py"):
                python_files.append(os.path.join(root, f))
    return python_files


def check_pyformatter_deps():
    missing = []
    for mod in ["pycodestyle", "autopep8"]:
        try:
            result = subprocess.run(
                [sys.executable, "-m", mod, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                missing.append(mod)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            missing.append(mod)
    return missing


def install_missing_deps(missing):
    print(Color.yellow(f"Auto-installing missing dependencies: {', '.join(missing)}"))
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install"] + missing,
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode == 0:
        print(Color.green(f"Successfully installed: {', '.join(missing)}"))
        return True
    else:
        print(Color.red(f"Failed to install dependencies (exit code {result.returncode})"))
        if result.stderr:
            print(Color.red(f"  {result.stderr.strip()}"))
        return False


def run_pyformatter(target_path, max_line_length, dry_run=True, verbose=False, autopep8_level=1):
    print(Color.cyan(f"{'=' * 60}"))
    print(Color.cyan("Phase 1-2: muthu-pyformatter (pycodestyle + autopep8)"))
    print(Color.cyan(f"{'=' * 60}"))
    print()

    missing = check_pyformatter_deps()
    if missing:
        if not install_missing_deps(missing):
            print(Color.red("Skipping pyformatter phase due to installation failure."))
            print()
            return False
        still_missing = check_pyformatter_deps()
        if still_missing:
            print(Color.red(f"Still missing after install: {', '.join(still_missing)}"))
            print(Color.yellow("Skipping pyformatter phase."))
            print()
            return False

    abs_path = os.path.abspath(target_path)
    python_files = get_python_files(target_path)
    total_files = len(python_files)

    print(Color.cyan(f"Target path: {abs_path}"))
    print(Color.blue(f"Python files found: {total_files}"))
    print()

    if total_files == 0:
        print(Color.yellow("No Python files to scan."))
        print()
        return True

    # Phase 1: pycodestyle check (before)
    print(Color.magenta(f"[Phase 1] Running pycodestyle (max line length: {max_line_length})..."))
    print()
    result_before = subprocess.run(
        [sys.executable, "-m", "pycodestyle",
         f"--max-line-length={max_line_length}", target_path],
        capture_output=True, text=True, timeout=120,
    )
    before_lines = result_before.stdout.strip().splitlines() if result_before.stdout.strip() else []
    before_count = len(before_lines)

    if before_count > 0:
        print(Color.yellow(f"  pycodestyle violations found: {before_count}"))
    else:
        print(Color.green("  pycodestyle violations found: 0"))

    if verbose and before_lines:
        for line in before_lines[:20]:
            print(Color.red(f"    {line}"))
        if before_count > 20:
            print(Color.yellow(f"    ... and {before_count - 20} more"))
    print()

    # Phase 2: autopep8 auto-fix
    if dry_run:
        print(Color.yellow("[Phase 2] autopep8 auto-fix: SKIPPED (dry-run mode)"))
        print(Color.yellow("  Run with --apply to execute autopep8 formatting."))
    else:
        print(Color.magenta("[Phase 2] Running autopep8 auto-fix..."))
        autopep8_cmd = [
            sys.executable, "-m", "autopep8",
            f"--max-line-length={max_line_length}",
            "--in-place",
        ]
        for _ in range(autopep8_level):
            autopep8_cmd.append("--aggressive")
        if os.path.isdir(target_path):
            autopep8_cmd.append("--recursive")
            autopep8_cmd.append(f"--exclude={FLAKE8_EXCLUDE_DIRS}")
        autopep8_cmd.append(target_path)
        result_autopep8 = subprocess.run(
            autopep8_cmd, capture_output=True, text=True, timeout=300,
        )
        if result_autopep8.returncode != 0:
            print(Color.red(f"  autopep8 failed (exit code {result_autopep8.returncode})"))
            if result_autopep8.stderr:
                print(Color.red(f"  {result_autopep8.stderr.strip()}"))
        else:
            print(Color.green("  autopep8 formatting applied."))

        # Re-check with pycodestyle
        print()
        print(Color.magenta("[Phase 2] Re-running pycodestyle after autopep8 fixes..."))
        result_after = subprocess.run(
            [sys.executable, "-m", "pycodestyle",
             f"--max-line-length={max_line_length}", target_path],
            capture_output=True, text=True, timeout=120,
        )
        after_lines = result_after.stdout.strip().splitlines() if result_after.stdout.strip() else []
        after_count = len(after_lines)
        print(Color.cyan(f"  Violations before autopep8: {before_count}"))
        print(Color.cyan(f"  Violations after autopep8:  {after_count}"))
        fixed_count = before_count - after_count
        if fixed_count > 0:
            print(Color.green(f"  Fixed by autopep8:          {fixed_count}"))
        else:
            print(Color.yellow(f"  Fixed by autopep8:          {fixed_count}"))

        if verbose and after_lines:
            print(Color.yellow("  Remaining violations:"))
            for line in after_lines[:20]:
                print(Color.red(f"    {line}"))
            if after_count > 20:
                print(Color.yellow(f"    ... and {after_count - 20} more"))

    print()
    print(Color.green(f"{'=' * 60}"))
    print(Color.green("Phase 1-2 Complete"))
    print(Color.green(f"{'=' * 60}"))
    print()
    return True


def run_flake8(target_path, max_line_length, codes_to_check):
    select_arg = ",".join(codes_to_check)
    cmd = [
        sys.executable, "-m", "flake8",
        "--format=default",
        f"--max-line-length={max_line_length}",
        f"--exclude={FLAKE8_EXCLUDE_DIRS}",
        "--jobs=auto",
        f"--select={select_arg}",
        target_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode > 1:
            print(Color.red(f"ERROR: flake8 execution failed (exit code {result.returncode})"))
            if result.stderr:
                print(Color.red(f"  {result.stderr.strip()}"))
            sys.exit(1)
        return result.stdout
    except FileNotFoundError:
        print(Color.red("ERROR: flake8 is not installed. Install it with: pip install flake8"))
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(Color.red("ERROR: flake8 timed out after 120 seconds"))
        sys.exit(1)


def parse_flake8_output(raw_output):
    errors_by_file = defaultdict(list)
    # Matches "filepath:line:col: CODE message"
    # Handles Windows drive letters (C:\...) by anchoring on ": CODE" pattern
    pattern = re.compile(
        r'^(.+?):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)$'
    )
    for line in raw_output.strip().splitlines():
        stripped = line.strip()
        # On Windows, skip the drive letter colon (e.g., C:\path)
        # by finding the match after any drive prefix
        m = pattern.match(stripped)
        if not m and len(stripped) > 2 and stripped[1] == ':':
            # Try matching after drive letter (e.g., "C:\foo\bar.py:10:1: E501 ...")
            m = pattern.match(stripped[2:])
            if m:
                filepath = os.path.normpath(stripped[:2] + m.group(1))
                lineno = int(m.group(2))
                col = int(m.group(3))
                code = m.group(4)
                message = m.group(5)
                errors_by_file[filepath].append((lineno, col, code, message))
                continue
        if m:
            filepath = os.path.normpath(m.group(1))
            lineno = int(m.group(2))
            col = int(m.group(3))
            code = m.group(4)
            message = m.group(5)
            errors_by_file[filepath].append((lineno, col, code, message))
    return errors_by_file


def is_inside_string(line, col):
    in_string = False
    quote_char = None
    triple = False
    i = 0
    limit = min(col - 1, len(line))
    while i < limit:
        ch = line[i]
        if not in_string:
            if ch in ('"', "'"):
                # Check for triple quote
                if line[i:i + 3] in ('"""', "'''"):
                    in_string = True
                    quote_char = ch
                    triple = True
                    i += 3
                    continue
                in_string = True
                quote_char = ch
                triple = False
                i += 1
                continue
            # Skip f/r/b string prefixes
            if ch in ('f', 'r', 'b', 'F', 'R', 'B') and i + 1 < limit:
                next_ch = line[i + 1]
                if next_ch in ('"', "'"):
                    i += 1
                    continue
            i += 1
        else:
            if ch == '\\' and not triple:
                i += 2
                continue
            if triple:
                if line[i:i + 3] == quote_char * 3:
                    in_string = False
                    quote_char = None
                    triple = False
                    i += 3
                    continue
            elif ch == quote_char:
                in_string = False
                quote_char = None
                i += 1
                continue
            i += 1
    return in_string


# ---------- Individual Fixers ----------

def fix_w291(line):
    newline = "\n" if line.endswith("\n") else ""
    return line.rstrip("\r\n \t") + newline


def fix_w293(line):
    if line.strip() == "":
        newline = "\r\n" if line.endswith("\r\n") else "\n"
        return newline
    return line


def fix_w391(lines):
    while len(lines) > 1 and lines[-1].strip() == "" and lines[-2].strip() == "":
        lines.pop()
    return True


def fix_e303(lines, lineno, message):
    m = re.search(r'(\d+)', message)
    if not m:
        return False
    idx = lineno - 1
    if idx <= 0:
        return False
    # Walk backwards to find the first blank line in the run
    blank_end = idx
    blank_start = idx - 1
    while blank_start > 0 and lines[blank_start - 1].strip() == "":
        blank_start -= 1
    # Determine max allowed: 2 for top-level, 1 for inside class/function
    max_allowed = 2
    if blank_start > 0:
        prev_content = lines[blank_start - 1]
        if prev_content[0:1] in (' ', '\t'):
            max_allowed = 1
    counted = blank_end - blank_start
    remove_count = counted - max_allowed
    if remove_count > 0 and blank_start + remove_count <= len(lines):
        del lines[blank_start:blank_start + remove_count]
        return True
    return False


def fix_e265(line):
    return re.sub(r'^(\s*)#([^ !#\n])', r'\1# \2', line)


def fix_e266(line):
    m = re.match(r'^(\s*)#{2,}\s*(.*)', line)
    if m:
        newline = "\r\n" if line.endswith("\r\n") else "\n"
        return m.group(1) + "# " + m.group(2) + newline
    return line


def fix_e231(line, col):
    if is_inside_string(line, col):
        return line
    idx = col - 1
    if idx < len(line):
        char_at = line[idx]
        if char_at in (',', ';'):
            if idx + 1 < len(line) and line[idx + 1] not in (' ', '\n', '\r'):
                return line[:idx + 1] + ' ' + line[idx + 1:]
    return line


def fix_e261(line):
    hash_pos = line.find("#")
    if hash_pos == -1:
        return line
    if is_inside_string(line, hash_pos + 1):
        return line
    before = line[:hash_pos].rstrip()
    after = line[hash_pos:]
    if before:
        return before + "  " + after
    return line


def fix_e272(line, col):
    if is_inside_string(line, col):
        return line
    idx = col - 1
    segment_before = line[:idx]
    segment_after = line[idx:]
    m = re.match(r'\s{2,}(\w+)', segment_after)
    if m:
        word = m.group(1)
        if word in PYTHON_KEYWORDS:
            return segment_before.rstrip() + " " + segment_after.lstrip()
    return line


def fix_e301(lines, lineno):
    idx = lineno - 1
    if idx > 0:
        prev_line = lines[idx - 1]
        if prev_line.strip() != "":
            lines.insert(idx, "\n")
            return True
    return False


def fix_e302(lines, lineno):
    idx = lineno - 1
    # Walk backwards past decorators to find the real insertion point
    insert_idx = idx
    while insert_idx > 0 and lines[insert_idx - 1].lstrip().startswith("@"):
        insert_idx -= 1
    blank_count = 0
    check_idx = insert_idx - 1
    while check_idx >= 0 and lines[check_idx].strip() == "":
        blank_count += 1
        check_idx -= 1
    needed = 2 - blank_count
    for _ in range(needed):
        lines.insert(insert_idx, "\n")
    return needed > 0


def fix_e305(lines, lineno):
    idx = lineno - 1
    if idx <= 0:
        return False
    # Walk backwards past decorators to find the real insertion point
    insert_idx = idx
    while insert_idx > 0 and lines[insert_idx - 1].lstrip().startswith("@"):
        insert_idx -= 1
    if insert_idx <= 0:
        return False
    blank_count = 0
    check_idx = insert_idx - 1
    while check_idx >= 0 and lines[check_idx].strip() == "":
        blank_count += 1
        check_idx -= 1
    needed = 2 - blank_count
    if needed <= 0:
        return False
    for _ in range(needed):
        lines.insert(insert_idx, "\n")
    return True


def get_f541_safe_positions(filepath, source):
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return set()

    safe_positions = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            has_placeholder = any(
                isinstance(v, ast.FormattedValue) for v in node.values
            )
            if not has_placeholder:
                safe_positions.add((node.lineno, node.col_offset))

    return safe_positions


def fix_f541_in_line(line, col_offset):
    idx = col_offset
    if idx >= len(line):
        return line
    rest = line[idx:]
    m = re.match(r'^([rRbBuU]*)([fF])', rest)
    if m:
        prefix_len = len(m.group(1)) + len(m.group(2))
        return line[:idx] + m.group(1) + rest[prefix_len:]
    return line


def fix_f401(lines, lineno, message, filepath):
    idx = lineno - 1
    if idx >= len(lines):
        return False

    # Skip __init__.py — imports there are often intentional re-exports
    if os.path.basename(filepath) == "__init__.py":
        return False

    line = lines[idx]
    stripped_line = line.strip()

    # Skip multiline imports (parenthesized or backslash-continued)
    if '(' in stripped_line and ')' not in stripped_line:
        return False
    if stripped_line.endswith('\\'):
        return False

    m = re.search(r"'([^']+)'\s+imported but unused", message)
    if not m:
        return False

    full_import = m.group(1)
    if " as " in full_import:
        import_name = full_import.split(" as ")[-1].strip()
    else:
        import_name = full_import.split(".")[-1]

    # Conservative grep — prefers false negatives (keeping unused imports)
    # over false positives (deleting used imports)
    for i, other_line in enumerate(lines):
        if i == idx:
            continue
        other_stripped = other_line.strip()
        if other_stripped.startswith("#"):
            continue
        if re.search(r'\b' + re.escape(import_name) + r'\b', other_line):
            return False

    if stripped_line.startswith("from") and "import" in stripped_line:
        import_match = re.match(
            r'^(\s*from\s+\S+\s+import\s+)(.*)',
            line.rstrip('\n'),
        )
        if import_match:
            prefix = import_match.group(1)
            imports_str = import_match.group(2)
            imports_list = [s.strip() for s in imports_str.split(",")]

            as_pattern = re.compile(r'^(\S+)\s+as\s+(\S+)$')
            remaining = []
            for imp in imports_list:
                as_m = as_pattern.match(imp)
                actual_name = as_m.group(2) if as_m else imp
                if actual_name == import_name:
                    continue
                remaining.append(imp)

            newline = "\r\n" if line.endswith("\r\n") else "\n"
            if not remaining:
                lines[idx] = ""
            else:
                lines[idx] = prefix + ", ".join(remaining) + newline
            return True
    elif stripped_line.startswith("import"):
        import_items = re.sub(r'^import\s+', '', stripped_line)
        items = [s.strip() for s in import_items.split(",")]
        remaining = [
            item for item in items
            if item.split(".")[-1] != import_name
            and not item.endswith(" as " + import_name)
        ]

        if not remaining:
            lines[idx] = ""
        else:
            indent = len(line) - len(line.lstrip())
            newline = "\r\n" if line.endswith("\r\n") else "\n"
            lines[idx] = " " * indent + "import " + ", ".join(remaining) + newline
        return True

    return False


# ---------- Main Fix Engine ----------

def apply_fixes_to_file(filepath, errors, codes_to_fix, verbose=False):
    # Read with utf-8-sig to transparently handle BOM
    with open(filepath, 'rb') as f:
        raw_bytes = f.read()
    has_bom = raw_bytes.startswith(b'\xef\xbb\xbf')
    encoding = 'utf-8-sig' if has_bom else 'utf-8'
    original_content = raw_bytes.decode(encoding, errors='replace')
    lines = original_content.splitlines(True)

    changes = []
    f541_positions = None

    errors_by_line = defaultdict(list)
    for lineno, col, code, message in errors:
        if code in codes_to_fix:
            errors_by_line[lineno].append((col, code, message))

    line_insert_codes = {"E301", "E302", "E303", "E305"}
    has_line_inserts = any(
        code in line_insert_codes
        for errs in errors_by_line.values()
        for _, code, _ in errs
    )

    if has_line_inserts:
        insert_errors = []
        for lineno, errs in sorted(errors_by_line.items()):
            for col, code, message in errs:
                if code in line_insert_codes:
                    insert_errors.append((lineno, col, code, message))

        for lineno, col, code, message in sorted(insert_errors, key=lambda x: x[0], reverse=True):
            if code == "E301":
                if fix_e301(lines, lineno):
                    changes.append((lineno, code, "inserted 1 blank line"))
            elif code == "E302":
                if fix_e302(lines, lineno):
                    changes.append((lineno, code, "inserted blank line(s) for 2-line gap"))
            elif code == "E303":
                if fix_e303(lines, lineno, message):
                    changes.append((lineno, code, "removed excess blank lines"))
            elif code == "E305":
                if fix_e305(lines, lineno):
                    changes.append((lineno, code, "inserted blank line(s) after definition"))

        remaining_codes = codes_to_fix - line_insert_codes
        if remaining_codes:
            lines = "".join(lines).splitlines(True)

    for lineno in sorted(errors_by_line.keys()):
        errs = errors_by_line[lineno]
        for col, code, message in sorted(errs, key=lambda x: x[0], reverse=True):
            if code in line_insert_codes:
                continue

            idx = lineno - 1
            if idx >= len(lines):
                continue

            old_line = lines[idx]

            if code == "W291":
                lines[idx] = fix_w291(old_line)
            elif code == "W293":
                lines[idx] = fix_w293(old_line)
            elif code == "E265":
                lines[idx] = fix_e265(old_line)
            elif code == "E266":
                lines[idx] = fix_e266(old_line)
            elif code == "E231":
                lines[idx] = fix_e231(old_line, col)
            elif code == "E261":
                lines[idx] = fix_e261(old_line)
            elif code == "E272":
                lines[idx] = fix_e272(old_line, col)
            elif code == "F541":
                if f541_positions is None:
                    f541_positions = get_f541_safe_positions(filepath, original_content)
                if (lineno, col - 1) in f541_positions:
                    lines[idx] = fix_f541_in_line(old_line, col - 1)
                else:
                    if verbose:
                        print(f"  SKIP F541 at {filepath}:{lineno}:{col} — not confirmed safe by AST")
                    continue
            elif code == "F401":
                if fix_f401(lines, lineno, message, filepath):
                    pass
                else:
                    if verbose:
                        print(f"  SKIP F401 at {filepath}:{lineno} — import name found elsewhere in file")
                    continue
            else:
                continue

            if lines[idx] != old_line:
                changes.append((lineno, code, "fixed"))

    w391_needed = "W391" in codes_to_fix and any(
        code == "W391" for _, _, code, _ in errors
    )
    if w391_needed and len(lines) > 1:
        orig_len = len(lines)
        fix_w391(lines)
        if len(lines) < orig_len:
            changes.append((orig_len, "W391", "removed trailing blank lines"))

    new_content = "".join(lines)

    w292_needed = "W292" in codes_to_fix and any(
        code == "W292" for _, _, code, _ in errors
    )
    if w292_needed and new_content and not new_content.endswith("\n"):
        new_content += "\n"
        changes.append((len(lines), "W292", "added newline at end of file"))

    if changes and new_content != original_content:
        try:
            ast.parse(new_content, filename=filepath)
        except SyntaxError as e:
            print(Color.red(
                f"  SAFETY: modifications to {filepath} produced invalid syntax "
                f"(line {e.lineno}) — reverting all changes"
            ))
            return original_content, original_content, [], has_bom

    return original_content, new_content, changes, has_bom


def show_diff(filepath, original, modified, verbose=False):
    if not verbose:
        return

    orig_lines = original.splitlines(True)
    mod_lines = modified.splitlines(True)

    diff = difflib.unified_diff(
        orig_lines, mod_lines,
        fromfile=filepath, tofile=filepath,
        lineterm="",
    )
    for diff_line in diff:
        text = diff_line.rstrip()
        if diff_line.startswith('+') and not diff_line.startswith('+++'):
            print(Color.green(f"    {text}"))
        elif diff_line.startswith('-') and not diff_line.startswith('---'):
            print(Color.red(f"    {text}"))
        elif diff_line.startswith('@@'):
            print(Color.cyan(f"    {text}"))
        else:
            print(f"    {text}")


def main():
    args = parse_args()

    args.dry_run = not args.apply

    codes_to_fix = set(ALL_SAFE_CODES)
    if args.codes:
        codes_to_fix = set(c.strip().upper() for c in args.codes.split(","))
    if args.exclude_codes:
        excluded = set(c.strip().upper() for c in args.exclude_codes.split(","))
        codes_to_fix -= excluded

    exclude_patterns = list(DEFAULT_EXCLUDE_PATTERNS)
    if args.exclude_files:
        exclude_patterns.extend(p.strip() for p in args.exclude_files.split(","))

    unsupported = codes_to_fix - set(ALL_SAFE_CODES)
    if unsupported:
        skipped_str = ', '.join(sorted(unsupported))
        print(Color.yellow(f"WARNING: These codes are not supported and will be skipped: {skipped_str}"))
        codes_to_fix -= unsupported

    print(Color.cyan(f"{'=' * 60}"))
    print(Color.cyan(f"Flake8 Auto-Fixer v{__version__}"))
    print(Color.cyan(f"{'=' * 60}"))
    if args.dry_run:
        mode_str = Color.yellow('DRY-RUN (no files modified)')
    else:
        mode_str = Color.green('APPLY (files will be modified)')
    print(f"Mode:            {mode_str}")
    print(f"Target:          {Color.cyan(os.path.abspath(args.path))}")
    pyf_str = Color.yellow('Skip') if args.skip_pyformatter else Color.green('Enabled')
    flk_str = Color.yellow('Skip') if args.only_pyformatter else Color.green('Enabled')
    print(f"Pyformatter:     {pyf_str}")
    print(f"Flake8 fixer:    {flk_str}")
    print(f"Codes to fix:    {Color.blue(', '.join(sorted(codes_to_fix)))}")
    print(f"Max line length: {args.max_line_length}")
    print(f"Autopep8 level:  {args.autopep8_level}")
    bkp_str = Color.green('Yes') if args.backup else 'No'
    print(f"Backup:          {bkp_str}")
    print(Color.cyan(f"{'=' * 60}"))
    print()

    # --- Phase 1-2: muthu-pyformatter (pycodestyle + autopep8) ---
    if not args.skip_pyformatter:
        run_pyformatter(
            args.path, args.max_line_length,
            dry_run=args.dry_run, verbose=args.verbose,
            autopep8_level=args.autopep8_level,
        )

    if args.only_pyformatter:
        print(Color.yellow("Skipping Phase 3 (flake8 fixer) -- --only-pyformatter was set."))
        return

    # --- Phase 3: flake8 AST-safe fixer ---
    print(Color.cyan(f"{'=' * 60}"))
    print(Color.cyan("Phase 3: Flake8 AST-Safe Fixer"))
    print(Color.cyan(f"{'=' * 60}"))
    print()

    if args.flake8_output:
        print(Color.cyan(f"Reading flake8 output from: {args.flake8_output}"))
        with open(args.flake8_output, 'r', encoding='utf-8') as f:
            raw_output = f.read()
    else:
        print(Color.magenta("Running flake8 ..."))
        raw_output = run_flake8(args.path, args.max_line_length, codes_to_fix)

    if not raw_output.strip():
        print(Color.green("No flake8 errors found. Nothing to fix."))
        return

    errors_by_file = parse_flake8_output(raw_output)

    total_errors = sum(len(errs) for errs in errors_by_file.values())
    print(Color.yellow(f"Found {total_errors} error(s) across {len(errors_by_file)} file(s)"))
    print()

    total_fixed = 0
    total_skipped = 0
    summary = defaultdict(int)

    for filepath in sorted(errors_by_file.keys()):
        if should_exclude_file(filepath, exclude_patterns):
            skipped = len(errors_by_file[filepath])
            total_skipped += skipped
            if args.verbose:
                print(Color.yellow(f"  EXCLUDED: {filepath} ({skipped} errors)"))
            continue

        if not os.path.isfile(filepath):
            if args.verbose:
                print(Color.red(f"  NOT FOUND: {filepath}"))
            continue

        errors = errors_by_file[filepath]

        try:
            original, modified, changes, file_has_bom = apply_fixes_to_file(
                filepath, errors, codes_to_fix, verbose=args.verbose
            )
        except Exception as e:
            print(Color.red(f"  ERROR processing {filepath}: {e}"))
            continue

        if original == modified:
            continue

        file_fixes = len(changes)
        total_fixed += file_fixes

        for _, code, _ in changes:
            summary[code] += 1

        print(Color.green(f"  {filepath}: {file_fixes} fix(es)"))

        if args.verbose:
            show_diff(filepath, original, modified, verbose=True)
            for lineno, code, desc in changes:
                print(f"    L{lineno} [{code}] {desc}")

        if not args.dry_run:
            if args.backup:
                shutil.copy2(filepath, filepath + ".bak")
            dir_name = os.path.dirname(os.path.abspath(filepath))
            fd, tmp_path = tempfile.mkstemp(
                dir=dir_name, suffix=".tmp", prefix=".flake8fix_",
            )
            try:
                write_encoding = 'utf-8-sig' if file_has_bom else 'utf-8'
                with os.fdopen(fd, 'w', encoding=write_encoding, newline='') as tmp_f:
                    tmp_f.write(modified)
                os.replace(tmp_path, filepath)
            except Exception:
                os.unlink(tmp_path)
                raise

    print()
    print(Color.cyan(f"{'=' * 60}"))
    print(Color.cyan("Summary"))
    print(Color.cyan(f"{'=' * 60}"))
    print(Color.yellow(f"Total errors found:    {total_errors}"))
    print(Color.green(f"Total fixes applied:   {total_fixed}"))
    print(Color.yellow(f"Total excluded/skipped: {total_skipped}"))
    print()

    if summary:
        print(Color.blue("Fixes by code:"))
        for code in sorted(summary.keys()):
            print(Color.green(f"  {code}: {summary[code]}"))
        print()

    remaining = total_errors - total_fixed - total_skipped
    if remaining > 0:
        print(Color.yellow(f"Remaining unfixed: {remaining} (may need manual review)"))

    if args.dry_run:
        print()
        print(Color.yellow("This was a DRY-RUN. No files were modified."))
        print(Color.yellow("Run with --apply to write changes to files."))
    else:
        print()
        print(Color.green("Changes have been written to files."))
        if args.backup:
            print(Color.green("Backup files (.bak) were created."))

    # --- Re-run flake8 to show ALL remaining errors (including manual-review codes) ---
    print()
    print(Color.cyan(f"{'=' * 60}"))
    print(Color.cyan("Remaining Errors (require manual fix)"))
    print(Color.cyan(f"{'=' * 60}"))
    print()

    remaining_cmd = [
        sys.executable, "-m", "flake8",
        "--format=default",
        f"--max-line-length={args.max_line_length}",
        f"--exclude={FLAKE8_EXCLUDE_DIRS}",
        "--jobs=auto",
        args.path,
    ]
    try:
        remaining_result = subprocess.run(remaining_cmd, capture_output=True, text=True, timeout=120)
        remaining_output = remaining_result.stdout.strip()
    except Exception:
        remaining_output = ""

    if not remaining_output:
        print(Color.green("No remaining flake8 errors. Codebase is clean!"))
    else:
        remaining_errors = parse_flake8_output(remaining_output)
        remaining_by_code = defaultdict(list)
        for filepath, errs in remaining_errors.items():
            for lineno, col, code, message in errs:
                remaining_by_code[code].append((filepath, lineno, col, message))

        manual_review_codes = {
            "F403": "star imports",
            "F405": "may be undefined (from star imports)",
            "F841": "unused local variable",
            "F811": "redefinition of unused",
            "E722": "bare except",
            "E501": "line too long",
            "E127": "continuation line over-indented",
            "E128": "continuation line under-indented",
            "E131": "continuation line unaligned",
            "E114": "indentation not a multiple of 4 (comment)",
            "E116": "unexpected indentation (comment)",
            "E225": "missing whitespace around operator",
            "E221": "multiple spaces before operator",
            "E201": "whitespace after '('",
        }

        total_remaining = sum(len(v) for v in remaining_by_code.values())
        print(Color.yellow(f"Total remaining errors: {total_remaining}"))
        print()

        for code in sorted(remaining_by_code.keys()):
            entries = remaining_by_code[code]
            desc = manual_review_codes.get(code, "")
            header = f"{code} — {desc}" if desc else code
            print(Color.magenta(f"  {header} ({len(entries)} errors):"))
            for filepath, lineno, col, message in entries:
                print(f"    {filepath}:{lineno}:{col} {message}")
            print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(Color.red("\nInterrupted by user"))
        sys.exit(130)
