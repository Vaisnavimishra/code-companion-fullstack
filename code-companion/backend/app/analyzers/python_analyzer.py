"""
Real static analysis for Python source code.

Layered approach:
1. `ast`/`compile` (stdlib, always available) — real syntax-error detection
   and an AST walk that finds genuine logic/quality/security/performance
   issues (mutable defaults, bare excepts, eval/exec, SQL string building,
   nested loops, missing docstrings, cyclomatic complexity, etc).
2. Optional external tools (`pyflakes`, `bandit`, `radon`) are invoked as
   subprocesses *when installed* to enrich the results with additional,
   independently-verified findings. If a tool isn't installed (e.g. the
   operator didn't `pip install` the optional extras) analysis still works
   using layer 1 — nothing ever hard-fails because a third-party tool is
   missing.

Every finding is a plain dict matching (a subset of) the `Finding` model
fields; the orchestrator assigns `id`/`agent`/`source`.
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

Finding = Dict[str, Any]

MAX_LINE_LENGTH = 100
LONG_FUNCTION_LINES = 50
HIGH_COMPLEXITY_THRESHOLD = 10

SECRET_PATTERN = re.compile(
    r"""(?i)\b(password|passwd|secret|api_key|apikey|access_key|token|auth)\b\s*=\s*['"][^'"\s]{3,}['"]"""
)
SQL_KEYWORDS = re.compile(r"(?i)\b(select|insert|update|delete|drop)\b.*\b(from|into|table)\b")


def _line_of(node: ast.AST) -> Optional[int]:
    return getattr(node, "lineno", None)


def _snippet(lines: List[str], lineno: Optional[int]) -> Optional[str]:
    if not lineno or lineno < 1 or lineno > len(lines):
        return None
    return lines[lineno - 1].strip()[:200]


class _ComplexityVisitor(ast.NodeVisitor):
    """A lightweight McCabe-style cyclomatic complexity counter."""

    def __init__(self) -> None:
        self.complexity = 1

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(
            node,
            (
                ast.If,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.Try,
                ast.ExceptHandler,
                ast.With,
                ast.AsyncWith,
                ast.BoolOp,
                ast.IfExp,
            ),
        ):
            self.complexity += 1
        if isinstance(node, ast.comprehension):
            self.complexity += 1 + len(node.ifs)
        super().generic_visit(node)


def _cyclomatic_complexity(fn: ast.AST) -> int:
    visitor = _ComplexityVisitor()
    visitor.visit(fn)
    return visitor.complexity


def _syntax_check(code: str, filename: str) -> Optional[Finding]:
    """Real syntax/compilation error detection via CPython's own compiler."""
    try:
        compile(code, filename, "exec", ast.PyCF_ONLY_AST)
    except SyntaxError as exc:
        return {
            "category": "syntax",
            "severity": "error",
            "line": exc.lineno,
            "column": exc.offset,
            "message": f"SyntaxError: {exc.msg}",
            "explanation": (
                "The Python interpreter cannot parse this source file. "
                "No further analysis can be performed until this is fixed."
            ),
            "suggestion": "Fix the syntax error indicated at the reported line/column.",
            "rule": "python-syntax-error",
        }
    except (ValueError, TypeError) as exc:  # e.g. null bytes
        return {
            "category": "syntax",
            "severity": "error",
            "line": None,
            "message": f"Compilation error: {exc}",
            "suggestion": "Ensure the file contains valid, UTF-8 Python source.",
            "rule": "python-compile-error",
        }
    return None


