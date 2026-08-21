import React, { useState } from 'react';
import { X, Code, Copy, Check, Terminal, Database, ArrowRight, Layers, Eye } from 'lucide-react';

interface SqlViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  sqlQuery?: string;
  operation?: string;
  table?: string;
  requestedLimit?: number;
  rowsReturned?: number;
  queryIntent?: string;
}

export const SqlViewerModal: React.FC<SqlViewerModalProps> = ({
  isOpen,
  onClose,
  sqlQuery,
  operation = 'SELECT',
  table = 'students',
  requestedLimit,
  rowsReturned,
  queryIntent,
}) => {
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const displaySql = sqlQuery || 'SELECT * FROM students;';

  const handleCopy = () => {
    navigator.clipboard.writeText(displaySql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Determine effective operation and table if not explicitly provided
  let inferredOp = operation;
  let inferredTable = table;
  if (displaySql.toUpperCase().startsWith('SELECT')) inferredOp = 'SELECT';
  else if (displaySql.toUpperCase().startsWith('UPDATE')) inferredOp = 'UPDATE';
  else if (displaySql.toUpperCase().startsWith('INSERT')) inferredOp = 'INSERT';
  else if (displaySql.toUpperCase().startsWith('DELETE')) inferredOp = 'DELETE';

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-3xl flex flex-col shadow-2xl overflow-hidden font-sans animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="p-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  SQL Query Inspection
                </h2>
                <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                  Read-Only
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Live executed SQL statement and query execution telemetry
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-200 transition-all cursor-pointer shadow-xs active:scale-95"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied' : 'Copy SQL'}</span>
            </button>

            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Query Metadata Badges */}
        <div className="px-5 py-3 bg-slate-50 dark:bg-slate-850/60 border-b border-slate-200 dark:border-slate-800 flex flex-wrap items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
            <span className="font-semibold text-slate-500 dark:text-slate-400">Operation:</span>
            <span className="px-2 py-0.5 font-mono font-bold bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300 rounded-md border border-blue-200 dark:border-blue-800">
              {inferredOp}
            </span>
          </div>

          <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
            <span className="font-semibold text-slate-500 dark:text-slate-400">Table:</span>
            <span className="px-2 py-0.5 font-mono font-bold bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-md">
              {inferredTable}
            </span>
          </div>

          {requestedLimit !== undefined && requestedLimit !== null && (
            <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
              <span className="font-semibold text-slate-500 dark:text-slate-400">Requested Limit:</span>
              <span className="px-2 py-0.5 font-mono font-bold bg-purple-100 dark:bg-purple-950 text-purple-800 dark:text-purple-300 rounded-md border border-purple-200 dark:border-purple-800">
                {requestedLimit}
              </span>
            </div>
          )}

          {rowsReturned !== undefined && rowsReturned !== null && (
            <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
              <span className="font-semibold text-slate-500 dark:text-slate-400">Rows Returned:</span>
              <span className="px-2 py-0.5 font-mono font-bold bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 rounded-md border border-emerald-200 dark:border-emerald-800">
                {rowsReturned}
              </span>
            </div>
          )}
        </div>

        {/* SQL Editor / Code Block View */}
        <div className="p-5 flex-1 overflow-auto bg-slate-950 text-slate-100">
          <div className="rounded-xl bg-slate-900 border border-slate-800 p-4 font-mono text-xs shadow-inner">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800 text-[11px] text-slate-400">
              <div className="flex items-center gap-2">
                <Database className="w-3.5 h-3.5 text-blue-400" />
                <span>PostgreSQL / Supabase Engine</span>
              </div>
              <span className="text-[10px] text-slate-500 font-sans uppercase tracking-wider font-semibold">
                Deterministic Output
              </span>
            </div>
            <pre className="text-emerald-400 whitespace-pre-wrap leading-relaxed select-text font-mono font-medium">
              {displaySql}
            </pre>
          </div>

          <div className="mt-4 p-3 rounded-xl bg-slate-900/80 border border-slate-800/80 text-xs text-slate-400 flex items-start gap-2.5">
            <div className="p-1 rounded-md bg-blue-950 text-blue-400 shrink-0 mt-0.5">
              <Layers className="w-3.5 h-3.5" />
            </div>
            <div className="space-y-1">
              <p className="font-semibold text-slate-300">Deterministic Query Execution</p>
              <p className="text-[11px] text-slate-400">
                Queries apply explicit limit constraints and secondary tie-breakers (<code className="text-emerald-300">roll_number ASC</code>) to ensure consistent results when sorting by rank or CGPA.
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-50 dark:bg-slate-800/80 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between shrink-0">
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Source: Campus DB Agent Execution
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl transition-all shadow-xs cursor-pointer active:scale-95"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
