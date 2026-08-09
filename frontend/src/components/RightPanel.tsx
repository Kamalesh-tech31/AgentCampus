import React, { useState } from 'react';
import { 
  ListChecks, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  Table, 
  Download, 
  ChevronDown, 
  ChevronUp, 
  Code, 
  FileText
} from 'lucide-react';
import { DynamicPlan, OrchestrationResult } from '../types';

interface RightPanelProps {
  plan?: DynamicPlan;
  result?: OrchestrationResult;
  activeTurnPrompt?: string;
  isExecuting: boolean;
  onOpenDataViewer: () => void;
  onOpenSqlViewer: (sql: string) => void;
  onOpenPlanJson: () => void;
  onExportCsv: () => void;
}

export const RightPanel: React.FC<RightPanelProps> = ({
  plan,
  result,
  activeTurnPrompt,
  isExecuting,
  onOpenDataViewer,
  onOpenSqlViewer,
  onOpenPlanJson,
  onExportCsv
}) => {
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  const steps = plan?.steps || [];
  const completedSteps = steps.filter(s => s.status === 'complete').length;
  const totalSteps = steps.length;
  const progressPercent = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;

  return (
    <div className="w-80 lg:w-96 h-full bg-slate-50 border-l border-gray-200 flex flex-col shrink-0 select-none overflow-hidden">
      {/* Panel Header */}
      <div className="p-3.5 border-b border-gray-200 bg-white flex flex-col gap-1 min-h-[56px] justify-center">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ListChecks className="w-4 h-4 text-blue-600" />
            <span className="text-xs font-semibold text-gray-900 tracking-tight">
              Plan & Results
            </span>
          </div>
          {totalSteps > 0 && (
            <span className="text-[11px] font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full border border-blue-200 shrink-0">
              {completedSteps} / {totalSteps} Steps
            </span>
          )}
        </div>
        {activeTurnPrompt && (
          <p className="text-[11px] text-gray-500 truncate" title={activeTurnPrompt}>
            Showing results for: <span className="text-gray-700 font-medium">"{activeTurnPrompt}"</span>
          </p>
        )}
      </div>

      {/* Progress Bar */}
      {totalSteps > 0 && (
        <div className="w-full bg-gray-200 h-1 overflow-hidden">
          <div
            className="bg-blue-600 h-full transition-all duration-500 ease-out"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      )}

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-3.5 space-y-4 custom-scrollbar">
        {/* Numbered Plan Checklist */}
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider px-1">
            Plan Steps
          </h3>

          {!plan || steps.length === 0 ? (
            <div className="p-4 text-center rounded-xl bg-white border border-dashed border-gray-200 text-gray-400 text-xs">
              Waiting for plan generation...
            </div>
          ) : (
            <div className="space-y-2">
              {steps.map((step) => {
                const isDone = step.status === 'complete';
                const isRunning = step.status === 'running';
                const isFailed = step.status === 'failed';

                return (
                  <div
                    key={step.id}
                    className={`p-3 rounded-xl border transition-all bg-white ${
                      isRunning
                        ? 'border-blue-400 shadow-xs ring-1 ring-blue-100'
                        : isDone
                        ? 'border-gray-200'
                        : isFailed
                        ? 'border-red-300 bg-red-50/20'
                        : 'border-gray-200 opacity-60'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5 min-w-0 pr-2">
                        <span className="w-5 h-5 rounded-full bg-gray-100 text-gray-700 flex items-center justify-center text-[11px] font-semibold shrink-0">
                          {step.stepNumber}
                        </span>
                        <span className="text-xs font-medium text-gray-800 truncate">
                          {step.action}
                        </span>
                      </div>

                      <div className="shrink-0">
                        {isDone && <CheckCircle2 className="w-4 h-4 text-blue-600" />}
                        {isRunning && <Clock className="w-4 h-4 text-blue-600 animate-spin" />}
                        {isFailed && <AlertCircle className="w-4 h-4 text-red-600" />}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Final Result Section */}
        {result && (
          <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3 shadow-xs">
            <h3 className="text-xs font-semibold text-gray-900">
              Result Summary
            </h3>

            {/* One short summary sentence */}
            <p className="text-xs text-gray-600 leading-relaxed">
              {result.summary}
            </p>

            {/* Primary Action Buttons */}
            <div className="pt-2 flex items-center gap-2">
              <button
                onClick={onOpenDataViewer}
                className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs transition-all cursor-pointer shadow-xs active:scale-95"
              >
                <Table className="w-3.5 h-3.5" />
                <span>View Data</span>
              </button>

              <button
                onClick={onExportCsv}
                className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 border border-gray-200 font-medium text-xs transition-all cursor-pointer active:scale-95"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Export CSV</span>
              </button>
            </div>

            {/* Optional Technical Details Expand */}
            <div className="pt-2 border-t border-gray-100">
              <button
                onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                className="flex items-center justify-between w-full text-[11px] font-medium text-gray-500 hover:text-gray-800 cursor-pointer"
              >
                <span>Technical Details</span>
                {showTechnicalDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>

              {showTechnicalDetails && (
                <div className="mt-2.5 pt-2 border-t border-gray-100 grid grid-cols-2 gap-2 text-xs">
                  {result.queryExecuted && (
                    <button
                      onClick={() => onOpenSqlViewer(result.queryExecuted!)}
                      className="flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg bg-gray-50 hover:bg-gray-100 text-gray-700 border border-gray-200 text-[11px] font-medium cursor-pointer"
                    >
                      <Code className="w-3.5 h-3.5 text-gray-500" />
                      <span>View SQL</span>
                    </button>
                  )}

                  <button
                    onClick={onOpenPlanJson}
                    className="flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg bg-gray-50 hover:bg-gray-100 text-gray-700 border border-gray-200 text-[11px] font-medium cursor-pointer"
                  >
                    <FileText className="w-3.5 h-3.5 text-gray-500" />
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

