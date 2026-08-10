import React, { useState } from 'react';
import { 
  Plus, 
  History, 
  PanelLeftClose, 
  PanelLeftOpen, 
  CheckCircle2, 
  AlertCircle, 
  Clock,
  MessageSquare
} from 'lucide-react';
import { ChatThread } from '../types';

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
  onNewThread
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <div
      className={`${
        isCollapsed ? 'w-16' : 'w-72 lg:w-80'
      } h-full bg-slate-50 border-r border-gray-200 flex flex-col shrink-0 select-none overflow-hidden transition-all duration-300 ease-in-out`}
    >
      {/* Panel Header */}
      <div className="p-3.5 border-b border-gray-200 bg-white flex items-center justify-between shrink-0 h-14">
        {!isCollapsed && (
          <div className="flex items-center gap-2 min-w-0">
            <History className="w-4 h-4 text-blue-600 shrink-0" />
            <span className="text-xs font-semibold text-gray-900 tracking-tight truncate">
              Conversations
            </span>
            <span className="text-[11px] font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full border border-gray-200">
              {threads.length}
            </span>
          </div>
        )}

        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className={`p-1.5 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors cursor-pointer ${
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
      <div className="p-3 border-b border-gray-200 bg-white shrink-0">
        {isCollapsed ? (
          <button
            onClick={onNewThread}
            className="w-10 h-10 mx-auto bg-blue-600 hover:bg-blue-700 text-white rounded-xl flex items-center justify-center transition-all cursor-pointer shadow-xs active:scale-95"
            title="New Chat"
          >
            <Plus className="w-5 h-5" />
          </button>
        ) : (
          <button
            onClick={onNewThread}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-3 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-xl transition-all cursor-pointer shadow-xs active:scale-95"
          >
            <Plus className="w-4 h-4" />
            <span>New Chat</span>
          </button>
        )}
      </div>

      {/* Threads List */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-1.5 custom-scrollbar">
        {threads.length === 0 ? (
          !isCollapsed && (
            <div className="p-4 text-center rounded-xl bg-white border border-dashed border-gray-200 text-gray-400 text-xs mt-2">
              No conversations yet...
            </div>
          )
        ) : (
          threads.map((thread) => {
            const isSelected = selectedThreadId === thread.id;
            const turnCount = thread.turns.length;
            const latestTurn = thread.turns[thread.turns.length - 1];
            const isRunning = thread.turns.some(t => t.status === 'running');
            const isFailed = thread.turns.some(t => t.status === 'failed');

            return isCollapsed ? (
              <button
                key={thread.id}
                onClick={() => onSelectThread(thread.id)}
                className={`w-10 h-10 mx-auto rounded-xl flex items-center justify-center border transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-blue-50 border-blue-300 text-blue-600'
                    : 'bg-white border-gray-200 hover:border-gray-300 text-gray-600'
                }`}
                title={thread.title}
              >
                {isRunning ? (
                  <Clock className="w-4 h-4 text-blue-600 animate-pulse" />
                ) : isFailed ? (
                  <AlertCircle className="w-4 h-4 text-red-600" />
                ) : (
                  <MessageSquare className="w-4 h-4 text-blue-600" />
                )}
              </button>
            ) : (
              <div
                key={thread.id}
                onClick={() => onSelectThread(thread.id)}
                className={`p-3 rounded-xl border transition-all cursor-pointer flex flex-col gap-1 ${
                  isSelected
                    ? 'bg-blue-50/80 border-blue-300 text-gray-900 shadow-xs'
                    : 'bg-white border-gray-200 hover:border-gray-300 text-gray-800 shadow-xs'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold truncate flex-1 text-gray-800">
                    {thread.title}
                  </span>
                  <div className="flex items-center gap-1 shrink-0">
                    {isRunning && <Clock className="w-3.5 h-3.5 text-blue-600 animate-pulse" />}
                    {!isRunning && isFailed && <AlertCircle className="w-3.5 h-3.5 text-red-600" />}
                    {!isRunning && !isFailed && <CheckCircle2 className="w-3.5 h-3.5 text-blue-600" />}
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-gray-400 mt-0.5">
                  <span>{turnCount} {turnCount === 1 ? 'msg' : 'msgs'}</span>
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
