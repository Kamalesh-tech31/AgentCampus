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
  Code,
  Sparkles,
  ArrowUpRight
} from 'lucide-react';
import { AgentState, AgentType, Turn } from '../types';

interface CenterPanelProps {
  turns: Turn[];
  selectedTurnId?: string;
  onSelectTurn: (turnId: string) => void;
  isExecuting: boolean;
  onOpenJsonModal: (title: string, data: any) => void;
  onSelectPreset?: (prompt: string) => void;
}

const PRESET_PROMPTS = [
  { label: 'Top 10 CS Students', prompt: 'Show top 10 Computer Science students ordered by CGPA with high attendance' },
  { label: 'Mechanical Dept Avg', prompt: 'Calculate average CGPA and score metrics for the Mechanical department' },
  { label: 'Update Rahul CGPA to 9.5', prompt: "Update Rahul Sharma's CGPA to 9.5 and recalculate Computer Science average" },
  { label: 'Low Attendance (<75%)', prompt: 'Find all students with attendance below 75% and show probation list' },
  { label: 'Add New Student', prompt: 'Add new student Ananya Roy with 8.9 CGPA in Electronics department' }
];

const AGENT_CONFIG: Record<AgentType, { name: string; role: string; icon: any }> = {
  input: {
    name: 'Input Agent',
    role: 'Parsing natural language intent',
    icon: Bot
  },
  mother: {
    name: 'Mother Agent',
    role: 'Orchestrating execution plan',
    icon: Cpu
  },
  db: {
    name: 'DB Agent',
    role: 'Executing database queries',
    icon: Database
  },
  analytics: {
    name: 'Analytics Agent',
    role: 'Calculating statistical metrics',
    icon: BarChart3
  },
  output: {
    name: 'Output Agent',
    role: 'Formatting tables and summary',
    icon: FileCheck
  }
};

