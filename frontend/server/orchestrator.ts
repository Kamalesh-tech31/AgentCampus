import { Response } from 'express';
import { dbInstance } from '../src/data/mockCampusDb';
import { parseInputWithGemini, generateMotherPlan, InputAgentResult } from './geminiService';
import { OrchestrationEvent, DynamicPlan, OrchestrationResult, StudentRecord } from '../src/types';

export async function runOrchestrationPipeline(
  userPrompt: string,
  res: Response
) {
  const taskId = `TASK-${Date.now().toString(36).toUpperCase()}`;
  const now = Date.now();

  // Helper to send SSE event
  const sendEvent = (event: OrchestrationEvent) => {
    res.write(`data: ${JSON.stringify(event)}\n\n`);
    if ((res as any).flush) {
      (res as any).flush();
    }
  };

  const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

  try {
    // 1. Event: TASK_CREATED
    sendEvent({
      type: 'TASK_CREATED',
      taskId,
      timestamp: now,
      message: `Orchestration task initialized for query: "${userPrompt}"`
    });

    await delay(300);

    // ==========================================
    // STEP 1: INPUT AGENT EXECUTION
    // ==========================================
    sendEvent({
      type: 'AGENT_STARTED',
      taskId,
      timestamp: Date.now(),
      agentId: 'input',
      message: 'Input Agent active: Parsing natural language user prompt into structured JSON'
    });

    await delay(400);

    sendEvent({
      type: 'AGENT_WORKING',
      taskId,
      timestamp: Date.now(),
      agentId: 'input',
      message: 'Calling Gemini AI model to extract intent, filters, entities, and operations...'
    });

    const structuredInput: InputAgentResult = await parseInputWithGemini(userPrompt);

    await delay(300);

    sendEvent({
      type: 'AGENT_WORKING',
      taskId,
      timestamp: Date.now(),
      agentId: 'input',
      message: `Structured intent generated: "${structuredInput.intent}" (${structuredInput.requestType.toUpperCase()})`,
      structuredIntent: structuredInput
    });

    sendEvent({
      type: 'AGENT_COMPLETED',
      taskId,
      timestamp: Date.now(),
      agentId: 'input',
      message: `Input Agent completed. Operations identified: ${structuredInput.operations.join(', ')}`,
      agentState: {
        status: 'complete',
        outputData: structuredInput
      }
    });

    await delay(400);

    // ==========================================
    // STEP 2: MOTHER AGENT EXECUTION
    // ==========================================
    sendEvent({
      type: 'AGENT_STARTED',
      taskId,
      timestamp: Date.now(),
      agentId: 'mother',
      message: 'Mother Agent active: Orchestrating dynamic multi-agent execution plan'
    });

    await delay(400);

    sendEvent({
      type: 'AGENT_WORKING',
      taskId,
      timestamp: Date.now(),
      agentId: 'mother',
      message: 'Synthesizing step-by-step dependency graph for specialized agents...'
    });

    const dynamicPlan: DynamicPlan = await generateMotherPlan(userPrompt, structuredInput);

    // Emit PLAN_UPDATED
    sendEvent({
      type: 'PLAN_UPDATED',
      taskId,
      timestamp: Date.now(),
      plan: dynamicPlan,
      message: `Dynamic plan synthesized with ${dynamicPlan.steps.length} execution steps`
    });

    await delay(300);

    sendEvent({
      type: 'AGENT_COMPLETED',
      taskId,
      timestamp: Date.now(),
      agentId: 'mother',
      message: `Mother Agent completed: Plan "${dynamicPlan.title}" ready for execution`,
      agentState: {
        status: 'complete',
        outputData: dynamicPlan
      }
    });

    await delay(400);

    // ==========================================
    // STEP 3: SPECIALIZED AGENTS EXECUTION
    // ==========================================
    let currentData: StudentRecord[] = [];
    let executedSql = '';
    let mutationMessage = '';
    let affectedCount = 0;

    // Check if plan contains DB Agent steps
    const hasDbStep = dynamicPlan.steps.some(s => s.agent === 'db');
    if (hasDbStep) {
      sendEvent({
        type: 'AGENT_STARTED',
        taskId,
        timestamp: Date.now(),
        agentId: 'db',
        message: 'DB Agent active: Validating parameters and querying campus database'
      });

      await delay(400);

      if (structuredInput.requestType === 'write') {
        // Mutation handling
        sendEvent({
          type: 'AGENT_WORKING',
          taskId,
          timestamp: Date.now(),
          agentId: 'db',
          message: `Validating write request for target "${structuredInput.updateTargetName || 'Student'}" with target CGPA ${structuredInput.newCgpaValue || 9.5}`
        });

        await delay(500);

        const targetName = structuredInput.updateTargetName || 'Rahul';
        const newCgpaVal = structuredInput.newCgpaValue !== undefined ? structuredInput.newCgpaValue : 9.5;
        const updateRes = dbInstance.updateStudentCgpa(targetName, newCgpaVal);

        executedSql = updateRes.sql;
        mutationMessage = updateRes.message;
        affectedCount = updateRes.affected.length;

        sendEvent({
          type: 'AGENT_WORKING',
          taskId,
          timestamp: Date.now(),
          agentId: 'db',
          message: `Executed SQL: ${executedSql}`,
          log: {
            id: `log-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            agentId: 'db',
            level: 'info',
            message: `SQL Statement Executed: ${executedSql}`
          }
        });

        // Re-query students to show updated data
        const queryRes = dbInstance.queryStudents({
          department: structuredInput.targetDepartment,
          limit: 100,
          sortBy: 'cgpa',
          sortOrder: 'desc'
        });
        currentData = queryRes.records;
      } else {
        // Read handling
        sendEvent({
          type: 'AGENT_WORKING',
          taskId,
          timestamp: Date.now(),
          agentId: 'db',
          message: `Building SQL query for Department: "${structuredInput.targetDepartment || 'All'}", Limit: ${structuredInput.limit || 100}, Max Attendance: ${structuredInput.maxAttendance || 'None'}`
        });

        await delay(500);

        const queryRes = dbInstance.queryStudents({
          department: structuredInput.targetDepartment,
          limit: structuredInput.limit,
          minCgpa: structuredInput.minCgpa,
          maxCgpa: structuredInput.maxCgpa,
          maxAttendance: structuredInput.maxAttendance,
          searchName: structuredInput.searchStudentName,
          sortBy: 'cgpa',
          sortOrder: 'desc'
        });

        currentData = queryRes.records;
        executedSql = queryRes.sql;

        sendEvent({
          type: 'AGENT_WORKING',
          taskId,
          timestamp: Date.now(),
          agentId: 'db',
          message: `SQL executed successfully. Fetched ${currentData.length} records.`,
          log: {
            id: `log-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            agentId: 'db',
            level: 'success',
            message: `Fetched ${currentData.length} rows using SQL: ${executedSql}`
          }
        });
      }

      await delay(400);

      sendEvent({
        type: 'AGENT_COMPLETED',
        taskId,
        timestamp: Date.now(),
        agentId: 'db',
        message: `DB Agent completed. Rows returned/modified: ${currentData.length}`,
        agentState: {
          status: 'complete',
          outputData: { recordCount: currentData.length, sql: executedSql }
        }
      });

      await delay(400);
    }

    // Check if plan contains Analytics Agent steps
    const hasAnalyticsStep = dynamicPlan.steps.some(s => s.agent === 'analytics');
    let metrics: ReturnType<typeof dbInstance.calculateMetrics> | undefined;

    if (hasAnalyticsStep) {
      sendEvent({
        type: 'AGENT_STARTED',
        taskId,
        timestamp: Date.now(),
        agentId: 'analytics',
        message: 'Analytics Agent active: Computing metrics, department distributions, and percentiles'
      });

      await delay(500);

      sendEvent({
        type: 'AGENT_WORKING',
        taskId,
        timestamp: Date.now(),
        agentId: 'analytics',
        message: `Calculating aggregations across ${currentData.length} student records...`
      });

      metrics = dbInstance.calculateMetrics(currentData);

      await delay(400);

      sendEvent({
        type: 'AGENT_COMPLETED',
        taskId,
        timestamp: Date.now(),
        agentId: 'analytics',
        message: `Analytics Agent completed. Average CGPA: ${metrics.averageCgpa}, Max CGPA: ${metrics.highestCgpa}`,
        agentState: {
          status: 'complete',
          outputData: metrics
        }
      });

      await delay(400);
    }

    // Step 4: Output Agent
    sendEvent({
      type: 'AGENT_STARTED',
      taskId,
      timestamp: Date.now(),
      agentId: 'output',
      message: 'Output Agent active: Formatting response tables, summary cards, and CSV exports'
    });

    await delay(500);

    // Build final summary text
    let summaryText = '';
    if (structuredInput.requestType === 'write') {
      summaryText = `Database update successfully executed! ${mutationMessage}. ${currentData.length} student records refreshed.`;
      if (metrics && metrics.averageCgpa) {
        summaryText += ` Recalculated department average CGPA: ${metrics.averageCgpa}.`;
      }
    } else if (structuredInput.requestType === 'analytics') {
      summaryText = `Performance analytics computed for ${metrics?.totalRecords || currentData.length} students. Average CGPA: ${metrics?.averageCgpa || 0}, Highest: ${metrics?.highestCgpa || 0}, Attendance Avg: ${metrics?.avgAttendance || 0}%.`;
    } else {
      summaryText = `Retrieved ${currentData.length} student record(s) matching criteria (${structuredInput.targetDepartment || 'All Departments'}).`;
      if (metrics && metrics.averageCgpa) {
        summaryText += ` Group Average CGPA: ${metrics.averageCgpa}.`;
      }
    }

    const csvOutput = dbInstance.toCSV(currentData);

    sendEvent({
      type: 'AGENT_WORKING',
      taskId,
      timestamp: Date.now(),
      agentId: 'output',
      message: 'Formatted summary card, table schema, and CSV payload ready.'
    });

    await delay(300);

    sendEvent({
      type: 'AGENT_COMPLETED',
      taskId,
      timestamp: Date.now(),
      agentId: 'output',
      message: 'Output Agent completed. Result card ready.',
      agentState: {
        status: 'complete'
      }
    });

    await delay(300);

    // Final RESULT_READY event
    const finalResult: OrchestrationResult = {
      summary: summaryText,
      queryExecuted: executedSql,
      mutationExecuted: mutationMessage,
      affectedCount,
      data: currentData,
      metrics,
      csvData: csvOutput,
      rawPlan: dynamicPlan,
      structuredIntent: structuredInput
    };

    sendEvent({
      type: 'RESULT_READY',
      taskId,
      timestamp: Date.now(),
      result: finalResult,
      message: 'All agents executed successfully. Final orchestration result ready.'
    });

  } catch (err: any) {
    console.error('[Orchestrator] Pipeline error:', err);
    sendEvent({
      type: 'AGENT_FAILED',
      taskId,
      timestamp: Date.now(),
      message: `Orchestration error: ${err.message || 'Unknown failure'}`
    });
  } finally {
    res.end();
  }
}
