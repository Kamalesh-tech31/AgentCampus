import { ChatThread, AgentState } from '../types';

const COMPLETED_INPUT_AGENT: AgentState = {
  id: 'input',
  name: 'Input Agent',
  role: 'Natural Language Intent Parser',
  badge: 'groq-llama3-70b',
  model: 'groq-llama3-70b',
  status: 'complete',
  statusMessage: 'Parsed query intent into structured parameters',
  durationMs: 420,
  logs: [
    { id: 'log-1', timestamp: '10:00:01 AM', agentId: 'input', level: 'info', message: 'Received user prompt' },
    { id: 'log-2', timestamp: '10:00:01 AM', agentId: 'input', level: 'success', message: 'Identified target department: Computer Science' },
    { id: 'log-3', timestamp: '10:00:02 AM', agentId: 'input', level: 'success', message: 'Extracted sorting key: CGPA (DESC), limit: 10' }
  ],
  outputData: {
    department: 'Computer Science',
    limit: 10,
    orderBy: 'cgpa DESC',
    filters: { attendanceMin: 75 }
  }
};

const COMPLETED_MOTHER_AGENT: AgentState = {
  id: 'mother',
  name: 'Mother Agent',
  role: 'Orchestrator & Dynamic Plan Synthesizer',
  badge: 'groq-llama3-70b',
  model: 'groq-llama3-70b',
  status: 'complete',
  statusMessage: 'Synthesized 5-step execution plan',
  durationMs: 650,
  logs: [
    { id: 'log-4', timestamp: '10:00:02 AM', agentId: 'mother', level: 'info', message: 'Synthesizing step dependency graph' },
    { id: 'log-5', timestamp: '10:00:03 AM', agentId: 'mother', level: 'success', message: 'Assigned execution tasks to DB, Analytics, and Output agents' }
  ],
  outputData: {
    planId: 'plan-cs-top10',
    stepsCount: 5,
    estimatedRuntimeMs: 2500
  }
};

const COMPLETED_DB_AGENT: AgentState = {
  id: 'db',
  name: 'DB Agent',
  role: 'Database Queries, Validation & SQL Execution',
  badge: 'campus-sql-engine',
  model: 'campus-sql-engine',
  status: 'complete',
  statusMessage: 'Executed SQL query on campus database',
  durationMs: 820,
  logs: [
    { id: 'log-6', timestamp: '10:00:03 AM', agentId: 'db', level: 'info', message: 'Generated SQL statement' },
    { id: 'log-7', timestamp: '10:00:04 AM', agentId: 'db', level: 'success', message: 'Query executed successfully. 10 records retrieved.' }
  ],
  outputData: {
    sql: "SELECT * FROM students WHERE department = 'Computer Science' AND attendance >= 75 ORDER BY cgpa DESC LIMIT 10;"
  }
};

const COMPLETED_ANALYTICS_AGENT: AgentState = {
  id: 'analytics',
  name: 'Analytics Agent',
  role: 'Aggregations, Percentiles & Statistical Metrics',
  badge: 'data-analytics-v1',
  model: 'data-analytics-v1',
  status: 'complete',
  statusMessage: 'Calculated department averages and metrics',
  durationMs: 510,
  logs: [
    { id: 'log-8', timestamp: '10:00:04 AM', agentId: 'analytics', level: 'info', message: 'Computing CGPA distribution' },
    { id: 'log-9', timestamp: '10:00:05 AM', agentId: 'analytics', level: 'success', message: 'Average CGPA: 9.38, Max CGPA: 9.90, Avg Attendance: 92.4%' }
  ],
  outputData: {
    averageCgpa: 9.38,
    maxCgpa: 9.9,
    avgAttendance: 92.4
  }
};

const COMPLETED_OUTPUT_AGENT: AgentState = {
  id: 'output',
  name: 'Output Agent',
  role: 'Table Formatting, Summary & CSV Generation',
  badge: 'output-formatter-v1',
  model: 'output-formatter-v1',
  status: 'complete',
  statusMessage: 'Formatted table response and CSV dataset',
  durationMs: 480,
  logs: [
    { id: 'log-10', timestamp: '10:00:05 AM', agentId: 'output', level: 'info', message: 'Generating summary text and CSV buffer' },
    { id: 'log-11', timestamp: '10:00:05 AM', agentId: 'output', level: 'success', message: 'Formatted 10 records for display' }
  ],
  outputData: {
    summary: 'Retrieved top 10 Computer Science students ordered by CGPA with high attendance.',
    recordCount: 10
  }
};

export const INITIAL_DEMO_THREAD: ChatThread = {
  id: 'chat-demo-1',
  title: 'Top 10 CS Students Query',
  mode: 'explore',
  createdAt: '10:00 AM',
  updatedAt: '10:00 AM',
  turns: [
    {
      id: 'turn-demo-1',
      timestamp: '10:00 AM',
      prompt: 'Show top 10 Computer Science students ordered by CGPA with high attendance',
      mode: 'explore',
      status: 'complete',
      durationMs: 2880,
      agents: {
        input: COMPLETED_INPUT_AGENT,
        mother: COMPLETED_MOTHER_AGENT,
        db: COMPLETED_DB_AGENT,
        analytics: COMPLETED_ANALYTICS_AGENT,
        output: COMPLETED_OUTPUT_AGENT
      },
      plan: {
        taskId: 'task-cs-top10',
        title: 'Top 10 CS Students Query',
        intent: 'Fetch top 10 Computer Science students ordered by CGPA',
        requestType: 'read',
        steps: [
          { id: 's1', stepNumber: 1, agent: 'input', action: 'Intent Parsing', description: 'Extract parameters', status: 'complete' },
          { id: 's2', stepNumber: 2, agent: 'mother', action: 'Plan Synthesis', description: 'Synthesize pipeline steps', status: 'complete' },
          { id: 's3', stepNumber: 3, agent: 'db', action: 'Execute Query', description: 'Run SELECT query on students table', status: 'complete' },
          { id: 's4', stepNumber: 4, agent: 'analytics', action: 'Compute Metrics', description: 'Compute CGPA & attendance metrics', status: 'complete' },
          { id: 's5', stepNumber: 5, agent: 'output', action: 'Format Output', description: 'Generate summary table and CSV payload', status: 'complete' }
        ]
      },
      result: {
        summary: 'Found 10 Computer Science students matching high attendance criteria. Highest CGPA is 9.90 (Aarav Patel) with average department CGPA of 9.38.',
        queryExecuted: "SELECT * FROM students WHERE department = 'Computer Science' AND attendance >= 75 ORDER BY cgpa DESC LIMIT 10;",
        metrics: {
          totalRecords: 10,
          averageCgpa: 9.38,
          highestCgpa: 9.90,
          avgAttendance: 92.4
        }
      }
    }
  ]
};