export const CenterPanel: React.FC<CenterPanelProps> = ({
  turns,
  selectedTurnId,
  onSelectTurn,
  isExecuting,
  onOpenJsonModal,
  onSelectPreset
}) => {
  const [expandedAgentCards, setExpandedAgentCards] = useState<Record<string, boolean>>({});
  const [collapsedFlows, setCollapsedFlows] = useState<Record<string, boolean>>({});
  const chatBottomRef = useRef<HTMLDivElement>(null);

  const toggleAgentCard = (cardKey: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedAgentCards(prev => ({ ...prev, [cardKey]: !prev[cardKey] }));
  };

  const agentOrder: AgentType[] = ['input', 'mother', 'db', 'analytics', 'output'];

  // Auto-scroll to bottom on new turn or when executing
  useEffect(() => {
    if (chatBottomRef.current) {
      chatBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [turns.length, isExecuting]);

  const handleTurnClick = (turnId: string) => {
    onSelectTurn(turnId);
    // Uncollapse flow when selecting
    setCollapsedFlows(prev => ({ ...prev, [turnId]: false }));
  };

  const handleToggleFlow = (turnId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setCollapsedFlows(prev => {
      const currentlyCollapsed = !!prev[turnId];
      if (currentlyCollapsed) {
        onSelectTurn(turnId);
      }
      return { ...prev, [turnId]: !currentlyCollapsed };
    });
  };

  return (
    <div className="flex-1 h-full bg-slate-50 flex flex-col min-w-0 overflow-hidden select-none">
      {/* Top Header Banner */}
      <div className="p-3.5 border-b border-gray-200 bg-white flex items-center justify-between shrink-0 h-14">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="p-1.5 rounded-lg bg-blue-50 border border-blue-200 text-blue-600 shrink-0">
            <Cpu className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xs font-semibold text-gray-900 truncate">
              Execution Thread
            </h2>
            <p className="text-[11px] text-gray-500 truncate mt-0.5">
              {turns.length} {turns.length === 1 ? 'request' : 'requests'} in this session
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[11px] font-medium text-gray-500 bg-gray-100 px-2.5 py-0.5 rounded-full border border-gray-200">
            {turns.length} Turns
          </span>
        </div>
      </div>

      {/* Content Area */}
      {turns.length === 0 ? (
        <div className="flex-1 overflow-y-auto p-6 flex flex-col items-center justify-center custom-scrollbar">
          <div className="max-w-lg w-full space-y-6 text-center">
            <div className="w-12 h-12 rounded-2xl bg-blue-50 border border-blue-200 text-blue-600 flex items-center justify-center mx-auto shadow-xs">
              <Sparkles className="w-6 h-6" />
            </div>

            <div>
              <h2 className="text-base font-semibold text-gray-900">
                What would you like to query?
              </h2>
              <p className="text-xs text-gray-500 mt-1">
                Select a sample prompt below or type your custom query in the bottom bar.
              </p>
            </div>

            <div className="space-y-2 text-left">
              {PRESET_PROMPTS.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => onSelectPreset?.(item.prompt)}
                  disabled={isExecuting}
                  className="w-full text-left p-3.5 rounded-xl bg-white hover:bg-blue-50/60 border border-gray-200 hover:border-blue-300 transition-all cursor-pointer group shadow-xs flex items-center justify-between active:scale-[0.99]"
                >
                  <div className="min-w-0 pr-3">
                    <span className="text-xs font-semibold text-gray-800 group-hover:text-blue-600 transition-colors block truncate">
                      {item.label}
                    </span>
                    <span className="text-[11px] text-gray-500 truncate block mt-0.5">
                      {item.prompt}
                    </span>
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-gray-400 group-hover:text-blue-600 shrink-0 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        /* Continuous Chat Thread */
        <div className="flex-1 overflow-y-auto p-4 lg:p-6 space-y-6 custom-scrollbar">
          <div className="max-w-3xl mx-auto space-y-6">
            {turns.map((turn) => {
              const isSelected = selectedTurnId === turn.id;
              const isTurnCollapsed = !!collapsedFlows[turn.id];
              const isExpanded = isSelected && !isTurnCollapsed;

              const isTurnComplete = turn.status === 'complete';
              const isTurnRunning = turn.status === 'running';
              const isTurnFailed = turn.status === 'failed';

              return (
                <div key={turn.id} className="space-y-3">
                  {/* User Request Bubble */}
                  <div className="flex justify-end">
                    <div
                      onClick={() => handleTurnClick(turn.id)}
                      className={`px-4 py-2.5 rounded-2xl rounded-tr-xs text-xs font-medium max-w-[85%] cursor-pointer transition-all ${
                        isSelected
                          ? 'bg-blue-600 text-white shadow-sm ring-2 ring-blue-300'
                          : 'bg-blue-600/90 text-white hover:bg-blue-600 shadow-xs'
                      }`}
                    >
                      {turn.prompt}
                    </div>
                  </div>

                  {/* Foldable Execution Flow Block */}
                  <div
                    className={`rounded-2xl border transition-all bg-white overflow-hidden ${
                      isSelected
                        ? 'border-blue-400 ring-2 ring-blue-500/15 shadow-sm'
                        : 'border-gray-200 hover:border-gray-300 shadow-xs'
                    }`}
                  >
                    {!isExpanded ? (
                      /* Collapsed 1-Line Execution Flow Summary */
                      <div 
                        onClick={() => handleTurnClick(turn.id)}
                        className="p-3 flex items-center justify-between text-xs hover:bg-gray-50/80 transition-colors cursor-pointer"
                      >
                        <div className="flex items-center gap-2 min-w-0 pr-2">
                          {isTurnComplete && <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0" />}
                          {isTurnRunning && <Clock className="w-4 h-4 text-blue-600 animate-spin shrink-0" />}
                          {isTurnFailed && <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />}

                          <span className="text-gray-800 font-semibold truncate">
                            Execution Flow
                          </span>
                          <span className="text-gray-300">•</span>
                          <span className="text-gray-600 font-medium shrink-0">
                            {turn.durationMs ? `${(turn.durationMs / 1000).toFixed(2)}s` : isTurnRunning ? 'Running...' : 'Completed'}
                          </span>
                          <span className="text-gray-300 hidden sm:inline">•</span>
                          <span className="text-gray-500 text-[11px] hidden sm:inline truncate">
                            5 agents {isTurnRunning ? 'in progress' : isTurnFailed ? 'failed' : 'completed'}
                          </span>
                        </div>

                        <button
                          type="button"
                          onClick={(e) => handleToggleFlow(turn.id, e)}
                          className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-gray-200/70 text-gray-500 hover:text-gray-800 transition-colors shrink-0 cursor-pointer"
                          title="Expand Execution Flow"
                        >
                          <ChevronDown className="w-4 h-4" />
                        </button>
                      </div>
                    ) : (
                      /* Expanded Full Execution Stepper */
                      <div>
                        {/* Header Bar */}
                        <div className="p-3 bg-gray-50/90 border-b border-gray-200 flex items-center justify-between">
                          <div className="flex items-center gap-2 min-w-0 pr-2">
                            <Cpu className="w-4 h-4 text-blue-600 shrink-0" />
                            <span className="text-xs font-semibold text-gray-900 truncate">
                              Execution Flow
                            </span>
                            {turn.durationMs && (
                              <span className="text-[11px] font-medium text-gray-500 bg-white px-2 py-0.5 rounded-full border border-gray-200 shrink-0">
                                {(turn.durationMs / 1000).toFixed(2)}s
                              </span>
                            )}
                            <span className="text-[11px] text-gray-500 hidden sm:inline truncate">
                              • 5 agents {isTurnRunning ? 'in progress' : isTurnFailed ? 'failed' : 'completed'}
                            </span>
                          </div>

                          <button
                            type="button"
                            onClick={(e) => handleToggleFlow(turn.id, e)}
                            className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-gray-200/80 text-gray-500 hover:text-gray-800 transition-colors shrink-0 cursor-pointer"
                            title="Collapse Execution Flow"
                          >
                            <ChevronUp className="w-4 h-4" />
                          </button>
                        </div>

                        {/* Stepper Content */}
                        <div className="p-4 space-y-0">
                          {agentOrder.map((agentId, index) => {
                            const agentState = turn.agents[agentId];
                            const config = AGENT_CONFIG[agentId];
                            const IconComponent = config.icon;

                            const cardKey = `${turn.id}-${agentId}`;
                            const isAgentExpanded = !!expandedAgentCards[cardKey];
                            const isWaiting = agentState.status === 'waiting';
                            const isRunning = agentState.status === 'running';
                            const isComplete = agentState.status === 'complete';
                            const isFailed = agentState.status === 'failed';

                            return (
                              <div key={agentId} className="relative pl-6 pb-5 last:pb-0">
                                {/* Vertical Line */}
                                {index < agentOrder.length - 1 && (
                                  <div
                                    className={`absolute left-[11px] top-5 bottom-0 w-0.5 transition-colors ${
                                      isComplete ? 'bg-blue-600' : 'bg-gray-200'
                                    }`}
                                  />
                                )}

                                {/* Step Node Dot */}
                                <div className="absolute left-0 top-3 -translate-y-1/2 flex items-center justify-center">
                                  {isWaiting && (
                                    <div className="w-5 h-5 rounded-full bg-white border-2 border-gray-300 flex items-center justify-center">
                                      <div className="w-1.5 h-1.5 rounded-full bg-gray-300" />
                                    </div>
                                  )}
                                  {isRunning && (
                                    <div className="relative w-5 h-5 flex items-center justify-center">
                                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                                      <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-blue-600" />
                                    </div>
                                  )}
                                  {isComplete && (
                                    <div className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center">
                                      <CheckCircle2 className="w-3.5 h-3.5" />
                                    </div>
                                  )}
                                  {isFailed && (
                                    <div className="w-5 h-5 rounded-full bg-red-600 text-white flex items-center justify-center">
                                      <AlertCircle className="w-3.5 h-3.5" />
                                    </div>
                                  )}
                                </div>

                                {/* Agent Card */}
                                <div
                                  className={`ml-2 bg-white rounded-xl border transition-all ${
                                    isRunning
                                      ? 'border-blue-400 ring-2 ring-blue-100 shadow-xs'
                                      : isComplete
                                      ? 'border-gray-200 hover:border-gray-300'
                                      : isFailed
                                      ? 'border-red-300 bg-red-50/20'
                                      : 'border-gray-200 opacity-60'
                                  }`}
                                >
                                  {/* Agent Header */}
                                  <div
                                    onClick={(e) => toggleAgentCard(cardKey, e)}
                                    className="p-3 flex items-center justify-between cursor-pointer hover:bg-gray-50/80 rounded-xl transition-colors"
                                  >
                                    <div className="flex items-center gap-3 min-w-0">
                                      <div className={`p-1.5 rounded-lg ${isComplete || isRunning ? 'bg-blue-50 text-blue-600' : 'bg-gray-100 text-gray-500'}`}>
                                        <IconComponent className="w-3.5 h-3.5" />
                                      </div>
                                      <div className="min-w-0">
                                        <h3 className="text-xs font-semibold text-gray-900">
                                          {config.name}
                                        </h3>
                                        <p className="text-[11px] text-gray-500 truncate mt-0.5">
                                          {agentState.statusMessage || config.role}
                                        </p>
                                      </div>
                                    </div>

                                    <div className="flex items-center gap-2 shrink-0">
                                      {agentState.durationMs && (
                                        <span className="text-[10px] font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full border border-gray-200">
                                          {(agentState.durationMs / 1000).toFixed(2)}s
                                        </span>
                                      )}
                                      <button
                                        type="button"
                                        className="p-1 text-gray-400 hover:text-gray-600 rounded-md transition-colors"
                                      >
                                        {isAgentExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                                      </button>
                                    </div>
                                  </div>

                                  {/* Agent Details */}
                                  {isAgentExpanded && (
                                    <div className="p-3 border-t border-gray-100 bg-gray-50/50 rounded-b-xl space-y-2">
                                      {(agentState.inputData || agentState.outputData) && (
                                        <div className="flex items-center justify-between">
                                          <span className="text-[11px] font-medium text-gray-600">Payload Details</span>
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              onOpenJsonModal(`${config.name} Data`, agentState.outputData || agentState.inputData);
                                            }}
                                            className="flex items-center gap-1 text-[11px] font-medium text-blue-600 hover:text-blue-700 cursor-pointer"
                                          >
                                            <Code className="w-3 h-3" />
                                            <span>View JSON</span>
                                          </button>
                                        </div>
                                      )}

                                      {agentState.logs.length > 0 && (
                                        <div className="space-y-1 pt-1">
                                          <span className="text-[11px] font-medium text-gray-500 block">Activity Summary:</span>
                                          <div className="bg-white p-2 rounded-lg border border-gray-200 text-xs text-gray-700 space-y-1 font-mono">
                                            {agentState.logs.map((log) => (
                                              <div key={log.id} className="leading-relaxed">
                                                • {log.message}
                                              </div>
                                            ))}
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
            <div ref={chatBottomRef} />
          </div>
        </div>
      )}
    </div>
  );
};
