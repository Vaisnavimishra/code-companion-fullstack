import pytest

from app.models import Language
from app.orchestrator import orchestrator


@pytest.mark.asyncio
async def test_review_python_buggy_code_returns_structured_response():
    code = (
        "def add_item(item, items=[]):\n"
        "    items.append(item)\n"
        "    return items\n"
    )
    result = await orchestrator.review(code, Language.PYTHON)
    assert result.language == Language.PYTHON
    assert result.summary.total_findings >= 1
    assert result.summary.errors >= 1
    assert result.summary.score < 100
    agent_names = {a.agent for a in result.agents}
    assert "Logic & Bug Detection Agent" in agent_names
    assert result.llm_enabled is False


@pytest.mark.asyncio
async def test_review_syntax_error_short_circuits_other_agents():
    code = "def broken(:\n    pass\n"
    result = await orchestrator.review(code, Language.PYTHON)
    assert result.summary.errors == 1
    assert result.summary.total_findings == 1
    syntax_agent = next(a for a in result.agents if a.agent == "Syntax & Compilation Agent")
    assert len(syntax_agent.findings) == 1


@pytest.mark.asyncio
async def test_review_clean_code_scores_highly():
    code = (
        '"""Clean module."""\n\n\n'
        "def add(a: int, b: int) -> int:\n"
        '    """Return the sum of a and b."""\n'
        "    return a + b\n"
    )
    result = await orchestrator.review(code, Language.PYTHON)
    assert result.summary.errors == 0
    assert result.summary.score >= 90


@pytest.mark.asyncio
async def test_review_java_buggy_code():
    code = (
        "public class A {\n"
        '    private String password = "secret123";\n'
        "    public void m(String input) {\n"
        '        if (input == "x") { }\n'
        "    }\n"
        "}\n"
    )
    result = await orchestrator.review(code, Language.JAVA)
    assert result.language == Language.JAVA
    assert result.summary.errors >= 1


@pytest.mark.asyncio
async def test_no_duplicate_findings_in_flattened_list():
    code = (
        "def add_item(item, items=[]):\n"
        "    items.append(item)\n"
        "    return items\n"
    )
    result = await orchestrator.review(code, Language.PYTHON)
    keys = [(f.category, f.line, f.message) for f in result.findings]
    assert len(keys) == len(set(keys))
