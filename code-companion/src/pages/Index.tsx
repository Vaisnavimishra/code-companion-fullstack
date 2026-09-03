import { useEffect, useState } from "react";
import { reviewCode, fetchHealth, fetchSamples, ApiError, Language, ReviewResponse, SampleCode, HealthResponse } from "@/lib/apiClient";
import CodeEditor, { PLACEHOLDERS } from "@/components/CodeEditor";
import AgentPanel from "@/components/AgentPanel";
import { Bot, GitBranch, FileCode2, ChevronDown } from "lucide-react";

const Index = () => {
  const [code, setCode] = useState("");
  const [language, setLanguage] = useState<Language>("python");
  const [report, setReport] = useState<ReviewResponse | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState(false);

  const [samples, setSamples] = useState<SampleCode[]>([]);
  const [showSamples, setShowSamples] = useState(false);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealthError(true));
    fetchSamples()
      .then(setSamples)
      .catch(() => {
        /* sample loading is a nice-to-have; silently ignore failures */
      });
  }, []);

  const handleAnalyze = async () => {
    const source = code.trim() || PLACEHOLDERS[language];
    if (!source.trim()) return;
    setIsAnalyzing(true);
    setError(null);
    setReport(null);
    try {
      const result = await reviewCode(source, language);
      setReport(result);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "An unexpected error occurred while analyzing your code.";
      setError(message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const languageSamples = samples.filter((s) => s.language === language);

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-border bg-card/50 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center glow-primary">
            <Bot className="w-4.5 h-4.5 text-primary" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight">
              <span className="text-gradient">CodeAgent</span>
              <span className="text-muted-foreground font-normal ml-1.5 text-xs">v1.0</span>
            </h1>
            <p className="text-[10px] text-muted-foreground">Multi-Agent Code Review & Debugging</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {languageSamples.length > 0 && (
            <div className="relative">
              <button
                onClick={() => setShowSamples((s) => !s)}
                className="flex items-center gap-1.5 text-xs font-mono text-muted-foreground hover:text-foreground border border-border rounded px-2.5 py-1.5 transition-colors"
              >
                <FileCode2 className="w-3.5 h-3.5" />
                Sample code
                <ChevronDown className="w-3 h-3" />
              </button>
              {showSamples && (
                <div className="absolute right-0 mt-1 w-72 rounded-md border border-border bg-popover shadow-lg z-10 overflow-hidden">
                  {languageSamples.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => {
                        setCode(s.code);
                        setReport(null);
                        setError(null);
                        setShowSamples(false);
                      }}
                      className="w-full text-left px-3 py-2 hover:bg-accent/10 transition-colors border-b border-border last:border-b-0"
                    >
                      <p className="text-xs font-medium">{s.title}</p>
                      <p className="text-[10px] text-muted-foreground mt-0.5">{s.description}</p>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex items-center gap-2 text-xs text-muted-foreground" title={healthError ? "Backend unreachable" : "Connected to review backend"}>
            <span className={`w-1.5 h-1.5 rounded-full ${healthError ? "bg-destructive" : health ? "bg-success" : "bg-muted-foreground/40 animate-pulse"}`} />
            <GitBranch className="w-3.5 h-3.5" />
            <span className="font-mono">
              {report ? `${report.agents.length} agents active` : health ? "5 agents ready" : healthError ? "backend offline" : "connecting…"}
            </span>
            {health?.llm_enabled && (
              <span className="ml-1 text-[10px] font-mono px-1.5 py-0.5 rounded bg-accent/20 text-accent-foreground/80 uppercase tracking-wide">
                AI on
              </span>
            )}
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 p-4 overflow-hidden">
        <CodeEditor
          code={code}
          language={language}
          onCodeChange={(c) => {
            setCode(c);
          }}
          onLanguageChange={(lang) => {
            setLanguage(lang);
            setReport(null);
            setError(null);
          }}
          onAnalyze={handleAnalyze}
          isAnalyzing={isAnalyzing}
        />
        <AgentPanel report={report} isAnalyzing={isAnalyzing} error={error} onRetry={handleAnalyze} />
      </main>
    </div>
  );
};

export default Index;
