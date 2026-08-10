import React from 'react';
import { Bot, Database, RefreshCw } from 'lucide-react';

interface HeaderProps {
  studentCount: number;
  activeAgentsCount: number;
  onResetDb: () => void;
  onOpenDataViewer: () => void;
  isExecuting: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  studentCount,
  activeAgentsCount,
  onResetDb,
  onOpenDataViewer,
  isExecuting
}) => {
  return (
    <header className="h-14 bg-white border-b border-gray-200 px-5 flex items-center justify-between shrink-0 select-none z-20">
      {/* Brand & Agents Online status */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-50 border border-blue-200 text-blue-600">
            <Bot className="w-5 h-5" />
          </div>
          <span className="font-bold text-gray-900 tracking-tight text-base">
            AgentCampus
          </span>
        </div>

        <div className="h-4 w-px bg-gray-200" />

        <div className="flex items-center gap-2 text-xs text-gray-500 font-medium">
          <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
          <span>Agents Online</span>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2">
        <button
          onClick={onOpenDataViewer}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 border border-gray-200 transition-all cursor-pointer shadow-xs active:scale-95"
          title="Open Campus Database Browser"
        >
          <Database className="w-3.5 h-3.5 text-gray-600" />
          <span>Database</span>
        </button>

        <button
          onClick={onResetDb}
          disabled={isExecuting}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-gray-500 hover:text-gray-800 bg-gray-50 hover:bg-gray-100 border border-gray-200 transition-all cursor-pointer disabled:opacity-50"
          title="Reset Campus DB to Initial Seed"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Reset DB</span>
        </button>
      </div>
    </header>
  );
};

