import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { reviewCode, fetchHealth, ApiError } from "@/lib/apiClient";

const mockReviewResponse = {
  language: "python",
  findings: [],
  agents: [
    { agent: "Syntax & Compilation Agent", category: "syntax", description: "", findings: [], execution_time_ms: 0.1 },
  ],
  summary: { total_findings: 0, errors: 0, warnings: 0, info: 0, success: 0, score: 100, verdict: "Looks good" },
  documentation: "ok",
  fixed_code: null,
  llm_enabled: false,
  analyzed_at: "2026-01-01T00:00:00Z",
};

describe("apiClient", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("reviewCode posts to /api/review and returns the parsed response", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockReviewResponse,
    }) as unknown as typeof fetch;

    const result = await reviewCode("print('hi')", "python");
    expect(result.summary.score).toBe(100);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/review"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("throws an ApiError with the server-provided detail on a non-2xx response", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      statusText: "Unprocessable Entity",
      json: async () => ({ detail: "code must not be empty" }),
    }) as unknown as typeof fetch;

    await expect(reviewCode("", "python")).rejects.toThrow(ApiError);
    await expect(reviewCode("", "python")).rejects.toThrow(/code must not be empty/);
  });

  it("throws a friendly ApiError when the backend is unreachable", async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(fetchHealth()).rejects.toThrow(ApiError);
    await expect(fetchHealth()).rejects.toThrow(/Could not reach the review backend/);
  });
});
