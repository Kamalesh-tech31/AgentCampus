import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { LeftPanel } from './components/LeftPanel';
import { CenterPanel } from './components/CenterPanel';
import { RightPanel } from './components/RightPanel';
import { BottomInputBar } from './components/BottomInputBar';
import { DataViewerModal } from './components/DataViewerModal';
import { DatabasePreviewModal } from './components/DatabasePreviewModal';
import { ModeSelectorModal } from './components/ModeSelectorModal';
import { ConfirmationModal } from './components/ConfirmationModal';
import { JsonViewerModal } from './components/JsonViewerModal';
import { 
  AppMode, 
  OutputFormat, 
  AgentState, 
  AgentType, 
  ChatThread, 
  Turn, 
  StudentRecord, 
  OrchestrationResult,
  ConfirmationDetails 
} from './types';
import { 
  orchestrateSync, 
  fetchStudents, 
  resetDatabase, 
  fetchDatabasePreview 
} from './services/api';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

const INITIAL_AGENTS: Record<AgentType, AgentState> = {
  input: {
    id: 'input',
    name: 'Input Agent',
    role: 'Natural Language Intent Parser',
    badge: 'groq-llama3-70b',
    model: 'groq-llama3-70b',
    status: 'waiting',
    statusMessage: 'Waiting for natural language input...',
    logs: []
  },
  mother: {
    id: 'mother',
    name: 'Mother Agent',
    role: 'Orchestrator & Dynamic Plan Synthesizer',
    badge: 'groq-llama3-70b',
    model: 'groq-llama3-70b',
    status: 'waiting',
    statusMessage: 'Synthesizing dynamic workflow plan...',
    logs: []
  },
  db: {
    id: 'db',
    name: 'DB Agent',
    role: 'Database Queries, Validation & SQL Execution',
    badge: 'campus-sql-engine',
    model: 'campus-sql-engine',
    status: 'waiting',
    statusMessage: 'Waiting for Mother Agent execution plan...',
    logs: []
  },
  analytics: {
    id: 'analytics',
    name: 'Pulse Analytics Agent',
    role: 'Deterministic Analytics, Rankings & Risk Models',
    badge: 'pulse-engine-v1',
    model: 'pulse-engine-v1',
    status: 'waiting',
    statusMessage: 'Waiting for DB query results...',
    logs: []
  },
  output: {
    id: 'output',
    name: 'Scribe Output Agent',
    role: 'Table Formatting, PDF/PPT Generation & Summaries',
    badge: 'scribe-output-v1',
    model: 'scribe-output-v1',
    status: 'waiting',
    statusMessage: 'Waiting for analytical outputs...',
    logs: []
  }
};

const INITIAL_THREAD: ChatThread = {
  id: 'session-1',
  title: 'Campus Database Session',
  mode: 'explore',
  createdAt: 'Just now',
  updatedAt: 'Just now',
  turns: []
};

