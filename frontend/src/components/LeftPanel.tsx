import React, { useState } from 'react';
import { 
  Plus, 
  History, 
  PanelLeftClose, 
  PanelLeftOpen, 
  CheckCircle2, 
  AlertCircle, 
  Clock, 
  MessageSquare,
  Compass,
  Database,
  LineChart
} from 'lucide-react';
import { ChatThread, AppMode } from '../types';

interface LeftPanelProps {
  threads: ChatThread[];
  selectedThreadId?: string;
  onSelectThread: (id: string) => void;
  onNewThread: () => void;
}

export const LeftPanel: React.FC<LeftPanelProps> = ({
  threads,
  selectedThreadId,
  onSelectThread,
  onNewThread,
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const getModeIcon = (mode: AppMode) => {
    switch (mode) {
      case 'modify': return <Database className="w-3 h-3 text-amber-500" />;
      case 'analyze': return <LineChart className="w-3 h-3 text-indigo-500" />;
      default: return <Compass className="w-3 h-3 text-blue-500" />;
    }
  };

  return (
    <div
      className={`${
        isCollapsed ? 'w-16' : 'w-72 lg:w-80'
      } h-full bg-slate-50 dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col shrink-0 select-none overflow-hidden transition-all duration-300 ease-in-out`}
    >
      {/* Panel Header */}
      <div className="p-3.5 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center justify-between shrink-0 h-14">
        {!isCollapsed && (
          <div className="flex items-center gap-2 min-w-0">
            <History className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0" />
            <span className="text-xs font-bold text-slate-900 dark:text-slate-100 tracking-tight truncate">
              Sessions
            </span>
            <span className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full border border-slate-200 dark:border-slate-700">
              {threads.length}
            </span>
          </div>
        )}

        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className={`p-1.5 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors cursor-pointer ${
            isCollapsed ? 'mx-auto' : ''
          }`}
          title={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          {isCollapsed ? (
            <PanelLeftOpen className="w-4 h-4" />
          ) : (
            <PanelLeftClose className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Primary Action Button (+ New Chat) */}
      <div className="p-3 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shrink-0">
        {isCollapsed ? (
          <button
            onClick={onNewThread}
            className="w-10 h-10 mx-auto bg-blue-600 hover:bg-blue-700 text-white rounded-xl flex items-center justify-center transition-all cursor-pointer shadow-xs active:scale-95"
            title="New Chat Session"
          >
            <Plus className="w-5 h-5" />
          </button>
        ) : (
          <button
            onClick={onNewThread}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-3 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-xl transition-all cursor-pointer shadow-xs active:scale-95"
          >
            <Plus className="w-4 h-4" />
            <span>New Session</span>
          </button>
        )}
      </div>

      {/* Threads List */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-1.5 custom-scrollbar">
        {threads.length === 0 ? (
          !isCollapsed && (
            <div className="p-4 text-center rounded-xl bg-white dark:bg-slate-800 border border-dashed border-slate-200 dark:border-slate-700 text-slate-400 text-xs mt-2">
              No sessions yet...
            </div>
          )
        ) : (
          threads.map((thread) => {
            const isSelected = selectedThreadId === thread.id;
            const turnCount = thread.turns.length;
            const isRunning = thread.turns.some((t) => t.status === 'running');
            const isFailed = thread.turns.some((t) => t.status === 'failed');

            return isCollapsed ? (
              <button
                key={thread.id}
                onClick={() => onSelectThread(thread.id)}
                className={`w-10 h-10 mx-auto rounded-xl flex items-center justify-center border transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-blue-50 dark:bg-blue-950/60 border-blue-300 dark:border-blue-700 text-blue-600 dark:text-blue-400'
                    : 'bg-white dark:bg-slate-800/80 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400'
                }`}
                title={thread.title}
              >
                {isRunning ? (
                  <Clock className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-pulse" />
                ) : isFailed ? (
                  <AlertCircle className="w-4 h-4 text-rose-600" />
                ) : (
                  <MessageSquare className="w-4 h-4" />
                )}
              </button>
            ) : (
              <div
                key={thread.id}
                onClick={() => onSelectThread(thread.id)}
                className={`p-3 rounded-xl border transition-all cursor-pointer flex flex-col gap-1 ${
                  isSelected
                    ? 'bg-blue-50/80 dark:bg-blue-950/40 border-blue-300 dark:border-blue-700 text-slate-900 dark:text-slate-100 shadow-xs'
                    : 'bg-white dark:bg-slate-800/60 border-slate-200 dark:border-slate-700/80 hover:border-slate-300 dark:hover:border-slate-600 text-slate-800 dark:text-slate-200 shadow-xs'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0 flex-1">
                    {getModeIcon(thread.mode)}
                    <span className="text-xs font-semibold truncate text-slate-800 dark:text-slate-200">
                      {thread.title}
                    </span>
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    {isRunning && <Clock className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 animate-pulse" />}
                    {!isRunning && isFailed && <AlertCircle className="w-3.5 h-3.5 text-rose-600" />}
                    {!isRunning && !isFailed && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />}
                  </div>
                </div>

                <div className="flex items-center justify-between text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">
                  <span className="uppercase font-semibold tracking-wider">{thread.mode}</span>
                  <span>{thread.updatedAt}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