def _walk_ast_checks(tree: ast.AST, lines: List[str]) -> List[Finding]:
    findings: List[Finding] = []

    class_stack: List[str] = []
    imported_names: Dict[str, int] = {}
    used_names: set = set()

    for node in ast.walk(tree):
        # ---- Imports (for unused-import detection) ----
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = (alias.asname or alias.name).split(".")[0]
                imported_names[name] = _line_of(node)
        elif isinstance(node, ast.ImportFrom):
            if node.module and any(alias.name == "*" for alias in node.names):
                findings.append(
                    {
                        "category": "quality",
                        "severity": "warning",
                        "line": _line_of(node),
                        "message": f"Wildcard import from '{node.module}'",
                        "explanation": "Wildcard imports pollute the namespace and make it hard to trace where names come from.",
                        "suggestion": f"Import only the specific names you need from '{node.module}'.",
                        "rule": "wildcard-import",
                    }
                )
            for alias in node.names:
                if alias.name == "*":
                    continue
                name = (alias.asname or alias.name).split(".")[0]
                imported_names[name] = _line_of(node)
        elif isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            base = node
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name):
                used_names.add(base.id)

        # ---- eval/exec/pickle/shell=True/yaml.load (security) ----
        if isinstance(node, ast.Call):
            fn_name = None
            if isinstance(node.func, ast.Name):
                fn_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fn_name = node.func.attr

            if fn_name in ("eval", "exec"):
                findings.append(
                    {
                        "category": "security",
                        "severity": "error",
                        "line": _line_of(node),
                        "message": f"Use of `{fn_name}()` on potentially untrusted input",
                        "explanation": f"`{fn_name}()` executes arbitrary code and is a common source of remote code execution vulnerabilities.",
                        "suggestion": "Avoid eval/exec. Use `ast.literal_eval` for data, or a proper parser/dispatch table.",
                        "rule": f"python-{fn_name}-usage",
                        "code_snippet": _snippet(lines, _line_of(node)),
                    }
                )
            if fn_name == "loads" and isinstance(node.func, ast.Attribute):
                mod = node.func.value
                if isinstance(mod, ast.Name) and mod.id == "pickle":
                    findings.append(
                        {
                            "category": "security",
                            "severity": "error",
                            "line": _line_of(node),
                            "message": "Untrusted deserialization via `pickle.loads`",
                            "explanation": "Unpickling data from an untrusted source can lead to arbitrary code execution.",
                            "suggestion": "Use `json` for data interchange, or validate/sign the payload before unpickling.",
                            "rule": "python-insecure-deserialization",
                        }
                    )
            if fn_name == "load" and isinstance(node.func, ast.Attribute):
                mod = node.func.value
                if isinstance(mod, ast.Name) and mod.id == "yaml":
                    has_safe_loader = any(
                        isinstance(kw.value, ast.Attribute) and kw.value.attr in ("SafeLoader", "CSafeLoader")
                        for kw in node.keywords
                    )
                    if not has_safe_loader:
                        findings.append(
                            {
                                "category": "security",
                                "severity": "warning",
                                "line": _line_of(node),
                                "message": "`yaml.load()` without a safe loader",
                                "explanation": "The default YAML loader can instantiate arbitrary Python objects from the input.",
                                "suggestion": "Use `yaml.safe_load(data)` instead.",
                                "rule": "python-yaml-unsafe-load",
                            }
                        )
            # subprocess shell=True
            if fn_name in ("call", "run", "Popen", "check_output", "check_call"):
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        findings.append(
                            {
                                "category": "security",
                                "severity": "error",
                                "line": _line_of(node),
                                "message": "`subprocess` call with `shell=True`",
                                "explanation": "Running a shell with untrusted input can lead to shell/command injection.",
                                "suggestion": "Pass a list of arguments and use `shell=False` (the default).",
                                "rule": "python-subprocess-shell-true",
                            }
                        )
            # os.system
            if isinstance(node.func, ast.Attribute) and node.func.attr == "system":
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                    findings.append(
                        {
                            "category": "security",
                            "severity": "warning",
                            "line": _line_of(node),
                            "message": "`os.system()` call detected",
                            "explanation": "Shelling out via os.system with interpolated input is a common injection vector.",
                            "suggestion": "Prefer `subprocess.run([...], shell=False)` with a fixed argument list.",
                            "rule": "python-os-system",
                        }
                    )
            # cursor.execute with an f-string / % / + built query -> possible SQL injection
            if fn_name == "execute" and node.args:
                first_arg = node.args[0]
                looks_dynamic = isinstance(first_arg, (ast.JoinedStr, ast.BinOp))
                if looks_dynamic:
                    findings.append(
                        {
                            "category": "security",
                            "severity": "error",
                            "line": _line_of(node),
                            "message": "Possible SQL injection: query string built with concatenation/f-string",
                            "explanation": "Building SQL by joining strings with user-controlled data allows attackers to alter query logic.",
                            "suggestion": "Use parameterized queries, e.g. cursor.execute('...WHERE id=%s', (id,)).",
                            "rule": "python-sql-injection",
                            "code_snippet": _snippet(lines, _line_of(node)),
                        }
                    )
            # print() usage
            if fn_name == "print":
                findings.append(
                    {
                        "category": "quality",
                        "severity": "info",
                        "line": _line_of(node),
                        "message": "`print()` statement found",
                        "suggestion": "Use the `logging` module instead of `print()` in production code.",
                        "rule": "python-print-statement",
                    }
                )

        # ---- SQL string built via concatenation/f-string and assigned to a variable ----
        if isinstance(node, ast.Assign) and isinstance(node.value, (ast.BinOp, ast.JoinedStr)):
            text_repr = ast.dump(node.value)
            joined_str_vals = [
                c.value for c in ast.walk(node.value) if isinstance(c, ast.Constant) and isinstance(c.value, str)
            ]
            combined_text = " ".join(joined_str_vals)
            if SQL_KEYWORDS.search(combined_text):
                findings.append(
                    {
                        "category": "security",
                        "severity": "error",
                        "line": _line_of(node),
                        "message": "SQL query string built via concatenation/f-string",
                        "explanation": "Interpolating values directly into SQL text allows attackers to alter query logic (SQL injection).",
                        "suggestion": "Use parameterized queries instead of building SQL with string concatenation.",
                        "rule": "python-sql-injection",
                        "code_snippet": _snippet(lines, _line_of(node)),
                    }
                )

        # ---- global keyword ----
        if isinstance(node, ast.Global):
            findings.append(
                {
                    "category": "quality",
                    "severity": "warning",
                    "line": _line_of(node),
                    "message": f"`global` keyword used for: {', '.join(node.names)}",
                    "explanation": "Mutable global state makes code harder to test and reason about.",
                    "suggestion": "Pass values as function parameters / return values instead of mutating globals.",
                    "rule": "python-global-statement",
                }
            )

        # ---- bare except / broad except ----
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                findings.append(
                    {
                        "category": "logic",
                        "severity": "error",
                        "line": _line_of(node),
                        "message": "Bare `except:` clause",
                        "explanation": "Catches every exception including SystemExit/KeyboardInterrupt, silently hiding bugs.",
                        "suggestion": "Catch specific exception types, e.g. `except ValueError:`.",
                        "rule": "python-bare-except",
                    }
                )
            elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                findings.append(
                    {
                        "category": "logic",
                        "severity": "warning",
                        "line": _line_of(node),
                        "message": "Overly broad `except Exception:` clause",
                        "explanation": "Catching the base Exception class can mask programming errors.",
                        "suggestion": "Catch the narrowest exception type that can actually occur.",
                        "rule": "python-broad-except",
                    }
                )
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                findings.append(
                    {
                        "category": "logic",
                        "severity": "warning",
                        "line": _line_of(node),
                        "message": "Exception silently swallowed (`except: pass`)",
                        "explanation": "Errors are discarded with no logging, making failures invisible.",
                        "suggestion": "At minimum log the exception, e.g. `logging.exception(...)`.",
                        "rule": "python-empty-except",
                    }
                )

        # ---- mutable default arguments ----
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defaults = list(node.args.defaults) + list(node.args.kw_defaults)
            for default in defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    findings.append(
                        {
                            "category": "logic",
                            "severity": "error",
                            "line": _line_of(node),
                            "message": f"Mutable default argument in `{node.name}()`",
                            "explanation": "Default arguments are evaluated once; a mutable default is shared and mutated across calls.",
                            "suggestion": "Use `None` as the default and initialize the mutable value inside the function body.",
                            "rule": "python-mutable-default-arg",
                        }
                    )

            # complexity / length
            complexity = _cyclomatic_complexity(node)
            end_line = getattr(node, "end_lineno", node.lineno)
            length = end_line - node.lineno + 1
            if complexity > HIGH_COMPLEXITY_THRESHOLD:
                findings.append(
                    {
                        "category": "quality",
                        "severity": "warning",
                        "line": _line_of(node),
                        "message": f"`{node.name}()` has high cyclomatic complexity ({complexity})",
                        "explanation": "High complexity functions are harder to test and more error-prone.",
                        "suggestion": "Break the function into smaller, single-purpose helpers.",
                        "rule": "python-high-complexity",
                    }
                )
            if length > LONG_FUNCTION_LINES:
                findings.append(
                    {
                        "category": "quality",
                        "severity": "info",
                        "line": _line_of(node),
                        "message": f"`{node.name}()` is {length} lines long",
                        "suggestion": f"Consider splitting functions longer than {LONG_FUNCTION_LINES} lines into smaller units.",
                        "rule": "python-long-function",
                    }
                )
            # missing docstring for "public" functions
            is_dunder = node.name.startswith("__") and node.name.endswith("__")
            if not node.name.startswith("_") and not is_dunder:
                has_docstring = (
                    len(node.body) > 0
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(getattr(node.body[0], "value", None), ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                )
                if not has_docstring:
                    findings.append(
                        {
                            "category": "quality",
                            "severity": "info",
                            "line": _line_of(node),
                            "message": f"`{node.name}()` is missing a docstring",
                            "suggestion": f'Add a docstring describing what `{node.name}` does, its parameters, and return value.',
                            "rule": "python-missing-docstring",
                        }
                    )

            # recursion without memoization
            calls_self = any(
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == node.name
                for n in ast.walk(node)
            )
            if calls_self:
                decorator_names = {
                    (d.id if isinstance(d, ast.Name) else getattr(d, "attr", ""))
                    for d in node.decorator_list
                }
                has_memo = bool(decorator_names & {"lru_cache", "cache", "cached_property"})
                if not has_memo:
                    findings.append(
                        {
                            "category": "performance",
                            "severity": "warning",
                            "line": _line_of(node),
                            "message": f"Recursive function `{node.name}()` has no memoization",
                            "explanation": "Unmemoized recursion (e.g. naive Fibonacci) can be exponential time.",
                            "suggestion": "Add `@functools.lru_cache` or convert to an iterative/DP implementation.",
                            "rule": "python-unmemoized-recursion",
                        }
                    )

        # ---- nested loops (O(n^2)+) ----
        if isinstance(node, (ast.For, ast.While)):
            for inner in ast.walk(node):
                if inner is not node and isinstance(inner, (ast.For, ast.While)):
                    findings.append(
                        {
                            "category": "performance",
                            "severity": "warning",
                            "line": _line_of(node),
                            "message": "Nested loop detected (potential O(n\u00b2) or worse)",
                            "explanation": "Loops nested inside loops often indicate quadratic (or worse) time complexity.",
                            "suggestion": "Consider a hash map/set lookup, sorting, or a different algorithm to avoid nested iteration.",
                            "rule": "python-nested-loop",
                        }
                    )
                    break

        # ---- string concatenation in a loop body (rough heuristic via AugAssign) ----
        if isinstance(node, (ast.For, ast.While)):
            for inner in ast.walk(node):
                if isinstance(inner, ast.AugAssign) and isinstance(inner.op, ast.Add):
                    findings.append(
                        {
                            "category": "performance",
                            "severity": "info",
                            "line": _line_of(inner),
                            "message": "String/list accumulation with `+=` inside a loop",
                            "suggestion": "Prefer `''.join(...)` for strings or a list comprehension for building sequences.",
                            "rule": "python-loop-accumulation",
                        }
                    )

    # unused imports
    for name, line in imported_names.items():
        if name not in used_names and name != "*":
            findings.append(
                {
                    "category": "quality",
                    "severity": "info",
                    "line": line,
                    "message": f"Imported name `{name}` appears unused",
                    "suggestion": f"Remove the unused import `{name}` or use it.",
                    "rule": "python-unused-import",
                }
            )

    return findings


def _line_level_checks(code: str, lines: List[str]) -> List[Finding]:
    findings: List[Finding] = []
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if len(line) > MAX_LINE_LENGTH:
            findings.append(
                {
                    "category": "quality",
                    "severity": "info",
                    "line": i,
                    "message": f"Line exceeds {MAX_LINE_LENGTH} characters ({len(line)})",
                    "suggestion": "Break the line up for readability (PEP 8 recommends <= 79-100 chars).",
                    "rule": "python-line-too-long",
                }
            )
        if re.search(r"#.*\b(TODO|FIXME|HACK|XXX)\b", line, re.IGNORECASE):
            findings.append(
                {
                    "category": "quality",
                    "severity": "info",
                    "line": i,
                    "message": "TODO/FIXME/HACK comment found",
                    "suggestion": "Track this in your issue tracker or resolve it before shipping.",
                    "rule": "python-todo-comment",
                }
            )
        if re.search(r"\s+$", line) and stripped:
            findings.append(
                {
                    "category": "quality",
                    "severity": "info",
                    "line": i,
                    "message": "Trailing whitespace",
                    "suggestion": "Remove trailing whitespace.",
                    "rule": "python-trailing-whitespace",
                }
            )
        if SECRET_PATTERN.search(line) and not stripped.startswith("#"):
            findings.append(
                {
                    "category": "security",
                    "severity": "error",
                    "line": i,
                    "message": "Possible hardcoded credential/secret",
                    "explanation": "Secrets committed to source code can leak via version control history.",
                    "suggestion": "Load secrets from environment variables or a secrets manager instead.",
                    "rule": "python-hardcoded-secret",
                }
            )
        if "while true" in stripped.lower().replace(" ", "") or re.match(r"while\s+True\s*:", stripped):
            has_break_nearby = any("break" in l for l in lines[i : min(i + 30, len(lines))])
            findings.append(
                {
                    "category": "logic",
                    "severity": "warning" if has_break_nearby else "error",
                    "line": i,
                    "message": "`while True:` loop detected",
                    "suggestion": "Verify a `break`/`return` always exits the loop under expected conditions."
                    if has_break_nearby
                    else "No nearby `break` found — this loop may never terminate.",
                    "rule": "python-infinite-loop",
                }
            )
    return findings


# ──────────────────────────────────────────────────────────────
# Optional external tools (used only if installed)
# ──────────────────────────────────────────────────────────────

def _run_pyflakes(filepath: str, timeout: float) -> List[Finding]:
    """Real, independent unused-variable/undefined-name analysis via pyflakes."""
    if shutil.which("pyflakes") is None:
        try:
            import pyflakes  # noqa: F401
        except ImportError:
            return []
        cmd = [sys.executable, "-m", "pyflakes", filepath]
    else:
        cmd = ["pyflakes", filepath]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return []

    findings: List[Finding] = []
    pattern = re.compile(r"^.*?:(\d+):(?:(\d+):)?\s*(.+)$")
    for raw in (proc.stdout or "").splitlines():
        m = pattern.match(raw)
        if not m:
            continue
        line_no, col, message = m.groups()
        severity = "warning"
        if "undefined name" in message.lower():
            severity = "error"
        findings.append(
            {
                "category": "logic",
                "severity": severity,
                "line": int(line_no),
                "column": int(col) if col else None,
                "message": message.strip(),
                "suggestion": "Review the reported name/import for typos or dead code.",
                "rule": "pyflakes",
                "tool": "pyflakes",
            }
        )
    return findings


def _run_bandit(filepath: str, timeout: float) -> List[Finding]:
    """Real security analysis via bandit, when installed."""
    if shutil.which("bandit") is None:
        return []
    try:
        proc = subprocess.run(
            ["bandit", "-f", "json", "-q", filepath],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        data = json.loads(proc.stdout or "{}")
    except Exception:
        return []

    severity_map = {"LOW": "info", "MEDIUM": "warning", "HIGH": "error"}
    findings: List[Finding] = []
    for issue in data.get("results", []):
        findings.append(
            {
                "category": "security",
                "severity": severity_map.get(issue.get("issue_severity", "MEDIUM"), "warning"),
                "line": issue.get("line_number"),
                "message": issue.get("issue_text", "Security issue detected"),
                "explanation": f"Bandit rule {issue.get('test_id')} ({issue.get('test_name')}), confidence: {issue.get('issue_confidence')}",
                "suggestion": "See the Bandit documentation for the specific rule for remediation guidance.",
                "rule": f"bandit-{issue.get('test_id', '')}",
                "tool": "bandit",
            }
        )
    return findings


def _run_radon(filepath: str, timeout: float) -> List[Finding]:
    """Real cyclomatic-complexity analysis via radon, when installed (cross-check)."""
    if shutil.which("radon") is None:
        return []
    try:
        proc = subprocess.run(
            ["radon", "cc", "-j", filepath], capture_output=True, text=True, timeout=timeout
        )
        data = json.loads(proc.stdout or "{}")
    except Exception:
        return []

    findings: List[Finding] = []
    for _, blocks in data.items():
        for block in blocks:
            rank = block.get("rank", "A")
            if rank in ("D", "E", "F"):
                findings.append(
                    {
                        "category": "quality",
                        "severity": "warning" if rank == "D" else "error",
                        "line": block.get("lineno"),
                        "message": f"radon: `{block.get('name')}` complexity rank {rank} (score {block.get('complexity')})",
                        "suggestion": "Refactor into smaller functions to reduce complexity.",
                        "rule": "radon-complexity",
                        "tool": "radon",
                    }
                )
    return findings


def analyze(code: str, timeout: float = 8.0) -> List[Finding]:
    """Run the full Python analysis pipeline and return a flat finding list."""
    lines = code.splitlines()
    findings: List[Finding] = []

    syntax_error = _syntax_check(code, "<submitted_code>")
    if syntax_error:
        # Nothing else can safely run against unparsable code.
        return [syntax_error]

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:  # pragma: no cover - defensive, already checked above
        return [
            {
                "category": "syntax",
                "severity": "error",
                "line": exc.lineno,
                "message": f"SyntaxError: {exc.msg}",
                "rule": "python-syntax-error",
            }
        ]

    findings.extend(_walk_ast_checks(tree, lines))
    findings.extend(_line_level_checks(code, lines))

    # External tools operate on an actual file on disk.
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name
    try:
        findings.extend(_run_pyflakes(tmp_path, timeout))
        findings.extend(_run_bandit(tmp_path, timeout))
        findings.extend(_run_radon(tmp_path, timeout))
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return findings


def build_documentation_notes(code: str) -> str:
    """Human-readable documentation coverage summary (used by the Docs tab)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return "Documentation analysis skipped: file has a syntax error."

    notes: List[str] = []
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]

    def has_doc(node: ast.AST) -> bool:
        return bool(ast.get_docstring(node))

    module_doc = ast.get_docstring(tree)
    notes.append("✓ Module has a top-level docstring." if module_doc else "⚠ No module-level docstring found.")

    documented_fns = [f for f in functions if has_doc(f)]
    if functions:
        notes.append(
            f"{'✓' if len(documented_fns) == len(functions) else '⚠'} "
            f"{len(documented_fns)}/{len(functions)} function(s) have docstrings."
        )
    else:
        notes.append("ℹ No function definitions found.")

    documented_classes = [c for c in classes if has_doc(c)]
    if classes:
        notes.append(
            f"{'✓' if len(documented_classes) == len(classes) else '⚠'} "
            f"{len(documented_classes)}/{len(classes)} class(es) have docstrings."
        )

    missing = [f.name for f in functions if not has_doc(f)]
    if missing:
        sample = ", ".join(missing[:8])
        notes.append(f"\nFunctions missing docstrings: {sample}{' ...' if len(missing) > 8 else ''}")

    return "\n\n".join(notes)


def generate_fixed_code(code: str, findings: List[Finding]) -> str:
    """
    Apply a conservative set of safe, mechanical auto-fixes.
    This intentionally only rewrites patterns that are unambiguous —
    it is not a full auto-repair tool.
    """
    fixed = code
    # Strip trailing whitespace on every line.
    fixed = "\n".join(line.rstrip() for line in fixed.split("\n"))
    return fixed
