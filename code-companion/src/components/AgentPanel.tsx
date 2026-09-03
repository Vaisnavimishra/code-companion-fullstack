import { useEffect, useState } from "react";
import { AgentResult, Category, Finding, ReviewResponse } from "@/lib/apiClient";
import {
  Search,
  ShieldAlert,
  Zap,
  FileText,
  BarChart3,
  Copy,
  Check,
  Bug,
  Sparkles,
  Loader2,
  XCircle,
  RefreshCw,
} from "lucide-react";

const CATEGORY_META: Record<Category, { label: string; icon: typeof Search }> = {
  syntax: { label: "Syntax", icon: Search },
  logic: { label: "Logic", icon: Bug },
  quality: { label: "Quality", icon: Sparkles },
  security: { label: "Security", icon: ShieldAlert },
  performance: { label: "Performance", icon: Zap },
  ai: { label: "AI", icon: Sparkles },
};

type StaticTabId = "documentation" | "consolidated";
type TabId = Category | StaticTabId;

const SEVERITY_STYLES: Record<Finding["severity"], string> = {
  error: "bg-destructive/15 text-destructive border-destructive/30",
  warning: "bg-warning/10 text-warning border-warning/30",
  info: "bg-primary/10 text-primary border-primary/30",
  success: "bg-success/15 text-success border-success/30",
};

const SEVERITY_DOT: Record<Finding["severity"], string> = {
  error: "bg-destructive",
  warning: "bg-warning",
  info: "bg-primary",
  success: "bg-success",
};

