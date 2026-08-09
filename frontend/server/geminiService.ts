import { GoogleGenAI, Type } from '@google/genai';
import { DynamicPlan, PlanStep } from '../src/types';

const apiKey = process.env.GEMINI_API_KEY;
let ai: GoogleGenAI | null = null;

if (apiKey && apiKey !== 'MY_GEMINI_API_KEY') {
  try {
    ai = new GoogleGenAI({
      apiKey,
      httpOptions: {
        headers: {
          'User-Agent': 'aistudio-build'
        }
      }
    });
  } catch (err) {
    console.warn('[GeminiService] Failed to initialize GoogleGenAI client:', err);
  }
}

export interface InputAgentResult {
  intent: string;
  requestType: 'read' | 'analytics' | 'write' | 'complex';
  targetDepartment?: string;
  limit?: number;
  minCgpa?: number;
  maxCgpa?: number;
  minAttendance?: number;
  maxAttendance?: number;
  searchStudentName?: string;
  updateTargetName?: string;
  newCgpaValue?: number;
  sortField?: string;
  sortOrder?: 'asc' | 'desc';
  operations: string[];
  explanation: string;
}

/**
 * 1. Input Agent: Calls Gemini to convert raw prompt to structured JSON
 */
export async function parseInputWithGemini(userPrompt: string): Promise<InputAgentResult> {
  const promptLower = userPrompt.toLowerCase();

  if (ai) {
    try {
      const response = await ai.models.generateContent({
        model: 'gemini-3.6-flash',
        contents: `Analyze the user's natural language request about a campus student database and convert it into a structured query/action intent JSON specification.

User Request: "${userPrompt}"`,
        config: {
          systemInstruction: `You are the Input Agent in a multi-agent university orchestration platform.
Parse natural language queries into structured JSON parameters for DB and Analytics execution.
Valid departments: 'Computer Science', 'Electronics', 'Mechanical', 'Civil', 'Data Science', 'AI & ML', or 'All'.
Classify requestType as 'read' (query/filter), 'analytics' (averages, statistics, rankings), 'write' (update/insert/delete), or 'complex' (multi-department compare or multi-step analysis).`,
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              intent: { type: Type.STRING, description: 'Short snake_case intent name, e.g. student_performance, update_cgpa, department_analytics' },
              requestType: { type: Type.STRING, description: 'One of: read, analytics, write, complex' },
              targetDepartment: { type: Type.STRING, description: 'Department name if mentioned, or "All"' },
              limit: { type: Type.INTEGER, description: 'Row limit if specified e.g. 10, 50, 100' },
              minCgpa: { type: Type.NUMBER, description: 'Minimum CGPA threshold if mentioned' },
              maxCgpa: { type: Type.NUMBER, description: 'Maximum CGPA threshold if mentioned' },
              minAttendance: { type: Type.NUMBER, description: 'Minimum attendance percentage' },
              maxAttendance: { type: Type.NUMBER, description: 'Maximum attendance percentage' },
              searchStudentName: { type: Type.STRING, description: 'Student name if searching for a specific individual' },
              updateTargetName: { type: Type.STRING, description: 'Student name if performing an UPDATE query' },
              newCgpaValue: { type: Type.NUMBER, description: 'New CGPA value if updating' },
              sortField: { type: Type.STRING, description: 'Field to sort by: cgpa, attendance, name, rollNumber' },
              sortOrder: { type: Type.STRING, description: 'asc or desc' },
              operations: {
                type: Type.ARRAY,
                items: { type: Type.STRING },
                description: 'List of internal operation tags e.g. ["retrieve_students", "calculate_average"]'
              },
              explanation: { type: Type.STRING, description: 'Brief 1-sentence explanation of what was extracted' }
            },
            required: ['intent', 'requestType', 'operations', 'explanation']
          }
        }
      });

      if (response.text) {
        const parsed = JSON.parse(response.text.trim()) as InputAgentResult;
        return parsed;
      }
    } catch (err) {
      console.warn('[GeminiService] Input Agent AI call failed, using rule-based fallback:', err);
    }
  }

  // Fallback rule-based parsing if Gemini API key not present or call fails
  let reqType: InputAgentResult['requestType'] = 'read';
  let intent = 'student_query';
  const ops: string[] = ['retrieve_students'];
  let updateName: string | undefined;
  let newCgpa: number | undefined;
  let dept = 'All';
  let limitVal = 100;
  let minCgpaVal: number | undefined;
  let maxCgpaVal: number | undefined;
  let minAtt: number | undefined;
  let maxAtt: number | undefined;

  // Check for write / update intent
  if (promptLower.includes('update') || promptLower.includes('set') || promptLower.includes('change')) {
    reqType = 'write';
    intent = 'update_student_cgpa';
    ops.push('validate_mutation', 'execute_update', 'recalculate_metrics');
    
    // Extract name and cgpa if possible
    const updateMatch = userPrompt.match(/update\s+([a-zA-Z\s]+)'?s?\s+cgpa\s+to\s+([\d.]+)/i) ||
                        userPrompt.match(/set\s+([a-zA-Z\s]+)'?s?\s+cgpa\s+to\s+([\d.]+)/i);
    if (updateMatch) {
      updateName = updateMatch[1].trim();
      newCgpa = parseFloat(updateMatch[2]);
    } else {
      updateName = 'Rahul';
      newCgpa = 9.5;
    }
  } else if (promptLower.includes('average') || promptLower.includes('avg') || promptLower.includes('stat') || promptLower.includes('analytics')) {
    reqType = 'analytics';
    intent = 'department_analytics';
    ops.push('calculate_aggregates', 'format_summary');
  }

  // Department check
  if (promptLower.includes('computer science') || promptLower.includes('cs')) dept = 'Computer Science';
  else if (promptLower.includes('electronics') || promptLower.includes('ec')) dept = 'Electronics';
  else if (promptLower.includes('mechanical') || promptLower.includes('me')) dept = 'Mechanical';
  else if (promptLower.includes('civil') || promptLower.includes('ce')) dept = 'Civil';
  else if (promptLower.includes('data science') || promptLower.includes('ds')) dept = 'Data Science';
  else if (promptLower.includes('ai') || promptLower.includes('machine learning') || promptLower.includes('ml')) dept = 'AI & ML';

  // Limit check
  const topMatch = promptLower.match(/top\s+(\d+)/);
  if (topMatch) {
    limitVal = parseInt(topMatch[1], 10);
  }

  // Attendance check
  if (promptLower.includes('attendance') && (promptLower.includes('below') || promptLower.includes('less') || promptLower.includes('<'))) {
    const attMatch = promptLower.match(/(\d+)%/);
    if (attMatch) {
      maxAtt = parseInt(attMatch[1], 10);
    } else {
      maxAtt = 75;
    }
  }

  return {
    intent,
    requestType: reqType,
    targetDepartment: dept,
    limit: limitVal,
    minCgpa: minCgpaVal,
    maxCgpa: maxCgpaVal,
    minAttendance: minAtt,
    maxAttendance: maxAtt,
    updateTargetName: updateName,
    newCgpaValue: newCgpa,
    sortField: 'cgpa',
    sortOrder: 'desc',
    operations: ops,
    explanation: `Extracted intent "${intent}" (${reqType}) targeting department: ${dept}.`
  };
}

/**
 * 2. Mother Agent: Generates dynamic execution plan based on structured request
 */
export async function generateMotherPlan(
  userPrompt: string,
  inputResult: InputAgentResult
): Promise<DynamicPlan> {
  const taskId = `TASK-${Date.now().toString(36).toUpperCase()}`;

  if (ai) {
    try {
      const response = await ai.models.generateContent({
        model: 'gemini-3.6-flash',
        contents: `You are the Mother Agent (Orchestrator).
Create a dynamic, tailored step-by-step agent execution plan based on this user query and structured request.

User Request: "${userPrompt}"
Structured Request: ${JSON.stringify(inputResult)}`,
        config: {
          systemInstruction: `You are the Mother Agent in AgentCampus.
Generate a dynamic step-by-step execution plan.
RULES FOR PLAN GENERATION:
1. Every plan MUST start with step 1: Input Agent ("parse_intent").
2. The remaining steps MUST be assigned to specialized agents ('db', 'analytics', 'output', etc.) depending on request type:
   - For simple 'read' (filter/top list): [input -> db (get_students) -> output (format_results)]
   - For 'analytics' (metrics/averages): [input -> db (get_students) -> analytics (calculate_metrics) -> output (format_report)]
   - For 'write' (updates/inserts): [input -> db (validate_request) -> db (execute_update) -> db (verify_changes) -> analytics (recalculate_metrics) -> output (confirm_status)]
   - For 'complex': [input -> db (query_multi) -> analytics (cross_compare) -> output (build_visualization)]
Do NOT output generic plans. Tailor descriptions specifically to the user request.`,
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              title: { type: Type.STRING, description: 'Descriptive title for this orchestration task' },
              steps: {
                type: Type.ARRAY,
                items: {
                  type: Type.OBJECT,
                  properties: {
                    agent: { type: Type.STRING, description: 'One of: input, db, analytics, output' },
                    action: { type: Type.STRING, description: 'Action code e.g. parse_intent, get_students, calculate_average, format_table' },
                    description: { type: Type.STRING, description: 'Detailed action description specific to this step' }
                  },
                  required: ['agent', 'action', 'description']
                }
              }
            },
            required: ['title', 'steps']
          }
        }
      });

      if (response.text) {
        const raw = JSON.parse(response.text.trim());
        const steps: PlanStep[] = raw.steps.map((s: any, idx: number) => ({
          id: `step-${idx + 1}`,
          stepNumber: idx + 1,
          agent: s.agent as any,
          action: s.action,
          description: s.description,
          status: 'waiting'
        }));

        return {
          taskId,
          title: raw.title || `Task Execution: ${inputResult.intent}`,
          intent: inputResult.intent,
          requestType: inputResult.requestType,
          steps
        };
      }
    } catch (err) {
      console.warn('[GeminiService] Mother Agent plan generation failed, using rule generator:', err);
    }
  }

  // Fallback Rule-Based Dynamic Plan Generator
  const steps: PlanStep[] = [
    {
      id: 'step-1',
      stepNumber: 1,
      agent: 'input',
      action: 'parse_intent',
      description: 'Convert natural language query into structured JSON specification',
      status: 'waiting'
    }
  ];

  if (inputResult.requestType === 'write') {
    steps.push(
      {
        id: 'step-2',
        stepNumber: 2,
        agent: 'db',
        action: 'validate_request',
        description: `Validate mutation target (${inputResult.updateTargetName || 'student'}) and bounds (CGPA <= 10.0)`,
        status: 'waiting'
      },
      {
        id: 'step-3',
        stepNumber: 3,
        agent: 'db',
        action: 'generate_sql_update',
        description: `Generate & execute SQL UPDATE for target student record`,
        status: 'waiting'
      },
      {
        id: 'step-4',
        stepNumber: 4,
        agent: 'analytics',
        action: 'recalculate_metrics',
        description: `Recalculate department averages and rank positions post-update`,
        status: 'waiting'
      },
      {
        id: 'step-5',
        stepNumber: 5,
        agent: 'output',
        action: 'format_confirmation',
        description: `Build audit log, confirmation summary, and updated record table`,
        status: 'waiting'
      }
    );
  } else if (inputResult.requestType === 'analytics') {
    steps.push(
      {
        id: 'step-2',
        stepNumber: 2,
        agent: 'db',
        action: 'get_students',
        description: `Query dataset for ${inputResult.targetDepartment || 'All'} department students`,
        status: 'waiting'
      },
      {
        id: 'step-3',
        stepNumber: 3,
        agent: 'analytics',
        action: 'calculate_aggregates',
        description: 'Compute department averages, CGPA standard distribution & attendance correlations',
        status: 'waiting'
      },
      {
        id: 'step-4',
        stepNumber: 4,
        agent: 'output',
        action: 'format_analytics_report',
        description: 'Render executive summary stats, metric cards, and CSV export file',
        status: 'waiting'
      }
    );
  } else {
    // Standard Read query
    steps.push(
      {
        id: 'step-2',
        stepNumber: 2,
        agent: 'db',
        action: 'get_students',
        description: `Execute SELECT query for ${inputResult.targetDepartment || 'All'} students (Limit ${inputResult.limit || 100})`,
        status: 'waiting'
      },
      {
        id: 'step-3',
        stepNumber: 3,
        agent: 'analytics',
        action: 'calculate_basic_stats',
        description: 'Summarize count, top score, and overall department average',
        status: 'waiting'
      },
      {
        id: 'step-4',
        stepNumber: 4,
        agent: 'output',
        action: 'format_table',
        description: 'Format student data table with view controls and CSV download',
        status: 'waiting'
      }
    );
  }

  let title = `Student Query: ${inputResult.targetDepartment || 'Campus'} Analysis`;
  if (inputResult.requestType === 'write') title = `Database Update: ${inputResult.updateTargetName || 'Student'} CGPA`;
  if (inputResult.requestType === 'analytics') title = `Analytics & Performance Breakdown`;

  return {
    taskId,
    title,
    intent: inputResult.intent,
    requestType: inputResult.requestType,
    steps
  };
}
