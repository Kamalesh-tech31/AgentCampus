import React, { useState, useEffect, useRef } from 'react';
import { 
  Bot, 
  Cpu, 
  Database, 
  BarChart3, 
  FileCheck, 
  CheckCircle2, 
  AlertCircle, 
  Clock, 
  ChevronDown, 
  ChevronUp, 
  Sparkles, 
  ArrowRight,
  Compass,
  LineChart,
  Code
} from 'lucide-react';
import { AgentState, AgentType, Turn, AppMode } from '../types';

interface CenterPanelProps {
  turns: Turn[];
  selectedTurnId?: string;
  onSelectTurn: (turnId: string) => void;
  isExecuting: boolean;
  currentMode: AppMode;
  onOpenJsonModal: (title: string, data: any) => void;
  onSelectPreset: (prompt: string) => void;
}

const AGENT_CONFIG: Record<AgentType, { name: string; role: string; icon: any; color: string }> = {
  input: {
    name: 'Input Agent',
    role: 'Parsing intent & entities',
    icon: Bot,
    color: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/60 border-blue-200 dark:border-blue-800'
  },
  mother: {
    name: 'Mother Agent',
    role: 'Synthesizing dynamic workflow',
    icon: Cpu,
    color: 'text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/60 border-purple-200 dark:border-purple-800'
  },
  db: {
    name: 'DB Agent',
    role: 'Querying / mutating database',
    icon: Database,
    color: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/60 border-amber-200 dark:border-amber-800'
  },
  analytics: {
    name: 'Pulse Analytics',
    role: 'Calculating statistical metrics',
    icon: BarChart3,
    color: 'text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 border-indigo-200 dark:border-indigo-800'
  },
  output: {
    name: 'Scribe Output',
    role: 'Formatting tables and reports',
    icon: FileCheck,
    color: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 border-emerald-200 dark:border-emerald-800'
  }
};

const MODE_WELCOME_PROMPTS: Record<AppMode, { title: string; subtitle: string; prompts: string[] }> = {
  modify: {
    title: 'Modify Database Mode',
    subtitle: 'Enter a mutation request to safely update or delete records.',
    prompts: [
      "Change Rahul's CGPA to 9.2",
      "Update Arun's attendance to 95%",
      "Delete all students with CGPA below 5",
      "Add new student Ananya Roy in Computer Science with 9.1 CGPA"
    ]
  },
  explore: {
    title: 'Explore Database Mode',
    subtitle: 'Search and inspect database records without altering data.',
    prompts: [
      "Show the top 10 CSE students",
      "Find all students with CGPA above 9.0",
      "List all students in Electronics with attendance below 75%",
      "Show all active students ordered by roll number"
    ]
  },
  analyze: {
    title: 'Analyze & Report Mode',
    subtitle: 'Request deep analytics, rankings, comparisons, and exportable reports.',
    prompts: [
      "Rank the top 10 students using 80% marks and 20% LeetCode count",
      "Find academically at-risk students and explain reasons",
      "Compare Computer Science and Electronics department performance",
      "Analyze attendance correlation with CGPA and create a detailed report in PDF"
    ]
  }
};

