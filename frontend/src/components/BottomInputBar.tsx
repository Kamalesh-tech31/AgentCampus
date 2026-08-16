import React, { useState, useEffect, useRef } from 'react';
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
  RotateCw
} from 'lucide-react';
import { AppMode, OutputFormat } from '../types';
import { getFreshSuggestions, SuggestionItem } from '../data/suggestions';

interface BottomInputBarProps {
  currentMode: AppMode;
  selectedFormat: OutputFormat;
  onSelectFormat: (fmt: OutputFormat) => void;
  onSubmitPrompt: (prompt: string) => void;
  isExecuting: boolean;
  usedPrompts?: string[];
}

export const BottomInputBar: React.FC<BottomInputBarProps> = ({
  currentMode,
  selectedFormat,
  onSelectFormat,
  onSubmitPrompt,
  isExecuting,
  usedPrompts = [],
}) => {
  const [prompt, setPrompt] = useState('');
  const [rotationOffset, setRotationOffset] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Reset prompt on execution start / finish if needed
  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!prompt.trim() || isExecuting) return;
    const submitted = prompt.trim();
    onSubmitPrompt(submitted);
    setPrompt('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSelectSuggestion = (suggestionPrompt: string) => {
    setPrompt(suggestionPrompt);
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  const handleRotateSuggestions = () => {
    setRotationOffset(prev => prev + 1);
  };

  const hasText = prompt.trim().length > 0;
  
  // Calculate fresh contextual suggestions based on current mode and history
  const allFresh = getFreshSuggestions(currentMode, usedPrompts, 8);
  // Apply rotation window of 3 items
  const displaySuggestions: SuggestionItem[] = [];
  if (allFresh.length > 0) {
    const startIndex = (rotationOffset * 3) % allFresh.length;
    for (let i = 0; i < Math.min(3, allFresh.length); i++) {
      displaySuggestions.push(allFresh[(startIndex + i) % allFresh.length]);
    }
  }

  return (
    <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border-t border-slate-200/80 dark:border-slate-800/80 p-3 sm:p-4 shrink-0 z-20 select-none transition-colors">
      <div className="max-w-5xl mx-auto space-y-3">
        {/* Top Controls: Mode Status & Output Format Selector */}
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          {/* Mode Guidance Tag */}
          <div className="flex items-center gap-2">
            {currentMode === 'modify' && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border border-amber-200/80 dark:border-amber-800/80 font-medium">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
                <span>Modify Mode: Operations require confirmation before execution.</span>
              </span>
            )}
            {currentMode === 'explore' && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-blue-800 dark:text-blue-300 border border-blue-200/80 dark:border-blue-800/80 font-medium">
                <ShieldCheck className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 shrink-0" />
                <span>Explore Mode: Read-only queries without data alteration.</span>
              </span>
            )}
            {currentMode === 'analyze' && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-800 dark:text-indigo-300 border border-indigo-200/80 dark:border-indigo-800/80 font-medium">
                <LineChart className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 shrink-0" />
                <span>Analyze Mode: Statistical models, factor assessment & multi-format reports.</span>
              </span>
            )}
          </div>

          {/* Analyze Mode Output Format Selector */}
          {currentMode === 'analyze' && (
            <div className="flex items-center gap-1 bg-slate-100/90 dark:bg-slate-800/90 p-0.5 rounded-xl border border-slate-200 dark:border-slate-700/80">
              <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 px-2 uppercase tracking-wider">
                Export:
              </span>
              {(['text', 'excel', 'pdf', 'ppt'] as OutputFormat[]).map((fmt) => (
                <button
                  key={fmt}
                  type="button"
                  onClick={() => onSelectFormat(fmt)}
                  disabled={isExecuting}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                    selectedFormat === fmt
                      ? 'bg-indigo-600 text-white shadow-2xs'
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

        {/* Main Input Form with Non-Invasive Dark Focus Styling */}
        <form onSubmit={handleSubmit} className="flex items-center gap-2.5">
          <div className="relative flex-1 flex items-center bg-slate-100/80 dark:bg-slate-800/80 border border-slate-300/80 dark:border-slate-700/80 rounded-2xl transition-all shadow-2xs focus-within:border-blue-500 dark:focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/20 focus-within:bg-white dark:focus-within:bg-slate-900">
            <div className="absolute left-4 text-blue-600 dark:text-blue-400 pointer-events-none">
              <Sparkles className="w-4 h-4" />
            </div>
            <input
              ref={inputRef}
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
                  : "Request analysis or report... e.g. \"Find academically at-risk students\", \"Rank top 10 students\""
              }
              className="w-full bg-transparent border-none outline-none ring-0 shadow-none pl-11 pr-24 py-3.5 text-xs sm:text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-0 font-normal"
            />
            <div className="absolute right-3.5 text-[11px] text-slate-400 hidden sm:block pointer-events-none">
              Press <kbd className="px-1.5 py-0.5 bg-slate-200 dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded text-[10px] text-slate-600 dark:text-slate-300 font-mono font-semibold">Enter</kbd>
            </div>
          </div>

          <button
            type="submit"
            disabled={!hasText || isExecuting}
            className={`flex items-center gap-2 px-5 py-3.5 text-xs font-bold rounded-2xl transition-all shrink-0 ${
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
                <span>Run {currentMode === 'modify' ? 'Mutation' : currentMode === 'explore' ? 'Query' : 'Analysis'}</span>
                <Send className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </form>

        {/* Dynamic Suggested Queries with Context and Clean Rotation */}
        {displaySuggestions.length > 0 && (
          <div className="flex items-center gap-2 overflow-x-auto py-0.5 custom-scrollbar text-[11px]">
            <div className="flex items-center gap-1 text-slate-400 dark:text-slate-500 font-semibold uppercase tracking-wider text-[10px] shrink-0">
              <Sparkles className="w-3 h-3 text-blue-500/80" />
              <span>Suggested:</span>
            </div>
            
            <div className="flex items-center gap-1.5 flex-1 overflow-x-auto custom-scrollbar">
              {displaySuggestions.map((sug) => (
                <button
                  key={sug.id}
                  type="button"
                  onClick={() => handleSelectSuggestion(sug.prompt)}
                  disabled={isExecuting}
                  className="px-2.5 py-1 rounded-xl bg-slate-100/90 dark:bg-slate-800/90 hover:bg-blue-50 dark:hover:bg-slate-700/80 text-slate-700 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 border border-slate-200/80 dark:border-slate-700/80 hover:border-blue-300 dark:hover:border-blue-600 transition-all whitespace-nowrap cursor-pointer disabled:opacity-50 text-[11px] flex items-center gap-1.5 shadow-2xs group"
                  title={sug.description}
                >
                  <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 group-hover:text-blue-500 uppercase tracking-wider">
                    {sug.category}
                  </span>
                  <span className="text-slate-300 dark:text-slate-600">•</span>
                  <span className="truncate max-w-[280px]">"{sug.prompt}"</span>
                </button>
              ))}
            </div>

            {allFresh.length > 3 && (
              <button
                type="button"
                onClick={handleRotateSuggestions}
                disabled={isExecuting}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors shrink-0 cursor-pointer"
                title="Show more suggested queries"
              >
                <RotateCw className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
