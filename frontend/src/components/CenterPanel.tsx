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
  Download,
  Copy,
  Check
} from 'lucide-react';
import { AgentState, AgentType, Turn, AppMode } from '../types';
import { getFileDownloadUrl } from '../services/api';
import { getFreshSuggestions, SuggestionItem } from '../data/suggestions';

interface CenterPanelProps {
  turns: Turn[];
  selectedTurnId?: string;
  onSelectTurn: (turnId: string) => void;
  isExecuting: boolean;
  currentMode: AppMode;
  onOpenJsonModal: (title: string, data: any) => void;
  onSelectPreset: (prompt: string) => void;
  usedPrompts?: string[];
}

const AGENT_CONFIG: Record<AgentType, { name: string; role: string; icon: any; color: string; badgeColor: string }> = {
  input: {
    name: 'Input Agent',
    role: 'Parsing intent & entities',
    icon: Bot,
    color: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/60 border-blue-200 dark:border-blue-800',
    badgeColor: 'bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300 border-blue-200 dark:border-blue-800'
  },
  mother: {
    name: 'Mother Agent',
    role: 'Synthesizing dynamic workflow plan',
    icon: Cpu,
    color: 'text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/60 border-purple-200 dark:border-purple-800',
    badgeColor: 'bg-purple-100 dark:bg-purple-950 text-purple-800 dark:text-purple-300 border-purple-200 dark:border-purple-800'
  },
  db: {
    name: 'DB Agent',
    role: 'Querying & safe SQL operations',
    icon: Database,
    color: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/60 border-amber-200 dark:border-amber-800',
    badgeColor: 'bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800'
  },
  analytics: {
    name: 'Pulse Analytics',
    role: 'Computing statistical metrics & models',
    icon: BarChart3,
    color: 'text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 border-indigo-200 dark:border-indigo-800',
    badgeColor: 'bg-indigo-100 dark:bg-indigo-950 text-indigo-800 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800'
  },
  output: {
    name: 'Scribe Output',
    role: 'Formatting verified tables & export reports',
    icon: FileCheck,
    color: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 border-emerald-200 dark:border-emerald-800',
    badgeColor: 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
  }
};

