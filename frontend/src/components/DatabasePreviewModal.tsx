import React, { useState, useEffect } from 'react';
import { 
  Database, 
  X, 
  RefreshCw, 
  Table as TableIcon, 
  Columns, 
  Hash, 
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { DatabaseTablePreview } from '../types';
import { fetchDatabasePreview } from '../services/api';

interface DatabasePreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRefreshSuccess?: () => void;
}

export const DatabasePreviewModal: React.FC<DatabasePreviewModalProps> = ({
  isOpen,
  onClose,
  onRefreshSuccess
}) => {
  const [tables, setTables] = useState<DatabaseTablePreview[]>([]);
  const [selectedTableIndex, setSelectedTableIndex] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<string>('');

  const loadPreview = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchDatabasePreview(10);
      setTables(data.tables || []);
      setLastRefreshed(new Date().toLocaleTimeString());
      if (onRefreshSuccess) onRefreshSuccess();
    } catch (err: any) {
      setError(err.message || 'Failed to fetch database preview.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadPreview();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const currentTable = tables[selectedTableIndex] || tables[0];
  const columns = currentTable?.columns || [];
  const sampleRecords = currentTable?.sampleRecords || [];
  const rowCount = currentTable?.rowCount ?? 0;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col shadow-2xl overflow-hidden font-sans">
        {/* Modal Header */}
        <div className="p-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  Live Database Preview
                </h2>
                <span className="px-2 py-0.5 text-[10px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 rounded-full border border-emerald-200 dark:border-emerald-800 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Live Sync
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Real database schema and live records directly from backend
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={loadPreview}
              disabled={isLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 rounded-xl text-xs font-medium transition-all cursor-pointer disabled:opacity-50"
              title="Refresh Live Data"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-blue-600' : ''}`} />
              <span>{isLoading ? 'Refreshing...' : 'Refresh DB'}</span>
            </button>

            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Table Selector Tabs */}
        {tables.length > 0 && (
          <div className="px-4 py-2 bg-slate-50 dark:bg-slate-800/40 border-b border-slate-200 dark:border-slate-800 flex items-center gap-2 overflow-x-auto shrink-0 custom-scrollbar">
            <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mr-1 flex items-center gap-1">
              <TableIcon className="w-3 h-3" />
              Tables:
            </span>
            {tables.map((t, idx) => (
              <button
                key={t.name}
                onClick={() => setSelectedTableIndex(idx)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all flex items-center gap-2 cursor-pointer ${
                  selectedTableIndex === idx
                    ? 'bg-blue-600 text-white shadow-xs'
                    : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700'
                }`}
              >
                <span className="font-mono">{t.name}</span>
                <span className={`px-1.5 py-0.2 rounded-full text-[10px] ${
                  selectedTableIndex === idx ? 'bg-blue-500 text-white' : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400'
                }`}>
                  {t.rowCount}
                </span>
              </button>
            ))}
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="m-4 p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 rounded-xl text-xs text-rose-800 dark:text-rose-300 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Modal Content */}
        <div className="flex-1 overflow-hidden flex flex-col p-4 space-y-4">
          {/* Table Metadata Bar */}
          {currentTable && (
            <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700 flex flex-wrap items-center justify-between gap-3 shrink-0 text-xs">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1.5">
                  <span className="text-slate-500 dark:text-slate-400">Current Table:</span>
                  <span className="font-bold text-slate-900 dark:text-slate-100 font-mono">
                    {currentTable.name}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Hash className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-slate-500 dark:text-slate-400">Total Records:</span>
                  <span className="font-semibold text-blue-600 dark:text-blue-400">
                    {rowCount}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Columns className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-slate-500 dark:text-slate-400">Columns:</span>
                  <span className="font-semibold text-slate-700 dark:text-slate-300">
                    {columns.length}
                  </span>
                </div>
              </div>

              {lastRefreshed && (
                <span className="text-[11px] text-slate-400">
                  Last refreshed at {lastRefreshed}
                </span>
              )}
            </div>
          )}

          {/* Columns Tag Cloud */}
          {columns.length > 0 && (
            <div className="space-y-1 shrink-0">
              <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Registered Schema Columns & Types
              </span>
              <div className="flex flex-wrap gap-1.5 p-2 bg-white dark:bg-slate-800/30 rounded-xl border border-slate-200 dark:border-slate-700/80 max-h-24 overflow-y-auto custom-scrollbar">
                {columns.map((col) => (
                  <span
                    key={col.name}
                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-[11px] text-slate-700 dark:text-slate-300"
                  >
                    <span className="font-mono font-medium text-slate-900 dark:text-slate-100">{col.name}</span>
                    <span className="text-[9px] px-1 py-0.2 bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 rounded font-mono">
                      {col.type}
                    </span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Sample Records Data Grid */}
          <div className="flex-1 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/20 flex flex-col">
            <div className="p-2.5 bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between shrink-0">
              <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                <TableIcon className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                <span>Live Sample Records ({sampleRecords.length} records)</span>
              </span>
            </div>

            <div className="flex-1 overflow-auto custom-scrollbar">
              {sampleRecords.length === 0 ? (
                <div className="h-full flex items-center justify-center p-8 text-center text-xs text-slate-400">
                  {isLoading ? 'Loading records...' : 'No sample records available in this table.'}
                </div>
              ) : (
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="sticky top-0 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold border-b border-slate-200 dark:border-slate-700 z-10">
                    <tr>
                      {columns.map((col) => (
                        <th key={col.name} className="px-3.5 py-2.5 font-mono text-[11px] whitespace-nowrap">
                          {col.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-800 dark:text-slate-200 font-normal">
                    {sampleRecords.map((row, rIdx) => (
                      <tr key={rIdx} className="hover:bg-blue-50/40 dark:hover:bg-slate-700/30 transition-colors">
                        {columns.map((col) => {
                          const val = row[col.name];
                          const displayVal = typeof val === 'object' && val !== null ? JSON.stringify(val) : String(val ?? '—');
                          const isNumeric = typeof val === 'number' || (col.name === 'cgpa' || col.name === 'attendance');

                          return (
                            <td key={col.name} className={`px-3.5 py-2 whitespace-nowrap text-[11px] ${
                              col.name === 'cgpa' ? 'font-semibold text-blue-600 dark:text-blue-400' : ''
                            }`}>
                              {displayVal}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-50 dark:bg-slate-800/80 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between shrink-0 text-xs">
          <div className="text-slate-500 dark:text-slate-400 text-[11px]">
            Connected to Supabase PostgreSQL & in-memory synced store
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl transition-all shadow-xs cursor-pointer"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
