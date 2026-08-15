import React, { useState, useEffect } from 'react';
import { 
  Send, 
  Sparkles, 
  FileText, 
  FileSpreadsheet, 
  Presentation, 
  FileCode, 
  AlertTriangle, 
  ShieldCheck, 
  LineChart,
  Lightbulb
} from 'lucide-react';
import { AppMode, OutputFormat } from '../types';
import { validateColumn } from '../services/api';

interface BottomInputBarProps {
  currentMode: AppMode;
  selectedFormat: OutputFormat;
  onSelectFormat: (fmt: OutputFormat) => void;
  onSubmitPrompt: (prompt: string) => void;
  isExecuting: boolean;
}

const MODE_PROMPTS: Record<AppMode, string[]> = {
  modify: [
    "Change Rahul's CGPA to 9.2",
    "Update Arun's attendance to 95%",
    "Delete all students with CGPA below 5",
    "Add new student Ananya Roy in CSE with 9.1 CGPA"
  ],
  explore: [
    "Show the top 10 CSE students",
    "Find students with CGPA above 9",
    "Show all students in Electronics with attendance below 75%",
    "List all students ordered by roll number"
  ],
  analyze: [
    "Rank the top 10 students using 80% marks and 20% LeetCode count",
    "Find academically at-risk students and explain reasons",
    "Compare CSE and ECE department performance",
    "Analyze attendance correlation with CGPA"
  ]
};

