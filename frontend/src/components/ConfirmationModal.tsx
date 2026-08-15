import React from 'react';
import { AlertTriangle, X, ShieldAlert, Check, Code } from 'lucide-react';
import { ConfirmationDetails } from '../types';

interface ConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  details?: ConfirmationDetails;
  isExecuting?: boolean;
}

export const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  details,
  isExecuting = false
}) => {
  if (!isOpen || !details) return null;

  const operation = (details.operation || 'MUTATION').toUpperCase();
  const table = details.target_table || 'students';
  const condition = details.condition || 'UNCONSTRAINED / ALL RECORDS';
  const affectedRecords = details.affected_records ?? 0;
  const warning = details.warning || 'This operation will modify or delete records in your database.';
  const sql = details.sql;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 border border-amber-300 dark:border-amber-700/80 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-200">
        {/* Modal Header */}
        <div className="p-5 bg-amber-50 dark:bg-amber-950/40 border-b border-amber-200 dark:border-amber-800/80 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-amber-100 dark:bg-amber-900/60 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-700">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Confirm Database Change
              </h2>
              <p className="text-[11px] text-amber-800 dark:text-amber-300 font-medium">
                Safety Confirmation Required
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            disabled={isExecuting}
            className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6 space-y-4 text-xs">
          {/* Warning Banner */}
          <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-400/40 text-amber-900 dark:text-amber-200 flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <span className="leading-relaxed font-medium">
              {warning}
            </span>
          </div>

          {/* Operation Details Card */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-slate-500 dark:text-slate-400 font-medium">Operation:</span>
              <span className="font-bold px-2 py-0.5 rounded bg-rose-100 text-rose-800 dark:bg-rose-950/80 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
                {operation}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-slate-500 dark:text-slate-400 font-medium">Target Table:</span>
              <span className="font-semibold text-slate-800 dark:text-slate-200 font-mono">
                {table}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-slate-500 dark:text-slate-400 font-medium">Condition:</span>
              <span className="font-mono text-slate-700 dark:text-slate-300 text-[11px] max-w-[240px] truncate" title={condition}>
                {condition}
              </span>
            </div>

            <div className="flex items-center justify-between pt-1 border-t border-slate-200 dark:border-slate-700">
              <span className="text-slate-500 dark:text-slate-400 font-medium">Records Affected:</span>
              <span className="text-sm font-bold text-amber-600 dark:text-amber-400">
                {affectedRecords} {affectedRecords === 1 ? 'record' : 'records'}
              </span>
            </div>
          </div>

          {/* SQL Preview if available */}
          {sql && (
            <div className="space-y-1">
              <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Code className="w-3.5 h-3.5" />
                <span>Planned SQL Statement</span>
              </span>
              <div className="p-3 rounded-lg bg-slate-900 text-emerald-400 font-mono text-[11px] overflow-x-auto border border-slate-800">
                <code>{sql}</code>
              </div>
            </div>
          )}
        </div>

        {/* Modal Actions */}
        <div className="p-4 bg-slate-50 dark:bg-slate-800/80 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-2.5">
          <button
            onClick={onClose}
            disabled={isExecuting}
            className="px-4 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-xl transition-all disabled:opacity-50 cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isExecuting}
            className="px-5 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 active:scale-95 rounded-xl shadow-xs transition-all flex items-center gap-2 disabled:opacity-50 cursor-pointer"
          >
            {isExecuting ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Applying Mutation...</span>
              </>
            ) : (
              <>
                <Check className="w-4 h-4" />
                <span>Confirm & Apply</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
