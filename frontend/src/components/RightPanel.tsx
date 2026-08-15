import React, { useState } from 'react';
import { 
  ListChecks, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  Table as TableIcon, 
  Download, 
  ChevronDown, 
  ChevronUp, 
  Code, 
  FileText, 
  Presentation, 
  FileSpreadsheet, 
  Sparkles,
  BarChart3,
  ExternalLink,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  Database
} from 'lucide-react';
import { AppMode, DynamicPlan, OrchestrationResult, StudentRecord } from '../types';
import { getFileDownloadUrl } from '../services/api';

interface RightPanelProps {
  mode: AppMode;
  plan?: DynamicPlan;
  result?: OrchestrationResult;
  activeTurnPrompt?: string;
  isExecuting: boolean;
  onOpenDataViewer: () => void;
  onOpenDatabasePreview: () => void;
  onOpenSqlViewer: (sql: string) => void;
  onOpenPlanJson: () => void;
  onExportCsv: () => void;
}

export const RightPanel: React.FC<RightPanelProps> = ({
  mode,
  plan,
  result,
  activeTurnPrompt,
  isExecuting,
  onOpenDataViewer,
  onOpenDatabasePreview,
  onOpenSqlViewer,
  onOpenPlanJson,
  onExportCsv,
}) => {
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  const steps = plan?.steps || [];
  const completedSteps = steps.filter((s) => s.status === 'complete').length;
  const totalSteps = steps.length;
  const progressPercent = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;

  const records = result?.data || [];
  const metrics = result?.metrics;
  const outputFile = result?.outputFile;
  const outputFormat = result?.outputFormat || 'text';
  const requiresConfirmation = result?.requiresConfirmation;
  const confirmationDetails = result?.confirmationDetails;

  return (
    <div className="w-80 lg:w-96 h-full bg-slate-50 dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 flex flex-col shrink-0 select-none overflow-hidden transition-colors">
      {/* Panel Header */}
      <div className="p-3.5 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col gap-1 min-h-[56px] justify-center">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ListChecks className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            <span className="text-xs font-bold text-slate-900 dark:text-slate-100 tracking-tight">
              Plan & Results
            </span>
          </div>
          {totalSteps > 0 && (
            <span className="text-[11px] font-semibold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/60 px-2.5 py-0.5 rounded-full border border-blue-200 dark:border-blue-800 shrink-0">
              {completedSteps} / {totalSteps} Steps
            </span>
          )}
        </div>
        {activeTurnPrompt && (
          <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate" title={activeTurnPrompt}>
            Prompt: <span className="text-slate-700 dark:text-slate-300 font-medium">"{activeTurnPrompt}"</span>
          </p>
        )}
      </div>

      {/* Progress Bar */}
      {totalSteps > 0 && (
        <div className="w-full bg-slate-200 dark:bg-slate-800 h-1 overflow-hidden">
          <div
            className="bg-blue-600 dark:bg-blue-500 h-full transition-all duration-500 ease-out"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      )}

      {/* Scrollable Content Area */}
      <div className="flex-1 overflow-y-auto p-3.5 space-y-4 custom-scrollbar">
        {/* Numbered Plan Checklist */}
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider px-1">
            Dynamic Workflow Plan
          </h3>

          {!plan || steps.length === 0 ? (
            <div className="p-4 text-center rounded-xl bg-white dark:bg-slate-800/60 border border-dashed border-slate-200 dark:border-slate-700 text-slate-400 text-xs">
              {isExecuting ? 'Synthesizing execution plan...' : 'Waiting for user request...'}
            </div>
          ) : (
            <div className="space-y-1.5">
              {steps.map((step) => {
                const isDone = step.status === 'complete';
                const isRunning = step.status === 'running';
                const isFailed = step.status === 'failed';

                return (
                  <div
                    key={step.id}
                    className={`p-2.5 rounded-xl border transition-all bg-white dark:bg-slate-800/80 ${
                      isRunning
                        ? 'border-blue-400 dark:border-blue-500 shadow-xs ring-1 ring-blue-100 dark:ring-blue-900/50'
                        : isDone
                        ? 'border-slate-200 dark:border-slate-700'
                        : isFailed
                        ? 'border-rose-300 dark:border-rose-800 bg-rose-50/20'
                        : 'border-slate-200 dark:border-slate-700/60 opacity-60'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5 min-w-0 pr-2">
                        <span className="w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 flex items-center justify-center text-[10px] font-bold shrink-0">
                          {step.stepNumber}
                        </span>
                        <span className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">
                          {step.action}
                        </span>
                      </div>

                      <div className="shrink-0">
                        {isDone && <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />}
                        {isRunning && <Clock className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-spin" />}
                        {isFailed && <AlertCircle className="w-4 h-4 text-rose-600" />}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Confirmation Gate Notification in Results Panel */}
        {requiresConfirmation && confirmationDetails && (
          <div className="p-4 rounded-xl border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/40 space-y-2.5 text-xs text-amber-900 dark:text-amber-200 shadow-xs">
            <div className="flex items-center gap-2 font-bold">
              <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400" />
              <span>Awaiting Confirmation</span>
            </div>
            <p className="text-[11px] leading-relaxed">
              {confirmationDetails.warning || 'Destructive operation requires explicit confirmation.'}
            </p>
            <div className="p-2 bg-white/70 dark:bg-slate-900/60 rounded-lg border border-amber-200 dark:border-amber-800 text-[11px]">
              <div><strong>Operation:</strong> {confirmationDetails.operation}</div>
              <div><strong>Affected Records:</strong> {confirmationDetails.affected_records}</div>
            </div>
          </div>
        )}

        {/* Mode-Dependent Result Section */}
        {result && !requiresConfirmation && (
          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/80 p-4 space-y-3.5 shadow-xs">
            {/* Header with Mode Badge */}
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                <span>Execution Result</span>
              </h3>
              <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-600">
                {mode}
              </span>
            </div>

            {/* Summary Text */}
            <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed font-normal">
              {result.summary}
            </p>

            {/* 1. EXPLORE MODE SPECIFIC RESULT */}
            {mode === 'explore' && (
              <div className="space-y-3 pt-1">
                <div className="flex items-center justify-between p-2.5 rounded-xl bg-blue-50/70 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 text-xs">
                  <span className="text-blue-900 dark:text-blue-300 font-medium">Retrieved Records:</span>
                  <span className="font-bold text-blue-700 dark:text-blue-400">
                    {records.length} {records.length === 1 ? 'record' : 'records'}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={onOpenDataViewer}
                    className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs transition-all cursor-pointer shadow-xs active:scale-95"
                  >
                    <TableIcon className="w-3.5 h-3.5" />
                    <span>View Data Table</span>
                  </button>

                  <button
                    onClick={onExportCsv}
                    className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-600 font-semibold text-xs transition-all cursor-pointer active:scale-95"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download Excel</span>
                  </button>
                </div>
              </div>
            )}

            {/* 2. MODIFY MODE SPECIFIC RESULT */}
            {mode === 'modify' && (
              <div className="space-y-3 pt-1">
                <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 space-y-1.5">
                  <div className="flex items-center gap-1.5 text-emerald-800 dark:text-emerald-300 font-bold text-xs">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                    <span>Database Updated Successfully</span>
                  </div>
                  <p className="text-[11px] text-emerald-700 dark:text-emerald-400">
                    Preview refreshed automatically with latest state.
                  </p>
                </div>

                <button
                  onClick={onOpenDatabasePreview}
                  className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-semibold text-xs transition-all cursor-pointer shadow-xs active:scale-95"
                >
                  <Database className="w-3.5 h-3.5" />
                  <span>Inspect Live Database Preview</span>
                </button>
              </div>
            )}

            {/* 3. ANALYZE MODE SPECIFIC RESULT */}
            {mode === 'analyze' && (
              <div className="space-y-3 pt-1">
                {/* Metrics Highlights Card */}
                {metrics && (
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {metrics.averageCgpa !== undefined && (
                      <div className="p-2.5 rounded-xl bg-indigo-50/70 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800">
                        <span className="text-[10px] text-indigo-700 dark:text-indigo-400 font-medium block">Average CGPA</span>
                        <span className="text-base font-bold text-indigo-900 dark:text-indigo-200">{metrics.averageCgpa.toFixed(2)}</span>
                      </div>
                    )}
                    {metrics.totalRecords !== undefined && (
                      <div className="p-2.5 rounded-xl bg-indigo-50/70 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800">
                        <span className="text-[10px] text-indigo-700 dark:text-indigo-400 font-medium block">Analyzed Pool</span>
                        <span className="text-base font-bold text-indigo-900 dark:text-indigo-200">{metrics.totalRecords} students</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Generated File Output Card */}
                {outputFile && (
                  <div className="p-3 rounded-xl bg-indigo-50 dark:bg-indigo-950/50 border border-indigo-200 dark:border-indigo-800 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-indigo-900 dark:text-indigo-200 flex items-center gap-1.5">
                        {outputFormat === 'pdf' && <FileText className="w-4 h-4 text-rose-600" />}
                        {outputFormat === 'ppt' && <Presentation className="w-4 h-4 text-orange-600" />}
                        {outputFormat === 'excel' && <FileSpreadsheet className="w-4 h-4 text-emerald-600" />}
                        <span>Generated {outputFormat.toUpperCase()} Artifact</span>
                      </span>
                      <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-950 px-2 py-0.5 rounded-full">
                        Ready
                      </span>
                    </div>

                    <a
                      href={getFileDownloadUrl(outputFile)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs transition-all shadow-xs active:scale-95"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>Download {outputFormat.toUpperCase()}</span>
                    </a>
                  </div>
                )}

                {/* View Data Grid Button */}
                {records.length > 0 && (
                  <button
                    onClick={onOpenDataViewer}
                    className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-600 font-semibold text-xs transition-all cursor-pointer"
                  >
                    <TableIcon className="w-3.5 h-3.5" />
                    <span>View Analyzed Dataset ({records.length} rows)</span>
                  </button>
                )}
              </div>
            )}

            {/* Technical Details Collapsible */}
            <div className="pt-2 border-t border-slate-100 dark:border-slate-700">
              <button
                onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                className="flex items-center justify-between w-full text-[11px] font-medium text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 cursor-pointer"
              >
                <span>Technical Trace</span>
                {showTechnicalDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>

              {showTechnicalDetails && (
                <div className="mt-2.5 pt-2 border-t border-slate-100 dark:border-slate-700 grid grid-cols-2 gap-2 text-xs">
                  {result.queryExecuted && (
                    <button
                      onClick={() => onOpenSqlViewer(result.queryExecuted!)}
                      className="flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg bg-slate-50 dark:bg-slate-700/60 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-600 text-[11px] font-medium cursor-pointer"
                    >
                      <Code className="w-3.5 h-3.5 text-slate-500" />
                      <span>View SQL</span>
                    </button>
                  )}

                  <button
                    onClick={onOpenPlanJson}
                    className="flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg bg-slate-50 dark:bg-slate-700/60 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-600 text-[11px] font-medium cursor-pointer"
                  >
                    <FileText className="w-3.5 h-3.5 text-slate-500" />
                    <span>Plan JSON</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
