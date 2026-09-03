from __future__ import annotations

import os
import re
import subprocess
import tempfile
from typing import Dict, List, Optional


Finding = Dict[str, object]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_strings_and_comments(code: str) -> str:
    """
    Remove Java comments and string/character contents while preserving
    line structure. This makes heuristic checks less likely to match text
    inside comments or string literals.
    """
    result: List[str] = []

    i = 0
    n = len(code)

    in_line_comment = False
    in_block_comment = False
    in_string = False
    in_char = False
    escaped = False

    while i < n:
        ch = code[i]
        nxt = code[i + 1] if i + 1 < n else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                result.append("\n")
            else:
                result.append(" ")
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                result.append(" ")
                result.append(" ")
                i += 2
                in_block_comment = False
            elif ch == "\n":
                result.append("\n")
                i += 1
            else:
                result.append(" ")
                i += 1
            continue

        if in_string:
            if escaped:
                escaped = False
                result.append(" ")
            elif ch == "\\":
                escaped = True
                result.append(" ")
            elif ch == '"':
                in_string = False
                result.append(" ")
            elif ch == "\n":
                in_string = False
                result.append("\n")
            else:
                result.append(" ")
            i += 1
            continue

        if in_char:
            if escaped:
                escaped = False
                result.append(" ")
            elif ch == "\\":
                escaped = True
                result.append(" ")
            elif ch == "'":
                in_char = False
                result.append(" ")
            elif ch == "\n":
                in_char = False
                result.append("\n")
            else:
                result.append(" ")
            i += 1
            continue

        if ch == "/" and nxt == "/":
            result.append(" ")
            result.append(" ")
            i += 2
            in_line_comment = True
            continue

        if ch == "/" and nxt == "*":
            result.append(" ")
            result.append(" ")
            i += 2
            in_block_comment = True
            continue

        if ch == '"':
            in_string = True
            result.append(" ")
            i += 1
            continue

        if ch == "'":
            in_char = True
            result.append(" ")
            i += 1
            continue

        result.append(ch)
        i += 1

    return "".join(result)


def _finding(
    category: str,
    severity: str,
    line: int,
    message: str,
    suggestion: str,
    rule: str,
) -> Finding:
    return {
        "category": category,
        "severity": severity,
        "line": line,
        "message": message,
        "suggestion": suggestion,
        "rule": rule,
    }


# ---------------------------------------------------------------------------
# javac integration
# ---------------------------------------------------------------------------

