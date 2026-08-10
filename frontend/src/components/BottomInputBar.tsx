import React, { useState } from 'react';
import { Send, Sparkles } from 'lucide-react';

interface BottomInputBarProps {
  onSubmitPrompt: (prompt: string) => void;
  isExecuting: boolean;
}

export const BottomInputBar: React.FC<BottomInputBarProps> = ({
  onSubmitPrompt,
  isExecuting
}) => {
  const [prompt, setPrompt] = useState('');

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!prompt.trim() || isExecuting) return;
    onSubmitPrompt(prompt.trim());
    setPrompt('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const hasText = prompt.trim().length > 0;

  return (
    <div className="bg-slate-50/80 border-t border-gray-200 p-3.5 sm:p-4 shrink-0 z-10 select-none">
      <form onSubmit={handleSubmit} className="max-w-5xl mx-auto flex items-center gap-3">
        <div className="relative flex-1 flex items-center">
          <div className="absolute left-4 text-blue-600 pointer-events-none">
            <Sparkles className="w-4 h-4" />
          </div>
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isExecuting}
            placeholder="Ask anything... e.g. 'Show top 10 CS students', 'Calculate Mechanical CGPA avg', 'Update Rahul CGPA to 9.5'"
            className="w-full bg-white border-[1.5px] border-slate-300 rounded-2xl pl-11 pr-28 py-3 text-xs sm:text-sm text-gray-900 placeholder:text-gray-500 focus:outline-none focus:border-blue-600 focus:ring-4 focus:ring-blue-500/15 disabled:opacity-50 transition-all shadow-md"
          />
          <div className="absolute right-3.5 text-[11px] text-gray-400 hidden sm:block pointer-events-none">
            Press <kbd className="px-1.5 py-0.5 bg-gray-100 border border-gray-200 rounded text-[10px] text-gray-500 font-mono">Enter</kbd>
          </div>
        </div>

        <button
          type="submit"
          disabled={!hasText || isExecuting}
          className={`flex items-center gap-2 px-5 py-3 text-xs font-semibold rounded-2xl transition-all shrink-0 ${
            hasText && !isExecuting
              ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-md active:scale-95 cursor-pointer'
              : 'bg-gray-100 text-gray-400 border border-gray-200 cursor-not-allowed'
          }`}
        >
          {isExecuting ? (
            <>
              <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Running...</span>
            </>
          ) : (
            <>
              <span>Run Pipeline</span>
              <Send className="w-3.5 h-3.5" />
            </>
          )}
        </button>
      </form>
    </div>
  );
};


