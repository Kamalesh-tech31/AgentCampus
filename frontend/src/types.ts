export type AppMode = 'modify' | 'explore' | 'analyze';

export type OutputFormat = 'text' | 'excel' | 'pdf' | 'ppt';

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
  department: string;
  cgpa: number;
  semester: number;
  attendance: number;
  email: string;
  status: string;
  backlogs: number;
  projectTitle?: string;
  [key: string]: any;
}

export interface TableColumnInfo {
  name: string;
  type: string;
}

export interface DatabaseTablePreview {
  name: string;
  columns: TableColumnInfo[];
  sampleRecords: Record<string, any>[];
  rowCount: number;
}

export interface DatabasePreviewResponse {
  tables: DatabaseTablePreview[];
}

export interface ConfirmationDetails {
  operation?: string;
  target_table?: string;
  condition?: string;
  affected_records?: number;
  message?: string;
  warning?: string;
  sql?: string;
  plan?: any;
  [key: string]: any;
}

export interface ExecutionAgentSummary {
  agent: string;
  status: string;
  durationMs?: number;
  error?: string;
}

export interface ExecutionSummary {
  agents: ExecutionAgentSummary[];
  totalDurationMs?: number;
  requiresConfirmation?: boolean;
}

export interface OrchestrationResult {
  mode?: AppMode;
  summary: string;
  queryExecuted?: string;
  mutationExecuted?: string;
  affectedCount?: number;
  data?: any[];
  metrics?: {
    totalRecords?: number;
    averageCgpa?: number;
    highestCgpa?: number;
    lowestCgpa?: number;
    avgAttendance?: number;
    probationCount?: number;
    departmentBreakdown?: Record<string, { count: number; avgCgpa: number }>;
    [key: string]: any;
  };
  outputFormat?: OutputFormat | string;
  outputFile?: string;
  requiresConfirmation?: boolean;
  confirmationDetails?: ConfirmationDetails;
  execution?: ExecutionSummary;
  rawPlan?: DynamicPlan;
  structuredIntent?: any;
  csvData?: string;
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
  mode: AppMode;
  outputFormat?: OutputFormat;
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
  mode: AppMode;
  createdAt: string;
  updatedAt: string;
  turns: Turn[];
}

export interface ColumnValidationResult {
  table: string;
  column: string;
  valid: boolean;
  resolvedColumn?: string;
  suggestion?: string;
}