const MODE_DESCRIPTIONS: Record<AppMode, { title: string; subtitle: string; icon: any }> = {
  modify: {
    title: 'Modify Database Mode',
    subtitle: 'Submit natural language requests to safely update, insert, or delete records. Requires explicit safety review before execution.',
    icon: Database
  },
  explore: {
    title: 'Explore Database Mode',
    subtitle: 'Search and inspect student records with complex conditions, sorting, and department filters in read-only safety.',
    icon: Compass
  },
  analyze: {
    title: 'Analyze & Report Mode',
    subtitle: 'Perform multi-factor risk assessment, weighted composite rankings, bivariate Pearson correlations, and generate executive PDF/PPT/Excel artifacts.',
    icon: LineChart
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
  usedPrompts = [],
}) => {
  const [expandedAgentCards, setExpandedAgentCards] = useState<Record<string, boolean>>({});
  const [copiedTurnId, setCopiedTurnId] = useState<string | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  const toggleAgentCard = (cardKey: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedAgentCards(prev => ({ ...prev, [cardKey]: !prev[cardKey] }));
  };

  const handleCopyText = (turnId: string, text: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopiedTurnId(turnId);
    setTimeout(() => setCopiedTurnId(null), 2000);
  };

  // Auto-scroll to bottom on new turn or when executing
  useEffect(() => {
    if (chatBottomRef.current) {
      chatBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [turns.length, isExecuting]);

  const modeInfo = MODE_DESCRIPTIONS[currentMode] || MODE_DESCRIPTIONS.explore;
  const ModeIcon = modeInfo.icon;
  const freshPresets = getFreshSuggestions(currentMode, usedPrompts, 4);

  return (
    <div className="flex-1 h-full bg-slate-50 dark:bg-slate-900 flex flex-col min-w-0 overflow-hidden select-none transition-colors">
      {/* Top Header Banner */}
      <div className="p-3.5 border-b border-slate-200/80 dark:border-slate-800/80 bg-white dark:bg-slate-900 flex items-center justify-between shrink-0 h-14 shadow-2xs">
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
            {turns.length} {turns.length === 1 ? 'Turn' : 'Turns'}
          </span>
        </div>
      </div>

      {/* Content Area */}
      {turns.length === 0 ? (
        <div className="flex-1 overflow-y-auto p-6 flex flex-col items-center justify-center custom-scrollbar">
          <div className="max-w-xl w-full space-y-6 text-center">
            {/* Icon & Title */}
            <div className="space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400 flex items-center justify-center mx-auto shadow-xs">
                <ModeIcon className="w-6 h-6" />
              </div>

              <div>
                <div className="flex items-center justify-center gap-2">
                  <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
                    {modeInfo.title}
                  </h2>
                  <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                    {currentMode}
                  </span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5 max-w-md mx-auto leading-relaxed">
                  {modeInfo.subtitle}
                </p>
              </div>
            </div>

            {/* Fresh Curated Suggestions Grid */}
            <div className="space-y-2 text-left pt-2">
              <div className="flex items-center justify-between px-1">
                <span className="text-[11px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                  Suggested Workflows
                </span>
                <span className="text-[10px] text-slate-400 dark:text-slate-500">
                  Click to populate input
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {freshPresets.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => onSelectPreset(item.prompt)}
                    className="p-3.5 rounded-xl bg-white dark:bg-slate-800/80 hover:bg-blue-50/70 dark:hover:bg-slate-700/80 border border-slate-200/80 dark:border-slate-700 hover:border-blue-300 dark:hover:border-blue-600 transition-all flex flex-col justify-between text-left group shadow-2xs cursor-pointer min-h-[90px]"
                  >
                    <div className="space-y-1">
                      <span className="text-[10px] font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wider block">
                        {item.category}
                      </span>
                      <p className="text-xs font-semibold text-slate-800 dark:text-slate-200 group-hover:text-blue-600 dark:group-hover:text-blue-400 line-clamp-2">
                        "{item.prompt}"
                      </p>
                    </div>
                    <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-700/60 mt-1">
                      <span className="text-[10px] text-slate-400 dark:text-slate-500 truncate max-w-[200px]">
                        {item.description}
                      </span>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-blue-600 dark:group-hover:text-blue-400 shrink-0 transition-transform group-hover:translate-x-1" />
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
          {turns.map((turn, turnIdx) => {
            const isSelected = selectedTurnId === turn.id;
            const turnAgents = (Object.values(turn.agents) as AgentState[]).filter((a: AgentState) => {
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
                    : 'bg-white/70 dark:bg-slate-800/50 border-slate-200/80 dark:border-slate-700/80 hover:border-slate-300 dark:hover:border-slate-600 shadow-2xs'
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
                    <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 border border-slate-200/60 dark:border-slate-600">
                      {turn.mode}
                    </span>
                    <span className="text-[11px] text-slate-400">
                      {turn.timestamp}
                    </span>
                  </div>
                </div>

                {/* Agents Timeline Sequence */}
                <div className="pt-3 space-y-2">
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
                            ? 'border-slate-200/80 dark:border-slate-700/80 bg-slate-50/50 dark:bg-slate-800/40'
                            : isFailed
                            ? 'border-rose-300 dark:border-rose-800 bg-rose-50/20'
                            : 'border-slate-200/60 dark:border-slate-700/40 opacity-50'
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

                {/* Assistant Response Card (Chat Answer) */}
                {turn.result?.summary && (
                  <div className="p-4 rounded-xl bg-white dark:bg-slate-850 border border-slate-200/90 dark:border-slate-700 shadow-2xs space-y-2.5 mt-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="p-1 rounded-md bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                          <Sparkles className="w-3.5 h-3.5" />
                        </div>
                        <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                          AgentCampus Analytical Answer
                        </span>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => handleCopyText(turn.id, turn.result?.summary || '', e)}
                          className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                          title="Copy answer to clipboard"
                        >
                          {copiedTurnId === turn.id ? (
                            <>
                              <Check className="w-3 h-3 text-emerald-500" />
                              <span className="text-emerald-600 dark:text-emerald-400 font-semibold">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3 h-3" />
                              <span>Copy</span>
                            </>
                          )}
                        </button>

                        {turn.result.outputFile && (
                          <a
                            href={getFileDownloadUrl(turn.result.outputFile)}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-50 dark:bg-blue-950/60 hover:bg-blue-100 dark:hover:bg-blue-900 border border-blue-200 dark:border-blue-800 text-[11px] font-semibold text-blue-600 dark:text-blue-400 transition-colors shadow-2xs"
                          >
                            <Download className="w-3.5 h-3.5" />
                            <span>Download {turn.result.outputFormat?.toUpperCase() || 'Report'}</span>
                          </a>
                        )}
                      </div>
                    </div>
                    <div className="text-xs text-slate-800 dark:text-slate-200 whitespace-pre-wrap font-sans leading-relaxed bg-slate-50/80 dark:bg-slate-900/70 p-3.5 rounded-lg border border-slate-200/60 dark:border-slate-800 font-mono text-[11.5px] max-h-96 overflow-y-auto custom-scrollbar">
                      {turn.result.summary}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          <div ref={chatBottomRef} />
        </div>
      )}
    </div>
  );
};