export const BottomInputBar: React.FC<BottomInputBarProps> = ({
  currentMode,
  selectedFormat,
  onSelectFormat,
  onSubmitPrompt,
  isExecuting,
}) => {
  const [prompt, setPrompt] = useState('');
  const [suggestion, setSuggestion] = useState<string | null>(null);

  // Check column names on user typing
  useEffect(() => {
    if (!prompt.trim() || prompt.length < 3) {
      setSuggestion(null);
      return;
    }

    const timer = setTimeout(async () => {
      // Extract potential column candidates (words with letters/numbers)
      const words = prompt.match(/\b[a-zA-Z_]{3,}\b/g) || [];
      for (const word of words) {
        const lower = word.toLowerCase();
        if (['the', 'and', 'with', 'for', 'all', 'top', 'find', 'show', 'list', 'using', 'rank', 'change', 'update', 'delete', 'students'].includes(lower)) {
          continue;
        }
        try {
          const res = await validateColumn('students', word);
          if (!res.valid && res.suggestion && res.suggestion.toLowerCase() !== lower) {
            setSuggestion(res.suggestion);
            return;
          }
        } catch {
          // ignore validation network hiccups
        }
      }
      setSuggestion(null);
    }, 400);

    return () => clearTimeout(timer);
  }, [prompt]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!prompt.trim() || isExecuting) return;
    onSubmitPrompt(prompt.trim());
    setPrompt('');
    setSuggestion(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const applySuggestion = (sug: string) => {
    // Append or replace the suggestion in prompt
    setPrompt(prev => `${prev} (${sug})`);
    setSuggestion(null);
  };

  const hasText = prompt.trim().length > 0;
  const examplePrompts = MODE_PROMPTS[currentMode] || MODE_PROMPTS.explore;

  return (
    <div className="bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border-t border-slate-200 dark:border-slate-800 p-3 sm:p-4 shrink-0 z-10 select-none transition-colors">
      <div className="max-w-5xl mx-auto space-y-3">
        {/* Top Controls: Mode Status & Output Format Selector */}
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          {/* Mode Guidance Tag */}
          <div className="flex items-center gap-2">
            {currentMode === 'modify' && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800 font-medium">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                <span>This mode can modify your database.</span>
              </span>
            )}
            {currentMode === 'explore' && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-blue-800 dark:text-blue-300 border border-blue-200 dark:border-blue-800 font-medium">
                <ShieldCheck className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                <span>Explore mode is read-only. Your database will not be modified.</span>
              </span>
            )}
            {currentMode === 'analyze' && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-800 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 font-medium">
                <LineChart className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                <span>Analyze mode: Pulse statistics and Scribe report generation.</span>
              </span>
            )}
          </div>

          {/* Analyze Mode Output Format Selector */}
          {currentMode === 'analyze' && (
            <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-0.5 rounded-xl border border-slate-200 dark:border-slate-700">
              <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 px-2 uppercase tracking-wider">
                Output:
              </span>
              {(['text', 'excel', 'pdf', 'ppt'] as OutputFormat[]).map((fmt) => (
                <button
                  key={fmt}
                  type="button"
                  onClick={() => onSelectFormat(fmt)}
                  disabled={isExecuting}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                    selectedFormat === fmt
                      ? 'bg-indigo-600 text-white shadow-xs'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                  }`}
                >
                  {fmt === 'text' && <FileCode className="w-3 h-3" />}
                  {fmt === 'excel' && <FileSpreadsheet className="w-3 h-3" />}
                  {fmt === 'pdf' && <FileText className="w-3 h-3" />}
                  {fmt === 'ppt' && <Presentation className="w-3 h-3" />}
                  <span className="capitalize">{fmt === 'ppt' ? 'PowerPoint' : fmt}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Suggestion Notification Chip */}
        {suggestion && (
          <div className="flex items-center gap-2 text-xs bg-amber-50 dark:bg-amber-950/50 border border-amber-200 dark:border-amber-800 px-3 py-1.5 rounded-xl text-amber-800 dark:text-amber-300 animate-in fade-in">
            <Lightbulb className="w-3.5 h-3.5 text-amber-600 shrink-0" />
            <span>Did you mean column <code className="px-1 py-0.5 bg-amber-100 dark:bg-amber-900/60 rounded font-mono font-bold text-amber-900 dark:text-amber-200">`{suggestion}`</code>?</span>
            <button
              onClick={() => applySuggestion(suggestion)}
              className="ml-auto text-[11px] font-semibold text-blue-600 dark:text-blue-400 hover:underline cursor-pointer"
            >
              Use `{suggestion}`
            </button>
          </div>
        )}

        {/* Main Input Form */}
        <form onSubmit={handleSubmit} className="flex items-center gap-2.5">
          <div className="relative flex-1 flex items-center">
            <div className="absolute left-4 text-blue-600 dark:text-blue-400 pointer-events-none">
              <Sparkles className="w-4 h-4" />
            </div>
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isExecuting}
              placeholder={
                currentMode === 'modify'
                  ? "Enter database change... e.g. \"Change Rahul's CGPA to 9.2\", \"Delete students below 5 CGPA\""
                  : currentMode === 'explore'
                  ? "Search database records... e.g. \"Show top 10 CSE students\", \"Find students with CGPA above 9\""
                  : "Request analysis or report... e.g. \"Rank top 10 by 80% marks and 20% LeetCode\", \"Find at-risk students\""
              }
              className="w-full bg-slate-50 dark:bg-slate-800/90 border border-slate-300 dark:border-slate-700 rounded-2xl pl-11 pr-24 py-3 text-xs sm:text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:border-blue-600 dark:focus:border-blue-500 focus:ring-3 focus:ring-blue-500/20 disabled:opacity-50 transition-all shadow-xs"
            />
            <div className="absolute right-3.5 text-[11px] text-slate-400 hidden sm:block pointer-events-none">
              Press <kbd className="px-1.5 py-0.5 bg-slate-200 dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded text-[10px] text-slate-600 dark:text-slate-300 font-mono">Enter</kbd>
            </div>
          </div>

          <button
            type="submit"
            disabled={!hasText || isExecuting}
            className={`flex items-center gap-2 px-5 py-3 text-xs font-semibold rounded-2xl transition-all shrink-0 ${
              hasText && !isExecuting
                ? currentMode === 'modify'
                  ? 'bg-amber-600 hover:bg-amber-700 text-white shadow-md active:scale-95 cursor-pointer'
                  : currentMode === 'analyze'
                  ? 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-md active:scale-95 cursor-pointer'
                  : 'bg-blue-600 hover:bg-blue-700 text-white shadow-md active:scale-95 cursor-pointer'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-600 border border-slate-200 dark:border-slate-700 cursor-not-allowed'
            }`}
          >
            {isExecuting ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Running...</span>
              </>
            ) : (
              <>
                <span>Run {currentMode === 'modify' ? 'Mutation' : currentMode === 'explore' ? 'Explore' : 'Analysis'}</span>
                <Send className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </form>

        {/* Quick Example Prompt Chips */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-0.5 custom-scrollbar text-[11px]">
          <span className="text-slate-400 dark:text-slate-500 font-medium shrink-0">Try:</span>
          {examplePrompts.map((p, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setPrompt(p)}
              disabled={isExecuting}
              className="px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 hover:bg-blue-50 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 border border-slate-200 dark:border-slate-700 transition-all whitespace-nowrap cursor-pointer disabled:opacity-50"
            >
              {p}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