function FindingCard({ finding }: { finding: Finding }) {
  return (
    <div className={`rounded-md border p-3 ${SEVERITY_STYLES[finding.severity]} animate-slide-up`}>
      <div className="flex items-start gap-2">
        <span className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${SEVERITY_DOT[finding.severity]}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {finding.line != null && (
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-background/50">L{finding.line}</span>
            )}
            <p className="text-sm font-medium">{finding.message}</p>
            {finding.source === "llm" && (
              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-accent/20 text-accent-foreground/80 uppercase tracking-wide">
                AI
              </span>
            )}
          </div>
          {finding.explanation && <p className="mt-1 text-xs opacity-80">{finding.explanation}</p>}
          {finding.suggestion && (
            <p className="mt-1 text-xs opacity-80">
              <span className="font-semibold">Fix: </span>
              {finding.suggestion}
            </p>
          )}
          {finding.fixed_snippet && (
            <pre className="mt-2 p-2 rounded bg-background/50 text-xs font-mono overflow-x-auto">{finding.fixed_snippet}</pre>
          )}
          {finding.rule && (
            <p className="mt-1.5 text-[10px] font-mono opacity-50">{finding.rule}</p>
          )}
        </div>
      </div>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button onClick={handleCopy} className="flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-colors">
      {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function SeverityBadge({ label, count, variant }: { label: string; count: number; variant: "error" | "warning" | "info" }) {
  if (count === 0) return null;
  const styles = {
    error: "bg-destructive/15 text-destructive",
    warning: "bg-warning/10 text-warning",
    info: "bg-primary/10 text-primary",
  };
  return <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${styles[variant]}`}>{count} {label}</span>;
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-4">
      <div className="w-16 h-16 rounded-full border-2 border-dashed border-border flex items-center justify-center">
        <Search className="w-6 h-6 opacity-40" />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium">No analysis yet</p>
        <p className="text-xs mt-1 opacity-60">Paste code and click Analyze to begin</p>
      </div>
    </div>
  );
}

function LoadingState() {
  const [messageIdx, setMessageIdx] = useState(0);
  const messages = [
    "Dispatching to specialized agents…",
    "Running syntax & compilation checks…",
    "Scanning for logic and security issues…",
    "Measuring complexity & performance…",
    "Consolidating findings…",
  ];
  useEffect(() => {
    const id = setInterval(() => setMessageIdx((i) => (i + 1) % messages.length), 1100);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-4">
      <Loader2 className="w-8 h-8 text-primary animate-spin" />
      <div className="text-center">
        <p className="text-sm font-medium text-foreground">Running multi-agent review…</p>
        <p className="text-xs mt-1 opacity-60 font-mono">{messages[messageIdx]}</p>
      </div>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-4 px-6">
      <div className="w-16 h-16 rounded-full border-2 border-destructive/30 bg-destructive/10 flex items-center justify-center">
        <XCircle className="w-7 h-7 text-destructive" />
      </div>
      <div className="text-center max-w-sm">
        <p className="text-sm font-medium text-foreground">Analysis failed</p>
        <p className="text-xs mt-1.5 opacity-70">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Try again
        </button>
      )}
    </div>
  );
}

interface AgentPanelProps {
  report: ReviewResponse | null;
  isAnalyzing: boolean;
  error: string | null;
  onRetry?: () => void;
}

export default function AgentPanel({ report, isAnalyzing, error, onRetry }: AgentPanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>("syntax");

  if (isAnalyzing) {
    return (
      <div className="flex flex-col h-full rounded-lg border border-border bg-card overflow-hidden">
        <LoadingState />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col h-full rounded-lg border border-border bg-card overflow-hidden">
        <ErrorState message={error} onRetry={onRetry} />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="flex flex-col h-full rounded-lg border border-border bg-card overflow-hidden">
        <EmptyState />
      </div>
    );
  }

  const agentTabs: { id: TabId; agent: AgentResult }[] = report.agents.map((a) => ({ id: a.category, agent: a }));
  const activeAgent = agentTabs.find((t) => t.id === activeTab)?.agent;

  return (
    <div className="flex flex-col h-full rounded-lg border border-border bg-card overflow-hidden">
      {/* Tab bar */}
      <div className="flex items-center border-b border-border bg-muted/50 overflow-x-auto">
        {agentTabs.map(({ id, agent }) => {
          const meta = CATEGORY_META[id];
          const Icon = meta.icon;
          const isActive = activeTab === id;
          const errCount = agent.findings.filter((f) => f.severity === "error").length;
          return (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-all whitespace-nowrap ${
                isActive
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {meta.label}
              {errCount > 0 && (
                <span className="ml-0.5 w-1.5 h-1.5 rounded-full bg-destructive" />
              )}
            </button>
          );
        })}
        <button
          onClick={() => setActiveTab("documentation")}
          className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-all whitespace-nowrap ${
            activeTab === "documentation" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          Docs
        </button>
        <button
          onClick={() => setActiveTab("consolidated")}
          className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-all whitespace-nowrap ${
            activeTab === "consolidated" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <BarChart3 className="w-3.5 h-3.5" />
          Report
        </button>
        <div className="ml-auto flex items-center gap-2 px-3">
          <SeverityBadge label="errors" count={report.summary.errors} variant="error" />
          <SeverityBadge label="warnings" count={report.summary.warnings} variant="warning" />
          <SeverityBadge label="info" count={report.summary.info} variant="info" />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {activeAgent && (
          <div className="flex flex-col gap-3">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{activeAgent.agent}</h3>
                <p className="text-xs text-muted-foreground/70 mt-1 max-w-md">{activeAgent.description}</p>
              </div>
              <span className="text-[10px] font-mono text-muted-foreground/60 whitespace-nowrap pt-0.5">
                {activeAgent.tool} · {activeAgent.execution_time_ms.toFixed(1)}ms
              </span>
            </div>
            {activeAgent.findings.length === 0 ? (
              <div className="rounded-md border border-success/20 bg-success/5 p-3 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-success flex-shrink-0" />
                <p className="text-sm">No issues found by this agent.</p>
              </div>
            ) : (
              activeAgent.findings
                .slice()
                .sort((a, b) => (a.line ?? 0) - (b.line ?? 0))
                .map((f) => <FindingCard key={f.id} finding={f} />)
            )}
          </div>
        )}

        {activeTab === "documentation" && (
          <div className="flex flex-col gap-3 animate-slide-up">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Documentation Coverage</h3>
            <div className="rounded-md border border-primary/20 bg-primary/5 p-4 text-sm text-foreground whitespace-pre-wrap font-mono leading-6">
              {report.documentation}
            </div>
          </div>
        )}

        {activeTab === "consolidated" && (
          <div className="flex flex-col gap-4 animate-slide-up">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Consolidated Report</h3>
              <CopyButton text={JSON.stringify(report, null, 2)} />
            </div>

            {/* Score + verdict */}
            <div className="rounded-md border border-border bg-background/50 p-4 flex items-center gap-4">
              <div className="text-3xl font-bold text-primary font-mono">{report.summary.score}</div>
              <div>
                <p className="text-sm font-medium">{report.summary.verdict}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {report.summary.total_findings} total finding{report.summary.total_findings === 1 ? "" : "s"} across {report.agents.length} agents
                  {report.llm_enabled ? " · AI review enabled" : ""}
                </p>
              </div>
            </div>

            {/* Summary cards */}
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-md border border-destructive/20 bg-destructive/5 p-3 text-center">
                <p className="text-2xl font-bold text-destructive">{report.summary.errors}</p>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">Errors</p>
              </div>
              <div className="rounded-md border border-warning/20 bg-warning/5 p-3 text-center">
                <p className="text-2xl font-bold text-warning">{report.summary.warnings}</p>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">Warnings</p>
              </div>
              <div className="rounded-md border border-primary/20 bg-primary/5 p-3 text-center">
                <p className="text-2xl font-bold text-primary">{report.summary.info}</p>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">Info</p>
              </div>
            </div>

            {/* Per-agent breakdown */}
            <div className="flex flex-col gap-2">
              <h4 className="text-xs font-semibold text-muted-foreground">Agent Breakdown</h4>
              <div className="rounded-md border border-border divide-y divide-border overflow-hidden">
                {report.agents.map((a) => (
                  <div key={a.agent} className="flex items-center justify-between px-3 py-2 text-xs">
                    <span className="font-medium">{a.agent}</span>
                    <span className="font-mono text-muted-foreground">
                      {a.findings.length} finding{a.findings.length === 1 ? "" : "s"} · {a.execution_time_ms.toFixed(1)}ms
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Fixed code */}
            {report.fixed_code && (
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold text-muted-foreground">Auto-Fixed Code (safe fixes only)</h4>
                  <CopyButton text={report.fixed_code} />
                </div>
                <pre className="rounded-md border border-border bg-background p-4 text-xs font-mono overflow-auto text-foreground leading-5 max-h-64">
                  {report.fixed_code}
                </pre>
              </div>
            )}

            {/* JSON dump */}
            <div className="flex flex-col gap-2">
              <h4 className="text-xs font-semibold text-muted-foreground">Raw JSON</h4>
              <pre className="rounded-md border border-border bg-background p-4 text-xs font-mono overflow-auto text-foreground leading-5 max-h-48">
                {JSON.stringify(report, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