export default function App() {
  // Theme State (Persisted in localStorage)
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    return (localStorage.getItem('agentcampus_theme') as 'light' | 'dark') || 'light';
  });

  // 3-Mode State (Persisted in localStorage)
  const [currentMode, setCurrentMode] = useState<AppMode>(() => {
    return (localStorage.getItem('agentcampus_mode') as AppMode) || 'explore';
  });

  // Selected Output Format for Analyze Mode
  const [selectedFormat, setSelectedFormat] = useState<OutputFormat>('text');

  // Threads & Turns State
  const [threads, setThreads] = useState<ChatThread[]>([INITIAL_THREAD]);
  const [selectedThreadId, setSelectedThreadId] = useState<string>(INITIAL_THREAD.id);
  const [selectedTurnId, setSelectedTurnId] = useState<string | undefined>(undefined);

  // Execution State
  const [isExecuting, setIsExecuting] = useState(false);

  // Live Database Records
  const [students, setStudents] = useState<StudentRecord[]>([]);

  // Modals & Drawers
  const [isDataViewerOpen, setIsDataViewerOpen] = useState(false);
  const [isDbPreviewOpen, setIsDbPreviewOpen] = useState(false);
  const [modeInfoModal, setModeInfoModal] = useState<{ isOpen: boolean; targetMode: AppMode }>({
    isOpen: false,
    targetMode: 'explore'
  });
  const [confirmationModal, setConfirmationModal] = useState<{
    isOpen: boolean;
    details?: ConfirmationDetails;
    pendingQuery?: string;
    pendingMode?: AppMode;
    pendingFormat?: OutputFormat;
    turnId?: string;
  }>({
    isOpen: false
  });
  const [jsonModalData, setJsonModalData] = useState<{ isOpen: boolean; title: string; data: any }>({
    isOpen: false,
    title: '',
    data: null
  });

  // Toast Notifications
  const [toast, setToast] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);

  const showToast = (text: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ text, type });
    setTimeout(() => {
      setToast(null);
    }, 4000);
  };

  // Sync theme with DOM and localStorage
  useEffect(() => {
    localStorage.setItem('agentcampus_theme', theme);
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  // Sync mode with localStorage
  useEffect(() => {
    localStorage.setItem('agentcampus_mode', currentMode);
  }, [currentMode]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };

  // Load initial student records from backend
  const loadStudents = async () => {
    try {
      const data = await fetchStudents();
      setStudents(data);
    } catch {
      // Backend may be starting up
    }
  };

  useEffect(() => {
    loadStudents();
  }, []);

  const activeThread = threads.find(t => t.id === selectedThreadId) || threads[0];
  const activeTurn = activeThread?.turns.find(t => t.id === selectedTurnId) || activeThread?.turns[activeThread.turns.length - 1];

  // Handle Mode Change
  const handleSelectMode = (mode: AppMode) => {
    setCurrentMode(mode);
    // Update active thread's mode
    setThreads(prev =>
      prev.map(t => (t.id === selectedThreadId ? { ...t, mode, updatedAt: 'Just now' } : t))
    );
    showToast(`Switched to ${mode.toUpperCase()} mode.`, 'info');
  };

  // Run Real Pipeline
  const handleRunPipeline = async (promptText: string, overrideMode?: AppMode, overrideFormat?: OutputFormat) => {
    if (isExecuting || !promptText.trim()) return;

    const modeToUse = overrideMode || currentMode;
    const formatToUse = overrideFormat || selectedFormat;
    const newTurnId = `turn-${Date.now()}`;
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Build initial turn with all agents waiting
    const initialTurnAgents: Record<AgentType, AgentState> = JSON.parse(JSON.stringify(INITIAL_AGENTS));
    initialTurnAgents.input.status = 'running';
    initialTurnAgents.input.statusMessage = 'Parsing natural language intent...';
    initialTurnAgents.mother.status = 'running';
    initialTurnAgents.mother.statusMessage = 'Synthesizing dynamic workflow plan...';

    const newTurn: Turn = {
      id: newTurnId,
      timestamp,
      prompt: promptText,
      mode: modeToUse,
      outputFormat: formatToUse,
      status: 'running',
      agents: initialTurnAgents,
    };

    setThreads(prev =>
      prev.map(t => {
        if (t.id === selectedThreadId) {
          const updatedTurns = [...t.turns, newTurn];
          return {
            ...t,
            title: t.turns.length === 0 ? promptText.slice(0, 30) + '...' : t.title,
            mode: modeToUse,
            updatedAt: 'Just now',
            turns: updatedTurns,
          };
        }
        return t;
      })
    );
    setSelectedTurnId(newTurnId);
    setIsExecuting(true);

    try {
      // Real backend API call
      const res: OrchestrationResult = await orchestrateSync(promptText, modeToUse, false, formatToUse);

      // Check if backend requires confirmation
      if (res.requiresConfirmation && res.confirmationDetails) {
        // Mark turn as awaiting confirmation
        setThreads(prev =>
          prev.map(t => {
            if (t.id === selectedThreadId) {
              const updatedTurns = t.turns.map(tn => {
                if (tn.id === newTurnId) {
                  const updatedAgents = { ...tn.agents };
                  updatedAgents.input.status = 'complete';
                  updatedAgents.mother.status = 'complete';
                  updatedAgents.db.status = 'waiting';
                  updatedAgents.db.statusMessage = 'Awaiting explicit safety confirmation...';

                  return {
                    ...tn,
                    status: 'waiting' as any,
                    result: res,
                    plan: res.rawPlan,
                    agents: updatedAgents,
                  };
                }
                return tn;
              });
              return { ...t, turns: updatedTurns };
            }
            return t;
          })
        );

        setConfirmationModal({
          isOpen: true,
          details: res.confirmationDetails,
          pendingQuery: promptText,
          pendingMode: modeToUse,
          pendingFormat: formatToUse,
          turnId: newTurnId,
        });

        setIsExecuting(false);
        return;
      }

      if (res.success === false) {
        const isRateLimit = res.errorType === 'RATE_LIMITED' || res.summary?.toLowerCase().includes('rate limit');
        const failedAgents: Record<AgentType, AgentState> = JSON.parse(JSON.stringify(INITIAL_AGENTS));
        failedAgents.input.status = 'complete';
        failedAgents.mother.status = 'failed';
        failedAgents.mother.statusMessage = isRateLimit ? 'AI service rate limit reached.' : 'Workflow execution failed.';

        setThreads(prev =>
          prev.map(t => {
            if (t.id === selectedThreadId) {
              const updatedTurns = t.turns.map(tn => {
                if (tn.id === newTurnId) {
                  return {
                    ...tn,
                    status: 'failed' as any,
                    result: res,
                    plan: res.rawPlan,
                    agents: failedAgents,
                  };
                }
                return tn;
              });
              return { ...t, turns: updatedTurns };
            }
            return t;
          })
        );
        showToast(
          isRateLimit
            ? 'AI service limit reached. Please try again after a few moments.'
            : (res.summary || 'Backend execution failed.'),
          'error'
        );
        return;
      }

      // Populate actual agent completion statuses based on backend execution
      const completedAgents: Record<AgentType, AgentState> = JSON.parse(JSON.stringify(INITIAL_AGENTS));
      completedAgents.input.status = 'complete';
      completedAgents.input.statusMessage = 'Intent & entities parsed successfully.';
      completedAgents.mother.status = 'complete';
      completedAgents.mother.statusMessage = 'Plan synthesized and executed.';
      completedAgents.db.status = 'complete';
      completedAgents.db.statusMessage = modeToUse === 'modify' ? 'Database modified.' : 'Query executed.';

      if (modeToUse === 'analyze') {
        completedAgents.analytics.status = 'complete';
        completedAgents.analytics.statusMessage = 'Deterministic metrics and insights calculated.';
      } else {
        completedAgents.analytics.status = 'waiting';
      }

      completedAgents.output.status = 'complete';
      completedAgents.output.statusMessage = res.outputFile ? `Generated ${res.outputFormat?.toUpperCase()} artifact.` : 'Summary generated.';

      setThreads(prev =>
        prev.map(t => {
          if (t.id === selectedThreadId) {
            const updatedTurns = t.turns.map(tn => {
              if (tn.id === newTurnId) {
                return {
                  ...tn,
                  status: 'complete' as any,
                  result: res,
                  plan: res.rawPlan,
                  agents: completedAgents,
                };
              }
              return tn;
            });
            return { ...t, turns: updatedTurns };
          }
          return t;
        })
      );

      // If modification occurred, immediately refresh live student dataset and DB preview
      if (modeToUse === 'modify') {
        await loadStudents();
        showToast('Database updated successfully. Preview refreshed.', 'success');
      } else {
        showToast('Execution finished successfully.', 'success');
      }
    } catch (err: any) {
      // Mark turn as failed
      setThreads(prev =>
        prev.map(t => {
          if (t.id === selectedThreadId) {
            const updatedTurns = t.turns.map(tn => {
              if (tn.id === newTurnId) {
                const failedAgents = { ...tn.agents };
                failedAgents.input.status = 'failed';
                failedAgents.mother.status = 'failed';
                return {
                  ...tn,
                  status: 'failed' as any,
                  result: {
                    summary: err.message || 'Unable to connect to AgentCampus backend.',
                  },
                  agents: failedAgents,
                };
              }
              return tn;
            });
            return { ...t, turns: updatedTurns };
          }
          return t;
        })
      );
      showToast(err.message || 'Backend execution failed.', 'error');
    } finally {
      setIsExecuting(false);
    }
  };

  // Confirm and Apply Dangerous Mutation
  const handleConfirmDatabaseChange = async () => {
    if (!confirmationModal.pendingQuery) return;
    setIsExecuting(true);

    try {
      const res = await orchestrateSync(
        confirmationModal.pendingQuery,
        'modify',
        true
      );

      setConfirmationModal({ isOpen: false });

      // Update turn
      if (confirmationModal.turnId) {
        const turnId = confirmationModal.turnId;
        const completedAgents: Record<AgentType, AgentState> = JSON.parse(JSON.stringify(INITIAL_AGENTS));
        completedAgents.input.status = 'complete';
        completedAgents.mother.status = 'complete';
        completedAgents.db.status = 'complete';
        completedAgents.db.statusMessage = 'Destructive mutation confirmed and executed.';
        completedAgents.output.status = 'complete';
        completedAgents.output.statusMessage = 'Summary generated.';

        setThreads(prev =>
          prev.map(t => {
            if (t.id === selectedThreadId) {
              const updatedTurns = t.turns.map(tn => {
                if (tn.id === turnId) {
                  return {
                    ...tn,
                    status: 'complete' as any,
                    result: res,
                    plan: res.rawPlan,
                    agents: completedAgents,
                  };
                }
                return tn;
              });
              return { ...t, turns: updatedTurns };
            }
            return t;
          })
        );
      }

      await loadStudents();
      showToast('Database updated successfully. Preview refreshed.', 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to apply confirmed mutation.', 'error');
    } finally {
      setIsExecuting(false);
    }
  };

  // New Chat Session
  const handleNewThread = () => {
    const newId = `session-${Date.now()}`;
    const newT: ChatThread = {
      id: newId,
      title: 'New Session',
      mode: currentMode,
      createdAt: 'Just now',
      updatedAt: 'Just now',
      turns: []
    };
    setThreads(prev => [newT, ...prev]);
    setSelectedThreadId(newId);
    setSelectedTurnId(undefined);
  };

  // Reset Database
  const handleResetDb = async () => {
    if (isExecuting) return;
    try {
      await resetDatabase();
      await loadStudents();
      showToast('Campus database reset to initial seed state.', 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to reset database.', 'error');
    }
  };

  // Export CSV / Excel
  const handleExportCsv = () => {
    const dataToExport = activeTurn?.result?.data || students;
    if (!dataToExport || dataToExport.length === 0) {
      showToast('No records available to export.', 'info');
      return;
    }

    const headers = Object.keys(dataToExport[0]).filter(k => typeof dataToExport[0][k] !== 'object');
    const rows = dataToExport.map(row =>
      headers.map(h => `"${String(row[h] ?? '').replace(/"/g, '""')}"`).join(',')
    );
    const csvContent = [headers.join(','), ...rows].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `agentcampus_export_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast('Excel/CSV export downloaded.', 'success');
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 font-sans select-none transition-colors">
      {/* Toast Notification Banner */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 animate-in fade-in slide-in-from-top-3 duration-200">
          <div className={`flex items-center gap-2.5 px-4 py-3 rounded-2xl shadow-xl border text-xs font-semibold ${
            toast.type === 'success'
              ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-900 dark:text-emerald-200 border-emerald-300 dark:border-emerald-700'
              : toast.type === 'error'
              ? 'bg-rose-50 dark:bg-rose-950 text-rose-900 dark:text-rose-200 border-rose-300 dark:border-rose-700'
              : 'bg-blue-50 dark:bg-blue-950 text-blue-900 dark:text-blue-200 border-blue-300 dark:border-blue-700'
          }`}>
            {toast.type === 'success' && <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />}
            {toast.type === 'error' && <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400" />}
            {toast.type === 'info' && <Info className="w-4 h-4 text-blue-600 dark:text-blue-400" />}
            <span>{toast.text}</span>
            <button onClick={() => setToast(null)} className="ml-2 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Global Header */}
      <Header
        currentMode={currentMode}
        onSelectMode={handleSelectMode}
        onOpenModeInfo={(mode) => setModeInfoModal({ isOpen: true, targetMode: mode })}
        onOpenDatabasePreview={() => setIsDbPreviewOpen(true)}
        onResetDb={handleResetDb}
        isExecuting={isExecuting}
        theme={theme}
        onToggleTheme={toggleTheme}
      />

      {/* Main 3-Column Layout */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* Left Column: Sessions Sidebar */}
        <LeftPanel
          threads={threads}
          selectedThreadId={selectedThreadId}
          onSelectThread={(id) => {
            setSelectedThreadId(id);
            const t = threads.find(th => th.id === id);
            if (t) setCurrentMode(t.mode);
          }}
          onNewThread={handleNewThread}
        />

        {/* Center Column: Execution Timeline & Main Chat */}
        <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
          <CenterPanel
            turns={activeThread?.turns || []}
            selectedTurnId={selectedTurnId}
            onSelectTurn={setSelectedTurnId}
            isExecuting={isExecuting}
            currentMode={currentMode}
            onOpenJsonModal={(title, data) => setJsonModalData({ isOpen: true, title, data })}
            onSelectPreset={(p) => handleRunPipeline(p)}
          />

          {/* Bottom Interactive Bar */}
          <BottomInputBar
            currentMode={currentMode}
            selectedFormat={selectedFormat}
            onSelectFormat={setSelectedFormat}
            onSubmitPrompt={(p) => handleRunPipeline(p)}
            isExecuting={isExecuting}
          />
        </div>

        {/* Right Column: Plan & Results Panel */}
        <RightPanel
          mode={currentMode}
          plan={activeTurn?.plan}
          result={activeTurn?.result}
          activeTurnPrompt={activeTurn?.prompt}
          isExecuting={isExecuting}
          onOpenDataViewer={() => setIsDataViewerOpen(true)}
          onOpenDatabasePreview={() => setIsDbPreviewOpen(true)}
          onOpenSqlViewer={(sql) => setJsonModalData({ isOpen: true, title: 'SQL Execution Trace', data: sql })}
          onOpenPlanJson={() => setJsonModalData({ isOpen: true, title: 'Dynamic Plan Schema', data: activeTurn?.plan })}
          onExportCsv={handleExportCsv}
        />
      </div>

      {/* Modals & Dialogs */}
      <ModeSelectorModal
        isOpen={modeInfoModal.isOpen}
        onClose={() => setModeInfoModal({ isOpen: false, targetMode: currentMode })}
        currentMode={currentMode}
        targetMode={modeInfoModal.targetMode}
        onSelectMode={handleSelectMode}
        onSelectExamplePrompt={(p, m) => handleRunPipeline(p, m)}
      />

      <DatabasePreviewModal
        isOpen={isDbPreviewOpen}
        onClose={() => setIsDbPreviewOpen(false)}
        onRefreshSuccess={() => showToast('Database preview refreshed with live data.', 'info')}
      />

      <ConfirmationModal
        isOpen={confirmationModal.isOpen}
        onClose={() => setConfirmationModal({ isOpen: false })}
        onConfirm={handleConfirmDatabaseChange}
        details={confirmationModal.details}
        isExecuting={isExecuting}
      />

      <DataViewerModal
        isOpen={isDataViewerOpen}
        onClose={() => setIsDataViewerOpen(false)}
        students={activeTurn?.result?.data || students}
        sqlQuery={activeTurn?.result?.queryExecuted}
        onExportCsv={handleExportCsv}
      />

      <JsonViewerModal
        isOpen={jsonModalData.isOpen}
        onClose={() => setJsonModalData({ isOpen: false, title: '', data: null })}
        title={jsonModalData.title}
        data={jsonModalData.data}
      />
    </div>
  );
}
