import { Language } from "@/lib/apiClient";

const PLACEHOLDERS: Record<Language, string> = {
  python: `def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# TODO: add memoization
password = "hardcoded-secret-123"
result = fibonacci(30)
print(result)`,
  java: `public class Main {
    public static void main(String[] args) {
        int[] arr = {5, 3, 8, 1, 2};
        for (int i = 0; i < arr.length; i++) {
            for (int j = 0; j < arr.length; j++) {
                if (arr[i] < arr[j]) {
                    int temp = arr[i];
                    arr[i] = arr[j];
                    arr[j] = temp;
                }
            }
        }
    }
}`,
};

interface CodeEditorProps {
  code: string;
  language: Language;
  onCodeChange: (code: string) => void;
  onLanguageChange: (lang: Language) => void;
  onAnalyze: () => void;
  isAnalyzing: boolean;
}

const LANGUAGES: { value: Language; label: string }[] = [
  { value: "python", label: "Python" },
  { value: "java", label: "Java" },
];

export default function CodeEditor({ code, language, onCodeChange, onLanguageChange, onAnalyze, isAnalyzing }: CodeEditorProps) {
  const lineCount = (code || PLACEHOLDERS[language]).split("\n").length;

  return (
    <div className="flex flex-col h-full rounded-lg border border-border bg-card overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-muted/50">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <span className="w-3 h-3 rounded-full bg-destructive/60" />
            <span className="w-3 h-3 rounded-full bg-warning/60" />
            <span className="w-3 h-3 rounded-full bg-success/60" />
          </div>
          <span className="text-xs font-mono text-muted-foreground">code-input</span>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={language}
            onChange={(e) => {
              const lang = e.target.value as Language;
              onLanguageChange(lang);
              if (!code) onCodeChange(PLACEHOLDERS[lang]);
            }}
            className="text-xs font-mono bg-secondary text-secondary-foreground border border-border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-primary"
          >
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>{l.label}</option>
            ))}
          </select>
          <button
            onClick={onAnalyze}
            disabled={isAnalyzing || !code.trim()}
            className="px-4 py-1.5 text-xs font-semibold rounded bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-40 transition-all glow-primary"
          >
            {isAnalyzing ? (
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                Analyzing…
              </span>
            ) : (
              "▶ Analyze"
            )}
          </button>
        </div>
      </div>

      {/* Editor area */}
      <div className="flex flex-1 overflow-auto">
        {/* Line numbers */}
        <div className="flex flex-col items-end py-4 px-3 bg-muted/30 text-muted-foreground text-xs font-mono select-none border-r border-border min-w-[3rem]">
          {Array.from({ length: lineCount }, (_, i) => (
            <span key={i} className="leading-6">{i + 1}</span>
          ))}
        </div>
        {/* Textarea */}
        <textarea
          value={code}
          onChange={(e) => onCodeChange(e.target.value)}
          placeholder={PLACEHOLDERS[language]}
          spellCheck={false}
          className="flex-1 p-4 bg-transparent text-foreground font-mono text-sm leading-6 resize-none focus:outline-none placeholder:text-muted-foreground/40"
        />
      </div>
    </div>
  );
}

export { PLACEHOLDERS };
