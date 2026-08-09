import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { LeftPanel } from './components/LeftPanel';
import { CenterPanel } from './components/CenterPanel';
import { RightPanel } from './components/RightPanel';
import { BottomInputBar } from './components/BottomInputBar';
import { DataViewerModal } from './components/DataViewerModal';
import { JsonViewerModal } from './components/JsonViewerModal';
import { INITIAL_DEMO_THREAD } from './data/initialDemoData';
import { 
  AgentState, 
  AgentType, 
  ChatThread, 
  Turn, 
  StudentRecord, 
  OrchestrationEvent 
} from './types';

const INITIAL_AGENTS: Record<AgentType, AgentState> = {
  input: {
    id: 'input',
    name: 'Input Agent',
    role: 'Natural Language Intent Parser',
    badge: 'gemini-3.6-flash',
    model: 'gemini-3.6-flash',
    status: 'waiting',
    statusMessage: 'Waiting for natural language input...',
    logs: []
  },
  mother: {
    id: 'mother',
    name: 'Mother Agent',
    role: 'Orchestrator & Dynamic Plan Synthesizer',
    badge: 'gemini-3.6-flash',
    model: 'gemini-3.6-flash',
    status: 'waiting',
    statusMessage: 'Waiting for structured intent from Input Agent...',
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
    name: 'Analytics Agent',
    role: 'Aggregations, Percentiles & Statistical Metrics',
    badge: 'data-analytics-v1',
    model: 'data-analytics-v1',
    status: 'waiting',
    statusMessage: 'Waiting for DB query results...',
    logs: []
  },
  output: {
    id: 'output',
    name: 'Output Agent',
    role: 'Table Formatting, Summary & CSV Generation',
    badge: 'output-formatter-v1',
    model: 'output-formatter-v1',
    status: 'waiting',
    statusMessage: 'Waiting for metric outputs...',
    logs: []
  }
};

