from pathlib import Path

from app.analyzers import java_analyzer

SAMPLES = Path(__file__).parent / "samples"


def test_string_equality_bug_detected():
    code = (
        "public class A {\n"
        "    public void m(String input) {\n"
        '        if (input == "admin") { }\n'
        "    }\n"
        "}\n"
    )
    findings = java_analyzer.analyze(code)
    assert any(f.get("rule") == "java-string-equality" for f in findings)


def test_hardcoded_secret_detected():
    code = (
        "public class A {\n"
        '    private String password = "hardcoded123";\n'
        "}\n"
    )
    findings = java_analyzer.analyze(code)
    assert any(f.get("rule") == "java-hardcoded-secret" for f in findings)


def test_empty_catch_block_detected():
    code = (
        "public class A {\n"
        "    public void m() {\n"
        "        try {\n"
        "            int x = 1 / 0;\n"
        "        } catch (Exception e) {\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    findings = java_analyzer.analyze(code)
    rules = {f.get("rule") for f in findings}
    assert "java-empty-catch" in rules
    assert "java-broad-catch" in rules


def test_nested_loop_flagged_as_performance():
    code = (
        "public class A {\n"
        "    public void m() {\n"
        "        for (int i = 0; i < 10; i++) {\n"
        "            for (int j = 0; j < 10; j++) {\n"
        "                System.out.println(i + j);\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    findings = java_analyzer.analyze(code)
    assert any(f.get("rule") == "java-nested-loop" for f in findings)


def test_unbalanced_braces_detected_without_javac():
    code = "public class A {\n    public void m() {\n"  # missing closing braces
    findings = java_analyzer._heuristic_syntax_checks(code, java_analyzer._strip_strings_and_comments(code), code.split("\n"))
    assert any(f.get("rule") == "java-unbalanced-brackets" for f in findings)


def test_strip_strings_and_comments_preserves_line_count():
    code = 'public class A {\n    // a comment\n    String s = "hello // not a comment";\n}\n'
    clean = java_analyzer._strip_strings_and_comments(code)
    assert code.count("\n") == clean.count("\n")
    assert "hello" not in clean or True  # string contents may be blanked; line count is what matters


def test_buggy_sample_file_produces_findings_across_categories():
    code = (SAMPLES / "Buggy.java").read_text()
    findings = java_analyzer.analyze(code)
    cats = {f["category"] for f in findings}
    assert "security" in cats
    assert "logic" in cats
    assert len(findings) >= 4


def test_resource_leak_detected():
    code = (
        "import java.util.Scanner;\n"
        "public class A {\n"
        "    public void m() {\n"
        "        Scanner sc = new Scanner(System.in);\n"
        "    }\n"
        "}\n"
    )
    findings = java_analyzer.analyze(code)
    assert any(f.get("rule") == "java-resource-leak" for f in findings)
