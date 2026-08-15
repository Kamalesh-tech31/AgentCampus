import React from 'react';
import { 
  Bot, 
  Database, 
  RefreshCw, 
  Sun, 
  Moon, 
  Compass, 
  LineChart, 
  HelpCircle,
  ShieldCheck,
  AlertTriangle
} from 'lucide-react';
import { AppMode } from '../types';

interface HeaderProps {
  currentMode: AppMode;
  onSelectMode: (mode: AppMode) => void;
  onOpenModeInfo: (mode: AppMode) => void;
  onOpenDatabasePreview: () => void;
  onResetDb: () => void;
  isExecuting: boolean;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentMode,
  onSelectMode,
  onOpenModeInfo,
  onOpenDatabasePreview,
  onResetDb,
  isExecuting,
  theme,
  onToggleTheme,
}) => {
  const modes: { id: AppMode; label: string; icon: any; color: string; activeBg: string }[] = [
    {
      id: 'explore',
      label: 'Explore Database',
      icon: Compass,
      color: 'text-blue-600 dark:text-blue-400',
      activeBg: 'bg-blue-50 text-blue-700 border-blue-300 dark:bg-blue-950/60 dark:text-blue-300 dark:border-blue-700',
    },
    {
      id: 'modify',
      label: 'Modify Database',
      icon: Database,
      color: 'text-amber-600 dark:text-amber-400',
      activeBg: 'bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-700',
    },
    {
      id: 'analyze',
      label: 'Analyze & Report',
      icon: LineChart,
      color: 'text-indigo-600 dark:text-indigo-400',
      activeBg: 'bg-indigo-50 text-indigo-700 border-indigo-300 dark:bg-indigo-950/60 dark:text-indigo-300 dark:border-indigo-700',
    },
  ];

  return (
    <header className="h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-4 sm:px-6 flex items-center justify-between shrink-0 select-none z-20 transition-colors">
      {/* Left: Brand & Tagline */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-blue-600 text-white shadow-sm">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <span className="font-bold text-slate-900 dark:text-slate-100 tracking-tight text-base block leading-tight">
              AgentCampus
            </span>
            <span className="text-[10px] text-slate-500 dark:text-slate-400 hidden sm:inline-block font-medium">
              Intelligent Multi-Agent System
            </span>
          </div>
        </div>
      </div>

      {/* Center: 3 Primary Modes Selector */}
      <div className="flex items-center bg-slate-100 dark:bg-slate-800/80 p-1 rounded-2xl border border-slate-200 dark:border-slate-700/80 gap-1 shadow-inner">
        {modes.map((m) => {
          const Icon = m.icon;
          const isActive = currentMode === m.id;

          return (
            <div key={m.id} className="flex items-center">
              <button
                onClick={() => onSelectMode(m.id)}
                disabled={isExecuting}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer disabled:opacity-50 ${
                  isActive
                    ? `${m.activeBg} shadow-xs border`
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-white/50 dark:hover:bg-slate-700/50'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? '' : m.color}`} />
                <span className="hidden md:inline">{m.label}</span>
                <span className="md:hidden">
                  {m.id === 'explore' ? 'Explore' : m.id === 'modify' ? 'Modify' : 'Analyze'}
                </span>
              </button>
              {isActive && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenModeInfo(m.id);
                  }}
                  className="p-1 text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 rounded-md transition-colors mr-0.5"
                  title={`Learn more about ${m.label}`}
                >
                  <HelpCircle className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Right: DB Preview, Reset, Theme Toggle */}
      <div className="flex items-center gap-2">
        {/* Current Mode Warning Indicator */}
        <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-[11px] font-medium border bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700">
          {currentMode === 'modify' ? (
            <>
              <AlertTriangle className="w-3 h-3 text-amber-500" />
              <span className="text-amber-700 dark:text-amber-400">Mutations Active</span>
            </>
          ) : (
            <>
              <ShieldCheck className="w-3 h-3 text-emerald-500" />
              <span className="text-emerald-700 dark:text-emerald-400">Read-Only</span>
            </>
          )}
        </div>

        {/* Database Preview Button */}
        <button
          onClick={onOpenDatabasePreview}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 transition-all cursor-pointer active:scale-95 shadow-xs"
          title="Open Live Database Preview"
        >
          <Database className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
          <span className="hidden sm:inline">DB Preview</span>
        </button>

        {/* Reset Database Button */}
        <button
          onClick={onResetDb}
          disabled={isExecuting}
          className="p-2 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 rounded-xl transition-all cursor-pointer disabled:opacity-50"
          title="Reset Database to Default Seed"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>

        {/* Theme Toggle (Sun/Moon) */}
        <button
          onClick={onToggleTheme}
          className="p-2 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 rounded-xl transition-all cursor-pointer"
          title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
        >
          {theme === 'dark' ? (
            <Sun className="w-3.5 h-3.5 text-amber-400" />
          ) : (
            <Moon className="w-3.5 h-3.5 text-slate-600" />
          )}
        </button>
      </div>
    </header>
  );
};