def _run_javac(code: str, timeout: float = 8.0) -> Optional[List[Finding]]:
    """
    Compile Java source with javac when available.

    Returns:
        []              -> javac available and compilation succeeded
        findings        -> javac available but compilation failed
        None            -> javac unavailable
    """
    try:
        subprocess.run(
            ["javac", "-version"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None

    temp_dir = tempfile.mkdtemp(prefix="codeagent_java_")
    java_file = os.path.join(temp_dir, "Main.java")

    try:
        with open(java_file, "w", encoding="utf-8") as f:
            f.write(code)

        process = subprocess.run(
            ["javac", java_file],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=temp_dir,
            check=False,
        )

        if process.returncode == 0:
            return []

        output = (process.stderr or process.stdout or "").strip()

        findings: List[Finding] = []

        if not output:
            findings.append(
                _finding(
                    "syntax",
                    "error",
                    1,
                    "Java compilation failed.",
                    "Fix the compilation error and try again.",
                    "javac",
                )
            )
            return findings

        # javac usually emits:
        # Main.java:5: error: ...
        pattern = re.compile(
            r"(?:.*?\.java:)?(\d+):\s*(?:error|warning):\s*(.*)"
        )

        matched = False

        for match in pattern.finditer(output):
            matched = True
            line = int(match.group(1))
            message = match.group(2).strip()

            severity = (
                "error"
                if "error:" in match.group(0).lower()
                else "warning"
            )

            findings.append(
                _finding(
                    "syntax",
                    severity,
                    line,
                    message,
                    "Fix the javac diagnostic before continuing.",
                    "javac",
                )
            )

        if not matched:
            first_line = output.splitlines()[0]
            findings.append(
                _finding(
                    "syntax",
                    "error",
                    1,
                    first_line,
                    "Fix the Java compilation error.",
                    "javac",
                )
            )

        return findings

    except subprocess.TimeoutExpired:
        return [
            _finding(
                "syntax",
                "warning",
                1,
                "Java compilation timed out.",
                "Check the source for unusually expensive compilation behavior.",
                "javac-timeout",
            )
        ]

    except (OSError, UnicodeError):
        return None

    finally:
        try:
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for name in files:
                    try:
                        os.remove(os.path.join(root, name))
                    except OSError:
                        pass

                for name in dirs:
                    try:
                        os.rmdir(os.path.join(root, name))
                    except OSError:
                        pass

            os.rmdir(temp_dir)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Syntax heuristics
# ---------------------------------------------------------------------------

def _check_balance(clean: str) -> List[Finding]:
    findings: List[Finding] = []

    brace_balance = 0
    paren_balance = 0
    bracket_balance = 0

    lines = clean.splitlines()

    for i, line in enumerate(lines, start=1):
        brace_balance += line.count("{")
        brace_balance -= line.count("}")

        paren_balance += line.count("(")
        paren_balance -= line.count(")")

        bracket_balance += line.count("[")
        bracket_balance -= line.count("]")

        if brace_balance < 0:
            findings.append(
                _finding(
                    "syntax",
                    "error",
                    i,
                    "Unexpected closing brace.",
                    "Check the placement of `{` and `}`.",
                    "java-brace-balance",
                )
            )
            brace_balance = 0

        if paren_balance < 0:
            findings.append(
                _finding(
                    "syntax",
                    "error",
                    i,
                    "Unexpected closing parenthesis.",
                    "Check the placement of `(` and `)`.",
                    "java-parenthesis-balance",
                )
            )
            paren_balance = 0

        if bracket_balance < 0:
            findings.append(
                _finding(
                    "syntax",
                    "error",
                    i,
                    "Unexpected closing bracket.",
                    "Check the placement of `[` and `]`.",
                    "java-bracket-balance",
                )
            )
            bracket_balance = 0

    if brace_balance > 0:
        findings.append(
            _finding(
                "syntax",
                "error",
                len(lines),
                "Unclosed `{` brace detected.",
                "Add the missing closing brace.",
                "java-brace-balance",
            )
        )

    if paren_balance > 0:
        findings.append(
            _finding(
                "syntax",
                "error",
                len(lines),
                "Unclosed `(` parenthesis detected.",
                "Add the missing closing parenthesis.",
                "java-parenthesis-balance",
            )
        )

    if bracket_balance > 0:
        findings.append(
            _finding(
                "syntax",
                "error",
                len(lines),
                "Unclosed `[` bracket detected.",
                "Add the missing closing bracket.",
                "java-bracket-balance",
            )
        )

    return findings


def _heuristic_syntax_checks(
    code: str,
    clean: str,
    lines: List[str],
) -> List[Finding]:
    findings: List[Finding] = []

    findings.extend(_check_balance(clean))

    for i, line in enumerate(lines, start=1):
        stripped = clean.splitlines()[i - 1].strip()

        if not stripped:
            continue

        # Basic missing semicolon heuristic.
        if (
            re.match(
                r"^(?:int|long|double|float|boolean|char|String|var)"
                r"\s+\w+\s*=.*$",
                stripped,
            )
            and not stripped.endswith(";")
        ):
            findings.append(
                _finding(
                    "syntax",
                    "error",
                    i,
                    "Possible missing semicolon.",
                    "Terminate the statement with `;`.",
                    "java-missing-semicolon",
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Rule-based analysis
# ---------------------------------------------------------------------------

def _rule_based_checks(
    code: str,
    clean: str,
    lines: List[str],
) -> List[Finding]:
    findings: List[Finding] = []

    clean_lines = clean.splitlines()

    # -----------------------------------------------------------------------
    # Line length
    # -----------------------------------------------------------------------

    for i, line in enumerate(lines, start=1):
        if len(line) > 120:
            findings.append(
                _finding(
                    "quality",
                    "warning",
                    i,
                    "Line is longer than 120 characters.",
                    "Break the line into smaller, readable expressions.",
                    "java-long-line",
                )
            )

    # -----------------------------------------------------------------------
    # TODO / FIXME / HACK / XXX
    # -----------------------------------------------------------------------

    for i, line in enumerate(lines, start=1):
        if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", line, re.IGNORECASE):
            findings.append(
                _finding(
                    "quality",
                    "info",
                    i,
                    "Development marker found in the source.",
                    "Resolve the marker before production if it represents unfinished work.",
                    "java-todo-marker",
                )
            )

    # -----------------------------------------------------------------------
    # System.out.print
    # -----------------------------------------------------------------------

    for i, stripped in enumerate(clean_lines, start=1):
        if re.search(r"\bSystem\.out\.print(?:ln)?\s*\(", stripped):
            findings.append(
                _finding(
                    "quality",
                    "warning",
                    i,
                    "Direct console output detected.",
                    "Use a proper logging framework instead of System.out.",
                    "java-system-out",
                )
            )

    # -----------------------------------------------------------------------
    # Broad catch
    # -----------------------------------------------------------------------

    for i, stripped in enumerate(clean_lines, start=1):
        if re.search(
            r"catch\s*\(\s*Exception\s+\w+\s*\)",
            stripped,
        ):
            findings.append(
                _finding(
                    "logic",
                    "warning",
                    i,
                    "Catching generic `Exception`.",
                    "Catch the most specific exception type(s) that can actually be thrown.",
                    "java-broad-catch",
                )
            )

    # -----------------------------------------------------------------------
    # EMPTY CATCH BLOCK
    #
    # Handles both:
    #
    # catch (Exception e) {}
    #
    # and:
    #
    # catch (Exception e) {
    # }
    # -----------------------------------------------------------------------

    for i, stripped in enumerate(clean_lines, start=1):
        catch_match = re.search(
            r"catch\s*\([^)]*\)\s*\{",
            stripped,
        )

        if not catch_match:
            continue

        # Same-line empty catch:
        #
        # catch (...) {}
        #
        if re.search(
            r"catch\s*\([^)]*\)\s*\{\s*\}",
            stripped,
        ):
            findings.append(
                _finding(
                    "logic",
                    "warning",
                    i,
                    "Empty catch block swallows the exception.",
                    "At minimum log the caught exception.",
                    "java-empty-catch",
                )
            )
            continue

        # Multiline empty catch:
        #
        # catch (...) {
        # }
        #
        depth = 0
        has_content = False

        for j in range(i - 1, len(clean_lines)):
            current = clean_lines[j]

            depth += current.count("{")
            depth -= current.count("}")

            # Ignore the catch declaration itself.
            if j > i - 1:
                content = current.strip()

                if content and content != "}":
                    has_content = True
                    break

            # Catch block is closed.
            if j > i - 1 and depth == 0:
                break

        if not has_content and depth == 0:
            findings.append(
                _finding(
                    "logic",
                    "warning",
                    i,
                    "Empty catch block swallows the exception.",
                    "At minimum log the caught exception.",
                    "java-empty-catch",
                )
            )

    # -----------------------------------------------------------------------
    # String comparison with ==
    # -----------------------------------------------------------------------

    for i, stripped in enumerate(clean_lines, start=1):
        if re.search(
            r"\bString\s+\w+.*|",
            "",
        ):
            pass

        if re.search(
            r"\b\w+\s*==\s*\"[^\"\\]*(?:\\.[^\"\\]*)*\"",
            stripped,
        ) or re.search(
            r"\"[^\"\\]*(?:\\.[^\"\\]*)*\"\s*==\s*\w+",
            stripped,
        ):
            findings.append(
                _finding(
                    "logic",
                    "warning",
                    i,
                    "String comparison using `==`.",
                    "Use `.equals()` or `Objects.equals()` for String value comparison.",
                    "java-string-equals",
                )
            )

    # -----------------------------------------------------------------------
    # Resource leaks
    # -----------------------------------------------------------------------

    for i, stripped in enumerate(clean_lines, start=1):
        if re.search(
            r"\bnew\s+(FileInputStream|FileOutputStream|"
            r"BufferedReader|BufferedWriter|"
            r"InputStreamReader|OutputStreamWriter)\s*\(",
            stripped,
        ):
            findings.append(
                _finding(
                    "quality",
                    "warning",
                    i,
                    "Potential resource leak detected.",
                    "Prefer try-with-resources so the resource is closed automatically.",
                    "java-resource-leak",
                )
            )

    # -----------------------------------------------------------------------
    # Command injection
    # -----------------------------------------------------------------------

    for i, stripped in enumerate(clean_lines, start=1):
        if re.search(
            r"Runtime\.getRuntime\(\)\.exec\s*\(",
            stripped,
        ):
            findings.append(
                _finding(
                    "security",
                    "error",
                    i,
                    "Runtime command execution detected.",
                    "Avoid passing untrusted input to OS commands and prefer safe APIs.",
                    "java-command-injection",
                )
            )

    # -----------------------------------------------------------------------
    # SQL injection
    # -----------------------------------------------------------------------

    for i, stripped in enumerate(clean_lines, start=1):
        if re.search(
            r"(Statement|PreparedStatement).*execute(?:Query|Update)?\s*\(",
            stripped,
        ) and "+" in stripped:
            findings.append(
                _finding(
                    "security",
                    "error",
                    i,
                    "Possible SQL injection through string concatenation.",
                    "Use parameterized PreparedStatement queries.",
                    "java-sql-injection",
                )
            )

    # -----------------------------------------------------------------------
    # Weak hashing
    # -----------------------------------------------------------------------

    for i, stripped in enumerate(clean_lines, start=1):
        if re.search(
            r'MessageDigest\.getInstance\s*\(\s*["\'](?:MD5|SHA-1)["\']',
            stripped,
            re.IGNORECASE,
        ):
            findings.append(
                _finding(
                    "security",
                    "warning",
                    i,
                    "Weak cryptographic hash algorithm detected.",
                    "Use a modern cryptographic hash such as SHA-256 or stronger.",
                    "java-weak-hash",
                )
            )

    # -----------------------------------------------------------------------
    # Insecure random
    # -----------------------------------------------------------------------

    for i, stripped in enumerate(clean_lines, start=1):
        if re.search(r"\bnew\s+Random\s*\(", stripped):
            findings.append(
                _finding(
                    "security",
                    "warning",
                    i,
                    "Non-cryptographic random generator detected.",
                    "Use SecureRandom when randomness is security-sensitive.",
                    "java-insecure-random",
                )
            )

    # -----------------------------------------------------------------------
    # Hardcoded secrets
    # -----------------------------------------------------------------------

    for i, stripped in enumerate(lines, start=1):
        if re.search(
            r"\b(password|passwd|secret|api[_-]?key|token)\b"
            r"\s*=\s*['\"][^'\"]{6,}['\"]",
            stripped,
            re.IGNORECASE,
        ):
            findings.append(
                _finding(
                    "security",
                    "error",
                    i,
                    "Possible hardcoded secret detected.",
                    "Move secrets to environment variables or a secure secret manager.",
                    "java-hardcoded-secret",
                )
            )

    # -----------------------------------------------------------------------
    # Unsafe Java deserialization
    # -----------------------------------------------------------------------

    for i, stripped in enumerate(clean_lines, start=1):
        if "ObjectInputStream" in stripped:
            findings.append(
                _finding(
                    "security",
                    "warning",
                    i,
                    "Java object deserialization detected.",
                    "Avoid deserializing untrusted data with ObjectInputStream.",
                    "java-unsafe-deserialization",
                )
            )

    # -----------------------------------------------------------------------
    # while(true)
    # -----------------------------------------------------------------------

    for i, stripped in enumerate(clean_lines, start=1):
        if re.search(r"\bwhile\s*\(\s*true\s*\)", stripped):
            findings.append(
                _finding(
                    "performance",
                    "warning",
                    i,
                    "Unbounded `while(true)` loop detected.",
                    "Ensure the loop has a clear termination condition.",
                    "java-infinite-loop",
                )
            )

    # -----------------------------------------------------------------------
    # Nested loops
    # -----------------------------------------------------------------------

    loop_stack: List[int] = []

    for i, stripped in enumerate(clean_lines, start=1):
        if re.search(r"\b(for|while)\s*\(", stripped):
            if loop_stack:
                findings.append(
                    _finding(
                        "performance",
                        "warning",
                        i,
                        "Nested loop detected.",
                        "Check whether the algorithm can be optimized to avoid unnecessary O(n²) or worse work.",
                        "java-nested-loops",
                    )
                )

            loop_stack.append(i)

        if "}" in stripped and loop_stack:
            close_count = stripped.count("}")
            for _ in range(min(close_count, len(loop_stack))):
                loop_stack.pop()

    # -----------------------------------------------------------------------
    # String concatenation inside loops
    # -----------------------------------------------------------------------

    inside_loop = False
    loop_depth = 0

    for i, stripped in enumerate(clean_lines, start=1):
        if re.search(r"\b(for|while)\s*\(", stripped):
            inside_loop = True
            loop_depth += stripped.count("{")

        if inside_loop and re.search(
            r"\b\w+\s*\+=\s*[^;]*['\"]",
            stripped,
        ):
            findings.append(
                _finding(
                    "performance",
                    "warning",
                    i,
                    "String concatenation inside a loop detected.",
                    "Consider StringBuilder for repeated string construction.",
                    "java-string-concat-loop",
                )
            )

        if inside_loop:
            loop_depth += stripped.count("{")
            loop_depth -= stripped.count("}")

            if loop_depth <= 0:
                inside_loop = False
                loop_depth = 0

    # -----------------------------------------------------------------------
    # Long methods
    # -----------------------------------------------------------------------

    method_start: Optional[int] = None
    method_brace_depth = 0

    for i, stripped in enumerate(clean_lines, start=1):
        method_signature = re.search(
            r"(public|private|protected|static|\s)+"
            r"[\w<>\[\], ?]+\s+\w+\s*\([^;]*\)\s*\{",
            stripped,
        )

        if method_signature and method_start is None:
            method_start = i
            method_brace_depth = (
                stripped.count("{") - stripped.count("}")
            )
            continue

        if method_start is not None:
            method_brace_depth += (
                stripped.count("{") - stripped.count("}")
            )

            if method_brace_depth <= 0:
                method_length = i - method_start + 1

                if method_length > 80:
                    findings.append(
                        _finding(
                            "quality",
                            "warning",
                            method_start,
                            "Method is longer than 80 lines.",
                            "Consider splitting the method into smaller focused methods.",
                            "java-long-method",
                        )
                    )

                method_start = None
                method_brace_depth = 0

    # -----------------------------------------------------------------------
    # Missing Javadoc for public methods
    # -----------------------------------------------------------------------

    for i, stripped in enumerate(clean_lines, start=1):
        if re.search(
            r"\bpublic\s+(?:static\s+)?[\w<>\[\], ?]+\s+\w+\s*\([^;]*\)\s*\{",
            stripped,
        ):
            previous_non_empty = ""

            for previous in reversed(clean_lines[: i - 1]):
                if previous.strip():
                    previous_non_empty = previous.strip()
                    break

            if (
                previous_non_empty
                and not previous_non_empty.endswith("*/")
                and not previous_non_empty.startswith("@")
            ):
                findings.append(
                    _finding(
                        "quality",
                        "info",
                        i,
                        "Public method does not appear to have Javadoc.",
                        "Add Javadoc describing the method's purpose, parameters, and return value.",
                        "java-missing-javadoc",
                    )
                )

    # -----------------------------------------------------------------------
    # Class declaration
    # -----------------------------------------------------------------------

    if not re.search(
        r"\b(class|interface|enum|record)\s+\w+",
        clean,
    ):
        findings.append(
            _finding(
                "syntax",
                "error",
                1,
                "No Java class, interface, enum, or record declaration found.",
                "Add a valid Java type declaration.",
                "java-no-class",
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze(code: str, timeout: float = 8.0) -> List[Finding]:
    """
    Analyze Java source code.

    Strategy:
      1. Try real javac compilation.
      2. If javac is unavailable, use structural syntax heuristics.
      3. Run rule-based quality/security/performance checks.
    """
    if not isinstance(code, str):
        raise TypeError("code must be a string")

    lines = code.split("\n")
    clean = _strip_strings_and_comments(code)

    findings: List[Finding] = []

    javac_findings = _run_javac(code, timeout)

    if javac_findings is not None:
        findings.extend(javac_findings)

        has_compile_error = any(
            f.get("severity") == "error"
            for f in javac_findings
        )

        for finding in javac_findings:
            finding["tool"] = "javac"

        # Keep structural balance checks when javac reports a syntax error.
        if has_compile_error:
            findings.extend(_check_balance(clean))

            # Do NOT return immediately.
            #
            # Rule-based checks are still useful even when javac reports
            # compilation errors.
    else:
        findings.extend(
            _heuristic_syntax_checks(
                code,
                clean,
                lines,
            )
        )

    findings.extend(
        _rule_based_checks(
            code,
            clean,
            lines,
        )
    )

    return findings