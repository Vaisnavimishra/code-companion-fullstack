from pathlib import Path

from app.analyzers import python_analyzer

SAMPLES = Path(__file__).parent / "samples"


def _categories(findings):
    return {f["category"] for f in findings}


def test_syntax_error_detected():
    findings = python_analyzer.analyze("def broken(:\n    pass\n")
    assert len(findings) == 1
    assert findings[0]["category"] == "syntax"
    assert findings[0]["severity"] == "error"
    assert findings[0]["line"] == 1


def test_valid_code_has_no_syntax_errors():
    findings = python_analyzer.analyze("def add(a, b):\n    return a + b\n")
    assert not any(f["category"] == "syntax" for f in findings)


def test_mutable_default_argument_detected():
    code = "def add_item(item, items=[]):\n    items.append(item)\n    return items\n"
    findings = python_analyzer.analyze(code)
    rules = {f.get("rule") for f in findings}
    assert "python-mutable-default-arg" in rules


def test_bare_except_detected():
    code = "try:\n    x = 1\nexcept:\n    pass\n"
    findings = python_analyzer.analyze(code)
    rules = {f.get("rule") for f in findings}
    assert "python-bare-except" in rules
    assert "python-empty-except" in rules


def test_hardcoded_secret_detected():
    findings = python_analyzer.analyze('password = "supersecret123"\n')
    assert any(f.get("rule") == "python-hardcoded-secret" for f in findings)


def test_sql_injection_detected():
    code = (
        "def q(name):\n"
        "    query = \"SELECT * FROM users WHERE name = '\" + name + \"'\"\n"
        "    return query\n"
    )
    findings = python_analyzer.analyze(code)
    assert any(f.get("rule") == "python-sql-injection" for f in findings)


def test_eval_flagged_as_security_error():
    findings = python_analyzer.analyze("x = eval(user_input)\n")
    matches = [f for f in findings if f.get("rule") == "python-eval-usage"]
    assert matches and matches[0]["severity"] == "error"


def test_nested_loop_flagged_as_performance():
    code = "for i in range(10):\n    for j in range(10):\n        pass\n"
    findings = python_analyzer.analyze(code)
    assert any(f.get("rule") == "python-nested-loop" for f in findings)


def test_unmemoized_recursion_flagged():
    code = "def fib(n):\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)\n"
    findings = python_analyzer.analyze(code)
    assert any(f.get("rule") == "python-unmemoized-recursion" for f in findings)


def test_memoized_recursion_not_flagged():
    code = (
        "from functools import lru_cache\n\n"
        "@lru_cache(maxsize=None)\n"
        "def fib(n):\n"
        "    if n <= 1:\n"
        "        return n\n"
        "    return fib(n-1) + fib(n-2)\n"
    )
    findings = python_analyzer.analyze(code)
    assert not any(f.get("rule") == "python-unmemoized-recursion" for f in findings)


def test_buggy_sample_file_produces_many_findings():
    code = (SAMPLES / "buggy.py").read_text()
    findings = python_analyzer.analyze(code)
    cats = _categories(findings)
    assert "security" in cats
    assert "logic" in cats
    assert "performance" in cats
    assert len(findings) >= 5


def test_clean_sample_file_has_no_errors():
    code = (SAMPLES / "clean.py").read_text()
    findings = python_analyzer.analyze(code)
    assert not any(f["severity"] == "error" for f in findings)


def test_documentation_notes_mentions_missing_docstring():
    code = "def foo(x):\n    return x\n"
    notes = python_analyzer.build_documentation_notes(code)
    assert "docstring" in notes.lower()


def test_generate_fixed_code_strips_trailing_whitespace():
    code = "x = 1   \ny = 2\t\n"
    fixed = python_analyzer.generate_fixed_code(code, [])
    assert all(not line.endswith((" ", "\t")) for line in fixed.split("\n"))
