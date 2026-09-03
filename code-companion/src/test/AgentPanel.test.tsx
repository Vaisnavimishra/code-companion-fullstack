import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AgentPanel from "@/components/AgentPanel";
import type { ReviewResponse } from "@/lib/apiClient";

const sampleReport: ReviewResponse = {
  language: "python",
  findings: [
    {
      id: "1",
      agent: "Security Agent",
      category: "security",
      severity: "error",
      line: 3,
      message: "Possible hardcoded credential/secret",
      explanation: "Secrets in source code can leak.",
      suggestion: "Use environment variables.",
      rule: "python-hardcoded-secret",
      source: "static-analysis",
    },
  ],
  agents: [
    { agent: "Syntax & Compilation Agent", category: "syntax", description: "d", findings: [], execution_time_ms: 0.2 },
    { agent: "Logic & Bug Detection Agent", category: "logic", description: "d", findings: [], execution_time_ms: 0.2 },
    { agent: "Code Quality Agent", category: "quality", description: "d", findings: [], execution_time_ms: 0.2 },
    {
      agent: "Security Agent",
      category: "security",
      description: "d",
      findings: [
        {
          id: "1",
          agent: "Security Agent",
          category: "security",
          severity: "error",
          line: 3,
          message: "Possible hardcoded credential/secret",
          source: "static-analysis",
        },
      ],
      execution_time_ms: 0.3,
    },
    { agent: "Performance Agent", category: "performance", description: "d", findings: [], execution_time_ms: 0.1 },
  ],
  summary: { total_findings: 1, errors: 1, warnings: 0, info: 0, success: 0, score: 85, verdict: "Needs work — blocking issues found" },
  documentation: "No module-level docstring found.",
  fixed_code: "x = 1",
  llm_enabled: false,
  analyzed_at: "2026-01-01T00:00:00Z",
};

describe("AgentPanel", () => {
  it("shows the empty state when there is no report", () => {
    render(<AgentPanel report={null} isAnalyzing={false} error={null} />);
    expect(screen.getByText(/no analysis yet/i)).toBeInTheDocument();
  });

  it("shows the loading state while analyzing", () => {
    render(<AgentPanel report={null} isAnalyzing={true} error={null} />);
    expect(screen.getByText(/running multi-agent review/i)).toBeInTheDocument();
  });

  it("shows the error state with a retry button", () => {
    render(<AgentPanel report={null} isAnalyzing={false} error="Could not reach the review backend." onRetry={() => {}} />);
    expect(screen.getByText(/analysis failed/i)).toBeInTheDocument();
    expect(screen.getByText(/try again/i)).toBeInTheDocument();
  });

  it("renders agent tabs and findings for a real report", () => {
    render(<AgentPanel report={sampleReport} isAnalyzing={false} error={null} />);
    expect(screen.getByText("Syntax")).toBeInTheDocument();
    expect(screen.getByText("Security")).toBeInTheDocument();
    expect(screen.getByText("Performance")).toBeInTheDocument();
  });
});
