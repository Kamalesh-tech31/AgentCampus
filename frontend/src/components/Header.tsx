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
    <header className="h-16 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border-b border-slate-200/80 dark:border-slate-800/80 px-4 sm:px-6 flex items-center justify-between shrink-0 select-none z-30 transition-colors shadow-2xs">
      {/* Left: Brand & Tagline */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 text-white shadow-xs ring-1 ring-blue-500/30">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-slate-900 dark:text-slate-50 tracking-tight text-base leading-none">
                AgentCampus
              </span>
              <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300 border border-blue-200 dark:border-blue-800 leading-none">
                Enterprise
              </span>
            </div>
            <span className="text-[11px] text-slate-500 dark:text-slate-400 hidden sm:inline-block font-normal mt-0.5">
              Autonomous Multi-Agent Academic Intelligence
            </span>
          </div>
        </div>
      </div>

      {/* Center: 3 Primary Modes Selector */}
      <div className="flex items-center bg-slate-100/90 dark:bg-slate-800/90 p-1 rounded-2xl border border-slate-200 dark:border-slate-700/80 gap-1 shadow-2xs">
        {modes.map((m) => {
          const Icon = m.icon;
          const isActive = currentMode === m.id;

          return (
            <div key={m.id} className="flex items-center">
              <button
                onClick={() => onSelectMode(m.id)}
                disabled={isExecuting}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer disabled:opacity-50 ${
                  isActive
                    ? `${m.activeBg} shadow-xs border font-bold`
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-white/60 dark:hover:bg-slate-700/60'
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

      {/* Right: Status Pill, DB Preview, Reset, Theme Toggle */}
      <div className="flex items-center gap-2.5">
        {/* Live Status Indicator */}
        <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-medium border bg-slate-50/80 dark:bg-slate-800/80 border-slate-200/80 dark:border-slate-700/80 shadow-2xs">
          {currentMode === 'modify' ? (
            <>
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
              <span className="text-amber-700 dark:text-amber-300 font-semibold text-[11.5px]">Mutations Active</span>
            </>
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="text-emerald-700 dark:text-emerald-300 font-semibold text-[11.5px]">Read-Only</span>
            </>
          )}
        </div>

        {/* Database Preview Button */}
        <button
          onClick={onOpenDatabasePreview}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700/80 border border-slate-200 dark:border-slate-700 transition-all cursor-pointer active:scale-95 shadow-2xs hover:shadow-xs"
          title="Open Live Database Preview"
        >
          <Database className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
          <span className="hidden sm:inline">Live DB</span>
        </button>

        {/* Reset Database Button */}
        <button
          onClick={onResetDb}
          disabled={isExecuting}
          className="p-2 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700/80 border border-slate-200 dark:border-slate-700 rounded-xl transition-all cursor-pointer disabled:opacity-50 shadow-2xs"
          title="Reset Database to Default Seed"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>

        {/* Theme Toggle (Sun/Moon) */}
        <button
          onClick={onToggleTheme}
          className="p-2 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700/80 border border-slate-200 dark:border-slate-700 rounded-xl transition-all cursor-pointer shadow-2xs"
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
