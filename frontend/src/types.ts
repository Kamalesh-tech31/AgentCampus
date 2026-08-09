export type AgentStatus = 'waiting' | 'running' | 'complete' | 'failed';

export type AgentType = 'input' | 'mother' | 'db' | 'analytics' | 'output';

export interface AgentInfo {
  id: AgentType;
  name: string;
  role: string;
  badge: string;
  model: string;
  color: string;
}

export interface ActivityLog {
  id: string;
  timestamp: string;
  agentId: AgentType;
  level: 'info' | 'working' | 'success' | 'warn' | 'error';
  message: string;
  details?: any;
}

export interface AgentState {
  id: AgentType;
  name: string;
  role: string;
  badge: string;
  model: string;
  status: AgentStatus;
  statusMessage: string;
  startTime?: number;
  endTime?: number;
  durationMs?: number;
  logs: ActivityLog[];
  inputData?: any;
  outputData?: any;
}

export interface PlanStep {
  id: string;
  stepNumber: number;
  agent: AgentType;
  action: string;
  description: string;
  status: AgentStatus;
  liveMessage?: string;
  details?: string;
}

export interface DynamicPlan {
  taskId: string;
  title: string;
  intent: string;
  requestType: 'read' | 'analytics' | 'write' | 'complex';
  steps: PlanStep[];
}

export interface StudentRecord {
  id: string;
  rollNumber: string;
  name: string;
  department: 'Computer Science' | 'Electronics' | 'Mechanical' | 'Civil' | 'Data Science' | 'AI & ML';
  cgpa: number;
  semester: number;
  attendance: number; // percentage 0-100
  email: string;
  status: 'Active' | 'Probation' | 'Graduated';
  backlogs: number;
  projectTitle?: string;
}

export interface OrchestrationResult {
  summary: string;
  queryExecuted?: string;
  mutationExecuted?: string;
  affectedCount?: number;
  data?: StudentRecord[];
  metrics?: {
    totalRecords?: number;
    averageCgpa?: number;
    highestCgpa?: number;
    lowestCgpa?: number;
    avgAttendance?: number;
    probationCount?: number;
    departmentBreakdown?: Record<string, { count: number; avgCgpa: number }>;
  };
  csvData?: string;
  rawPlan?: DynamicPlan;
  structuredIntent?: any;
}

export interface OrchestrationEvent {
  type: 
    | 'TASK_CREATED'
    | 'AGENT_STARTED'
    | 'AGENT_WORKING'
    | 'AGENT_COMPLETED'
    | 'AGENT_FAILED'
    | 'PLAN_UPDATED'
    | 'RESULT_READY';
  taskId: string;
  timestamp: number;
  agentId?: AgentType;
  message?: string;
  plan?: DynamicPlan;
  agentState?: Partial<AgentState>;
  log?: ActivityLog;
  result?: OrchestrationResult;
  structuredIntent?: any;
}

export interface Turn {
  id: string;
  timestamp: string;
  prompt: string;
  status: AgentStatus;
  agents: Record<AgentType, AgentState>;
  plan?: DynamicPlan;
  result?: OrchestrationResult;
  structuredIntent?: any;
  durationMs?: number;
}

export interface ChatThread {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  turns: Turn[];
}

export interface HistoryItem {
  id: string;
  timestamp: string;
  prompt: string;
  planTitle: string;
  status: AgentStatus;
  resultSummary?: string;
  structuredIntent?: any;
}