export default function App() {
  // Multi-Turn Threads State
  const [threads, setThreads] = useState<ChatThread[]>([INITIAL_DEMO_THREAD]);
  const [selectedThreadId, setSelectedThreadId] = useState<string>(INITIAL_DEMO_THREAD.id);
  const [selectedTurnId, setSelectedTurnId] = useState<string | undefined>(INITIAL_DEMO_THREAD.turns[0].id);
  
  const [isExecuting, setIsExecuting] = useState(false);
  
  // Database State
  const [students, setStudents] = useState<StudentRecord[]>([]);

  // Modals State
  const [isDataViewerOpen, setIsDataViewerOpen] = useState(false);
  const [jsonModalData, setJsonModalData] = useState<{ isOpen: boolean; title: string; data: any }>({
    isOpen: false,
    title: '',
    data: null
  });

  // Derived active thread and turn
  const activeThread = threads.find(t => t.id === selectedThreadId) || threads[0];
  const activeTurn = activeThread?.turns.find(t => t.id === selectedTurnId) || activeThread?.turns[activeThread.turns.length - 1];

  // Fetch campus student dataset on initial mount
  const fetchStudents = async () => {
    try {
      const res = await fetch('/api/students');
      if (res.ok) {
        const data = await res.json();
        setStudents(data.students || []);
      }
    } catch (err) {
      console.error('Failed to fetch students:', err);
    }
  };

  useEffect(() => {
    fetchStudents();
  }, []);

  // Reset DB
  const handleResetDb = async () => {
    try {
      const res = await fetch('/api/students/reset', { method: 'POST' });
      if (res.ok) {
        await fetchStudents();
      }
    } catch (err) {
      console.error('Failed to reset DB:', err);
    }
  };

  // Main SSE Orchestration Stream Handler
  const handleRunPipeline = async (prompt: string) => {
    if (!prompt.trim() || isExecuting) return;

    setIsExecuting(true);

    const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const newTurnId = `turn-${Date.now()}`;

    const newTurn: Turn = {
      id: newTurnId,
      timestamp: nowStr,
      prompt,
      status: 'running',
      agents: JSON.parse(JSON.stringify(INITIAL_AGENTS))
    };

    let targetThreadId = selectedThreadId;

    setThreads(prevThreads => {
      let threadExists = prevThreads.some(t => t.id === targetThreadId);
      
      if (!threadExists || !targetThreadId) {
        const newThreadId = `chat-${Date.now()}`;
        targetThreadId = newThreadId;
        setSelectedThreadId(newThreadId);
        
        const newThread: ChatThread = {
          id: newThreadId,
          title: prompt.length > 32 ? prompt.slice(0, 32) + '...' : prompt,
          createdAt: nowStr,
          updatedAt: nowStr,
          turns: [newTurn]
        };
        return [newThread, ...prevThreads];
      }

      return prevThreads.map(thread => {
        if (thread.id === targetThreadId) {
          const isFirstTurn = thread.turns.length === 0;
          return {
            ...thread,
            title: isFirstTurn || thread.title === 'New Conversation' 
              ? (prompt.length > 32 ? prompt.slice(0, 32) + '...' : prompt)
              : thread.title,
            updatedAt: nowStr,
            turns: [...thread.turns, newTurn]
          };
        }
        return thread;
      });
    });

    setSelectedTurnId(newTurnId);

    try {
      const response = await fetch('/api/orchestrate/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });

      if (!response.ok || !response.body) {
        throw new Error('Failed to connect to orchestration stream');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            const jsonStr = trimmed.substring(6);
            try {
              const event: OrchestrationEvent = JSON.parse(jsonStr);
              processOrchestrationEvent(event, targetThreadId!, newTurnId);
            } catch (err) {
              console.warn('Failed to parse SSE event JSON:', err, jsonStr);
            }
          }
        }
      }
    } catch (err: any) {
      console.error('Orchestration stream error:', err);
      updateTurnState(targetThreadId!, newTurnId, (turn) => ({
        ...turn,
        status: 'failed'
      }));
    } finally {
      setIsExecuting(false);
      await fetchStudents();
    }
  };

  // Helper to update specific turn inside state
  const updateTurnState = (
    threadId: string, 
    turnId: string, 
    updater: (turn: Turn) => Turn
  ) => {
    setThreads(prev => prev.map(t => {
      if (t.id === threadId) {
        return {
          ...t,
          turns: t.turns.map(tn => tn.id === turnId ? updater(tn) : tn)
        };
      }
      return t;
    }));
  };

  // Process Event Dispatcher
  const processOrchestrationEvent = (
    event: OrchestrationEvent, 
    threadId: string, 
    turnId: string
  ) => {
    const timestampStr = new Date().toLocaleTimeString();

    switch (event.type) {
      case 'AGENT_STARTED':
        if (event.agentId) {
          const agId = event.agentId;
          updateTurnState(threadId, turnId, (turn) => {
            const nextAgents = { ...turn.agents };
            nextAgents[agId] = {
              ...nextAgents[agId],
              status: 'running',
              statusMessage: event.message || `Executing ${agId} agent...`,
              startTime: event.timestamp,
              logs: [
                ...nextAgents[agId].logs,
                { id: `log-${Date.now()}-${Math.random()}`, timestamp: timestampStr, agentId: agId, level: 'info', message: event.message || 'Started' }
              ]
            };
            return { ...turn, agents: nextAgents };
          });
        }
        break;

      case 'AGENT_WORKING':
        if (event.agentId) {
          const agId = event.agentId;
          updateTurnState(threadId, turnId, (turn) => {
            const nextAgents = { ...turn.agents };
            const currentLogs = nextAgents[agId].logs;
            const newLog = event.log || {
              id: `log-${Date.now()}-${Math.random()}`,
              timestamp: timestampStr,
              agentId: agId,
              level: 'working',
              message: event.message || 'Working...'
            };

            nextAgents[agId] = {
              ...nextAgents[agId],
              statusMessage: event.message || nextAgents[agId].statusMessage,
              logs: [...currentLogs, newLog]
            };
            return { ...turn, agents: nextAgents };
          });
        }
        break;

      case 'PLAN_UPDATED':
        if (event.plan) {
          updateTurnState(threadId, turnId, (turn) => ({
            ...turn,
            plan: event.plan
          }));
        }
        break;

      case 'AGENT_COMPLETED':
        if (event.agentId) {
          const agId = event.agentId;
          updateTurnState(threadId, turnId, (turn) => {
            const nextAgents = { ...turn.agents };
            const startTime = nextAgents[agId].startTime || event.timestamp;
            const durationMs = event.timestamp - startTime;

            let updatedPlan = turn.plan;
            if (updatedPlan) {
              const updatedSteps = updatedPlan.steps.map(s => {
                if (s.agent === agId) {
                  return { ...s, status: 'complete' as const, liveMessage: event.message };
                }
                return s;
              });
              updatedPlan = { ...updatedPlan, steps: updatedSteps };
            }

            nextAgents[agId] = {
              ...nextAgents[agId],
              status: 'complete',
              statusMessage: event.message || 'Completed',
              endTime: event.timestamp,
              durationMs,
              outputData: event.agentState?.outputData || nextAgents[agId].outputData,
              logs: [
                ...nextAgents[agId].logs,
                { id: `log-${Date.now()}-${Math.random()}`, timestamp: timestampStr, agentId: agId, level: 'success', message: event.message || 'Completed step successfully.' }
              ]
            };

            // Calculate total turn duration if output agent finishes
            const totalDuration = Object.values(nextAgents).reduce((acc, a) => acc + (a.durationMs || 0), 0);

            return {
              ...turn,
              agents: nextAgents,
              plan: updatedPlan,
              durationMs: totalDuration > 0 ? totalDuration : turn.durationMs
            };
          });
        }
        break;

      case 'RESULT_READY':
        if (event.result) {
          updateTurnState(threadId, turnId, (turn) => ({
            ...turn,
            status: 'complete',
            result: event.result
          }));
          if (event.result.data) {
            setStudents(event.result.data);
          }
        }
        break;

      case 'AGENT_FAILED':
        if (event.agentId) {
          const agId = event.agentId;
          updateTurnState(threadId, turnId, (turn) => {
            const nextAgents = { ...turn.agents };
            nextAgents[agId] = {
              ...nextAgents[agId],
              status: 'failed',
              statusMessage: event.message || 'Failed',
              logs: [
                ...nextAgents[agId].logs,
                { id: `log-${Date.now()}-${Math.random()}`, timestamp: timestampStr, agentId: agId, level: 'error', message: event.message || 'Agent failed.' }
              ]
            };
            return {
              ...turn,
              status: 'failed',
              agents: nextAgents
            };
          });
        }
        break;
    }
  };

  // Export CSV
  const handleExportCsv = () => {
    const csvContent = activeTurn?.result?.csvData || 'ID,RollNumber,Name,Department,CGPA\n';
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `agent_campus_export_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Select item/thread from sidebar
  const handleSelectThread = (id: string) => {
    setSelectedThreadId(id);
    const thread = threads.find(t => t.id === id);
    if (thread && thread.turns.length > 0) {
      setSelectedTurnId(thread.turns[thread.turns.length - 1].id);
    } else {
      setSelectedTurnId(undefined);
    }
  };

  // Start a new conversation thread (+ New Request)
  const handleNewThread = () => {
    if (isExecuting) return;
    const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const newThreadId = `chat-${Date.now()}`;
    const newThread: ChatThread = {
      id: newThreadId,
      title: 'New Conversation',
      createdAt: nowStr,
      updatedAt: nowStr,
      turns: []
    };
    setThreads(prev => [newThread, ...prev]);
    setSelectedThreadId(newThreadId);
    setSelectedTurnId(undefined);
  };

  // Select specific turn in center panel
  const handleSelectTurn = (turnId: string) => {
    setSelectedTurnId(turnId);
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-white text-gray-900 font-sans antialiased overflow-hidden select-none">
      {/* Header */}
      <Header
        studentCount={students.length}
        activeAgentsCount={5}
        onResetDb={handleResetDb}
        onOpenDataViewer={() => setIsDataViewerOpen(true)}
        isExecuting={isExecuting}
      />

      {/* Main 3-Panel Split Area */}
      <div className="flex-1 flex min-h-0 divide-x divide-gray-200 overflow-hidden">
        {/* LEFT PANEL */}
        <LeftPanel
          threads={threads}
          selectedThreadId={selectedThreadId}
          onSelectThread={handleSelectThread}
          onNewThread={handleNewThread}
        />

        {/* CENTER PANEL */}
        <CenterPanel
          turns={activeThread?.turns || []}
          selectedTurnId={selectedTurnId}
          onSelectTurn={handleSelectTurn}
          isExecuting={isExecuting}
          onOpenJsonModal={(title, data) => setJsonModalData({ isOpen: true, title, data })}
          onSelectPreset={(p) => handleRunPipeline(p)}
        />

        {/* RIGHT PANEL */}
        <RightPanel
          plan={activeTurn?.plan}
          result={activeTurn?.result}
          activeTurnPrompt={activeTurn?.prompt}
          isExecuting={isExecuting}
          onOpenDataViewer={() => setIsDataViewerOpen(true)}
          onOpenSqlViewer={(sql) => setJsonModalData({ isOpen: true, title: 'Executed SQL Statement', data: { sql } })}
          onOpenPlanJson={() => setJsonModalData({ isOpen: true, title: 'Raw Mother Agent Plan JSON', data: activeTurn?.plan })}
          onExportCsv={handleExportCsv}
        />
      </div>

      {/* BOTTOM INPUT BAR */}
      <BottomInputBar
        onSubmitPrompt={handleRunPipeline}
        isExecuting={isExecuting}
      />

      {/* MODALS */}
      <DataViewerModal
        isOpen={isDataViewerOpen}
        onClose={() => setIsDataViewerOpen(false)}
        students={students}
        sqlQuery={activeTurn?.result?.queryExecuted}
        onExportCsv={handleExportCsv}
      />

      <JsonViewerModal
        isOpen={jsonModalData.isOpen}
        onClose={() => setJsonModalData({ isOpen: false, title: '', data: null })}
        title={jsonModalData.title}
        jsonData={jsonModalData.data}
      />
    </div>
  );
}