export const CenterPanel: React.FC<CenterPanelProps> = ({
  turns,
  selectedTurnId,
  onSelectTurn,
  isExecuting,
  currentMode,
  onOpenJsonModal,
  onSelectPreset,
}) => {
  const [expandedAgentCards, setExpandedAgentCards] = useState<Record<string, boolean>>({});
  const chatBottomRef = useRef<HTMLDivElement>(null);

  const toggleAgentCard = (cardKey: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedAgentCards(prev => ({ ...prev, [cardKey]: !prev[cardKey] }));
  };

  // Auto-scroll to bottom on new turn or when executing
  useEffect(() => {
    if (chatBottomRef.current) {
      chatBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [turns.length, isExecuting]);

  const welcome = MODE_WELCOME_PROMPTS[currentMode] || MODE_WELCOME_PROMPTS.explore;

  return (
    <div className="flex-1 h-full bg-slate-50 dark:bg-slate-900 flex flex-col min-w-0 overflow-hidden select-none transition-colors">
      {/* Top Header Banner */}
      <div className="p-3.5 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center justify-between shrink-0 h-14">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="p-1.5 rounded-lg bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400 shrink-0">
            <Cpu className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xs font-bold text-slate-900 dark:text-slate-100 truncate">
              Execution Timeline
            </h2>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
              {turns.length} {turns.length === 1 ? 'request' : 'requests'} in this session
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 px-2.5 py-0.5 rounded-full border border-slate-200 dark:border-slate-700">
            {turns.length} Turns
          </span>
        </div>
      </div>

      {/* Content Area */}
      {turns.length === 0 ? (
        <div className="flex-1 overflow-y-auto p-6 flex flex-col items-center justify-center custom-scrollbar">
          <div className="max-w-lg w-full space-y-6 text-center">
            <div className="w-12 h-12 rounded-2xl bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400 flex items-center justify-center mx-auto shadow-xs">
              <Sparkles className="w-6 h-6" />
            </div>

            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
                {welcome.title}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                {welcome.subtitle}
              </p>
            </div>

            <div className="space-y-2 text-left">
              {welcome.prompts.map((promptText, idx) => (
                <button
                  key={idx}
                  onClick={() => onSelectPreset(promptText)}
                  className="w-full text-left p-3 rounded-xl bg-white dark:bg-slate-800/80 hover:bg-blue-50/70 dark:hover:bg-slate-700/80 border border-slate-200 dark:border-slate-700 hover:border-blue-300 dark:hover:border-blue-600 transition-all flex items-center justify-between text-xs font-medium text-slate-700 dark:text-slate-200 group shadow-xs cursor-pointer"
                >
                  <span className="truncate pr-3">"{promptText}"</span>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-blue-600 dark:group-hover:text-blue-400 shrink-0 transition-transform group-hover:translate-x-1" />
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
          {turns.map((turn, turnIdx) => {
            const isSelected = selectedTurnId === turn.id;
            const turnAgents = Object.values(turn.agents).filter((a) => {
              // Only render analytics agent if it actually ran or in analyze mode
              if (a.id === 'analytics') {
                return turn.mode === 'analyze' || a.status !== 'waiting';
              }
              return true;
            });

            return (
              <div
                key={turn.id}
                onClick={() => onSelectTurn(turn.id)}
                className={`p-4 rounded-2xl border transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-white dark:bg-slate-800/90 border-blue-400 dark:border-blue-500 shadow-md ring-1 ring-blue-100 dark:ring-blue-900/40'
                    : 'bg-white/60 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700/80 hover:border-slate-300 dark:hover:border-slate-600 shadow-xs'
                }`}
              >
                {/* Turn Header */}
                <div className="flex items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-700/80">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-[11px] font-bold shrink-0">
                      {turnIdx + 1}
                    </span>
                    <span className="text-xs font-bold text-slate-900 dark:text-slate-100 truncate">
                      "{turn.prompt}"
                    </span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
                      {turn.mode}
                    </span>
                    <span className="text-[11px] text-slate-400">
                      {turn.timestamp}
                    </span>
                  </div>
                </div>

                {/* Agents Timeline Sequence */}
                <div className="pt-3 space-y-2.5">
                  {turnAgents.map((agent) => {
                    const cfg = AGENT_CONFIG[agent.id] || AGENT_CONFIG.input;
                    const Icon = cfg.icon;
                    const isDone = agent.status === 'complete';
                    const isRunning = agent.status === 'running';
                    const isFailed = agent.status === 'failed';
                    const cardKey = `${turn.id}-${agent.id}`;
                    const isExpanded = !!expandedAgentCards[cardKey];

                    return (
                      <div
                        key={agent.id}
                        className={`rounded-xl border transition-all overflow-hidden ${
                          isRunning
                            ? 'border-blue-400 dark:border-blue-500 bg-blue-50/20 dark:bg-blue-950/20 shadow-xs'
                            : isDone
                            ? 'border-slate-200 dark:border-slate-700/80 bg-slate-50/50 dark:bg-slate-800/40'
                            : isFailed
                            ? 'border-rose-300 dark:border-rose-800 bg-rose-50/20'
                            : 'border-slate-200 dark:border-slate-700/40 opacity-50'
                        }`}
                      >
                        {/* Agent Card Header */}
                        <div
                          onClick={(e) => toggleAgentCard(cardKey, e)}
                          className="p-2.5 flex items-center justify-between cursor-pointer hover:bg-slate-100/50 dark:hover:bg-slate-700/40 transition-colors"
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className={`p-1.5 rounded-lg border ${cfg.color} shrink-0`}>
                              <Icon className="w-3.5 h-3.5" />
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-bold text-slate-900 dark:text-slate-100 truncate">
                                  {cfg.name}
                                </span>
                                <span className="text-[10px] text-slate-400 font-mono hidden sm:inline">
                                  {agent.badge}
                                </span>
                              </div>
                              <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                                {agent.statusMessage || cfg.role}
                              </p>
                            </div>
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            {isDone && <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />}
                            {isRunning && <Clock className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-spin" />}
                            {isFailed && <AlertCircle className="w-4 h-4 text-rose-600" />}
                            {agent.logs.length > 0 && (
                              <span className="text-slate-400">
                                {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Expandable Agent Logs & Payload */}
                        {isExpanded && agent.logs.length > 0 && (
                          <div className="p-3 bg-slate-900 text-slate-200 border-t border-slate-800 text-[11px] font-mono space-y-1.5 max-h-48 overflow-y-auto custom-scrollbar">
                            {agent.logs.map((log) => (
                              <div key={log.id} className="flex items-start gap-2">
                                <span className="text-slate-500 shrink-0">[{log.timestamp}]</span>
                                <span className={
                                  log.level === 'error' ? 'text-rose-400' :
                                  log.level === 'success' ? 'text-emerald-400' :
                                  log.level === 'working' ? 'text-blue-400' : 'text-slate-300'
                                }>
                                  {log.message}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
          <div ref={chatBottomRef} />
        </div>
      )}
    </div>
  );
};
