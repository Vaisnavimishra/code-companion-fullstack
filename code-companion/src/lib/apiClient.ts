/**
 * API client for the CodeAgent multi-agent review backend.
 *
 * Talks to the real FastAPI service (see /backend). All types here mirror
 * the Pydantic models in `backend/app/models.py` — keep them in sync.
 *
 * Base URL resolution:
 *  - VITE_API_URL env var, if set (e.g. for a split frontend/backend deploy)
 *  - otherwise "/api", which works out of the box in dev via the Vite proxy
 *    (see vite.config.ts) and in prod behind a reverse proxy that forwards
 *    /api to the backend.
 */

export type Language = "python" | "java";

export type Severity = "error" | "warning" | "info" | "success";

export type Category = "syntax" | "logic" | "quality" | "security" | "performance" | "ai";

export interface Finding {
  id: string;
  agent: string;
  category: Category;
  severity: Severity;
  line?: number | null;
  column?: number | null;
  message: string;
  explanation?: string | null;
  suggestion?: string | null;
  fixed_snippet?: string | null;
  rule?: string | null;
  source: "static-analysis" | "llm";
}

export interface AgentResult {
  agent: string;
  category: Category;
  description: string;
  findings: Finding[];
  execution_time_ms: number;
  tool?: string | null;
}

export interface ReviewSummary {
  total_findings: number;
  errors: number;
  warnings: number;
  info: number;
  success: number;
  score: number;
  verdict: string;
}

export interface ReviewResponse {
  language: Language;
  findings: Finding[];
  agents: AgentResult[];
  summary: ReviewSummary;
  documentation: string;
  fixed_code?: string | null;
  llm_enabled: boolean;
  analyzed_at: string;
}

export interface SampleCode {
  id: string;
  title: string;
  language: Language;
  description: string;
  code: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  llm_enabled: boolean;
  llm_provider?: string | null;
  supported_languages: Language[];
  available_tools: Record<string, boolean>;
}

const RAW_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.trim();
const API_BASE = RAW_BASE ? RAW_BASE.replace(/\/$/, "") : "/api";

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 30000): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("The request timed out. Is the backend running?");
    }
    throw new ApiError(
      "Could not reach the review backend. Make sure the FastAPI server is running (see backend/README or run `uvicorn app.main:app --reload` in /backend)."
    );
  } finally {
    clearTimeout(timeout);
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.error || detail;
      if (Array.isArray(body.detail)) {
        // FastAPI/Pydantic validation error array
        detail = body.detail.map((d: { msg?: string }) => d.msg).join("; ");
      }
    } catch {
      // response wasn't JSON — fall back to statusText
    }
    throw new ApiError(detail || `Request failed with status ${res.status}`, res.status);
  }

  return (await res.json()) as T;
}

export function reviewCode(code: string, language: Language, filename?: string): Promise<ReviewResponse> {
  return request<ReviewResponse>("/review", {
    method: "POST",
    body: JSON.stringify({ code, language, filename }),
  });
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { method: "GET" }, 5000);
}

export function fetchSamples(): Promise<SampleCode[]> {
  return request<SampleCode[]>("/samples", { method: "GET" }, 8000);
}
