import React from 'react';
import { 
  X, 
  Database, 
  Compass, 
  LineChart, 
  Check, 
  AlertTriangle, 
  ShieldCheck, 
  FileText, 
  ArrowRight,
  Info
} from 'lucide-react';
import { AppMode } from '../types';

interface ModeSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentMode: AppMode;
  targetMode: AppMode;
  onSelectMode: (mode: AppMode) => void;
  onSelectExamplePrompt?: (prompt: string, mode: AppMode) => void;
}

interface ModeDetails {
  id: AppMode;
  title: string;
  subtitle: string;
  tagline: string;
  icon: any;
  color: string;
  bgColor: string;
  borderColor: string;
  modifiesDb: boolean;
  whatItDoes: string[];
  whatItDoesNotDo: string[];
  outputType: string;
  examples: string[];
}

const MODE_DETAILS: Record<AppMode, ModeDetails> = {
  modify: {
    id: 'modify',
    title: 'Modify Database',
    subtitle: 'Database Mutation & State Alteration',
    tagline: 'Add, update, or delete database records directly with safety guards.',
    icon: Database,
    color: 'text-amber-600 dark:text-amber-400',
    bgColor: 'bg-amber-50 dark:bg-amber-950/40',
    borderColor: 'border-amber-200 dark:border-amber-800',
    modifiesDb: true,
    whatItDoes: [
      'Executes safe INSERT, UPDATE, and DELETE operations.',
      'Requires explicit confirmation for bulk or destructive queries.',
      'Automatically synchronizes live database preview upon completion.',
      'Allows schema changes (add/drop columns) with safety gates.'
    ],
    whatItDoesNotDo: [
      'Does NOT perform complex statistical analytics or correlation models.',
      'Does NOT run Pulse agent calculations.',
      'Does NOT automatically generate multi-page PDF or PowerPoint reports.'
    ],
    outputType: 'Database mutation summary, updated row count, and live preview refresh.',
    examples: [
      "Change Rahul's CGPA to 9.2",
      "Update Arun's attendance to 95%",
      "Delete all students with CGPA below 5",
      "Add new student Ananya Roy in Computer Science with 9.1 CGPA"
    ]
  },
  explore: {
    id: 'explore',
    title: 'Explore Database',
    subtitle: 'Read-Only Data Search & Inspection',
    tagline: 'Search and view database records quickly without changing them.',
    icon: Compass,
    color: 'text-blue-600 dark:text-blue-400',
    bgColor: 'bg-blue-50 dark:bg-blue-950/40',
    borderColor: 'border-blue-200 dark:border-blue-800',
    modifiesDb: false,
    whatItDoes: [
      'Reads and filters records directly from the live database.',
      'Renders clean, interactive tables with search, sorting, and pagination.',
      'Provides on-demand Excel spreadsheet export when requested.',
      'Executes fast without computational or analytical overhead.'
    ],
    whatItDoesNotDo: [
      'Will NOT alter, insert, or delete any records.',
      'Does NOT execute statistical algorithms or risk formulas.',
      'Does NOT automatically generate PDF or PPT presentations.'
    ],
    outputType: 'Interactive table of real records + on-demand Excel download.',
    examples: [
      "Show the top 10 CSE students",
      "Find all students with CGPA above 9.0",
      "List all students in Electronics with attendance below 75%",
      "Show all active students ordered by roll number"
    ]
  },
  analyze: {
    id: 'analyze',
    title: 'Analyze & Report',
    subtitle: 'Deep Analytics & Multi-Format Scribe Reporting',
    tagline: 'Analyze data, discover insights, evaluate risks, and generate reports.',
    icon: LineChart,
    color: 'text-indigo-600 dark:text-indigo-400',
    bgColor: 'bg-indigo-50 dark:bg-indigo-950/40',
    borderColor: 'border-indigo-200 dark:border-indigo-800',
    modifiesDb: false,
    whatItDoes: [
      'Executes Pulse deterministic analytics (rankings, composite weighting, group comparisons).',
      'Calculates academic risk factors and student percentiles.',
      'Renders comprehensive Scribe reports in Text, Excel, PDF, or PowerPoint.',
      'Provides actionable executive insights and statistical summaries.'
    ],
    whatItDoesNotDo: [
      'Will NOT modify or overwrite any database records.',
      'Does NOT generate all document formats simultaneously (only user-selected format).'
    ],
    outputType: 'Statistical metrics, risk evaluation, and selected artifact (Text / Excel / PDF / PPT).',
    examples: [
      "Rank the top 10 students using 80% marks and 20% LeetCode count",
      "Find academically at-risk students and explain reasons",
      "Compare Computer Science and Electronics department performance",
      "Analyze attendance correlation with CGPA and create a detailed report in PDF"
    ]
  }
};

export const ModeSelectorModal: React.FC<ModeSelectorModalProps> = ({
  isOpen,
  onClose,
  currentMode,
  targetMode,
  onSelectMode,
  onSelectExamplePrompt
}) => {
  if (!isOpen) return null;

  const info = MODE_DETAILS[targetMode] || MODE_DETAILS.explore;
  const Icon = info.icon;
  const isCurrent = currentMode === targetMode;

  const handleUseMode = () => {
    onSelectMode(targetMode);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className={`p-5 ${info.bgColor} border-b ${info.borderColor} flex items-start justify-between`}>
          <div className="flex items-center gap-3.5">
            <div className={`p-2.5 rounded-xl bg-white dark:bg-slate-800 border ${info.borderColor} ${info.color} shadow-xs`}>
              <Icon className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
                  {info.title}
                </h2>
                {isCurrent && (
                  <span className="px-2 py-0.5 text-[11px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 rounded-full border border-emerald-200 dark:border-emerald-800">
                    Active Mode
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
                {info.subtitle}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 rounded-lg hover:bg-white/50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5 custom-scrollbar text-xs leading-relaxed text-slate-700 dark:text-slate-300">
          {/* Summary Tagline */}
          <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 font-medium text-slate-800 dark:text-slate-200 flex items-start gap-2.5">
            <Info className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
            <span>{info.tagline}</span>
          </div>

          {/* Database Risk Warning Banner */}
          {info.modifiesDb ? (
            <div className="p-3.5 rounded-xl bg-amber-50/80 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 text-amber-900 dark:text-amber-300 flex items-start gap-3">
              <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold block">This mode can modify your database.</span>
                <span className="text-[11px] text-amber-800 dark:text-amber-400">
                  Destructive operations (e.g. bulk deletes, column drops) will prompt for explicit confirmation before executing.
                </span>
              </div>
            </div>
          ) : (
            <div className="p-3.5 rounded-xl bg-emerald-50/80 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900 text-emerald-900 dark:text-emerald-300 flex items-start gap-3">
              <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold block">Read-only mode: Your database will not be modified.</span>
                <span className="text-[11px] text-emerald-800 dark:text-emerald-400">
                  All queries in this mode are strictly non-mutating and safe.
                </span>
              </div>
            </div>
          )}

          {/* Capabilities Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/80 space-y-2">
              <h3 className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                <span>What It Does</span>
              </h3>
              <ul className="space-y-1.5 pl-1">
                {info.whatItDoes.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-[11px] text-slate-600 dark:text-slate-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0 mt-1.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/80 space-y-2">
              <h3 className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <X className="w-3.5 h-3.5 text-rose-500" />
                <span>What It Does NOT Do</span>
              </h3>
              <ul className="space-y-1.5 pl-1">
                {info.whatItDoesNotDo.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-[11px] text-slate-600 dark:text-slate-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-400 shrink-0 mt-1.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Example Prompts */}
          <div className="space-y-2">
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <FileText className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
              <span>Example Prompts</span>
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {info.examples.map((ex, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    if (onSelectExamplePrompt) {
                      onSelectExamplePrompt(ex, targetMode);
                    }
                    onSelectMode(targetMode);
                    onClose();
                  }}
                  className="text-left p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800 hover:bg-blue-50 dark:hover:bg-slate-700/80 border border-slate-200 dark:border-slate-700 hover:border-blue-300 dark:hover:border-blue-700 transition-all text-[11px] text-slate-700 dark:text-slate-300 flex items-center justify-between group"
                >
                  <span className="truncate pr-2">"{ex}"</span>
                  <ArrowRight className="w-3 h-3 text-slate-400 group-hover:text-blue-600 dark:group-hover:text-blue-400 shrink-0 transition-transform group-hover:translate-x-0.5" />
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-50 dark:bg-slate-800/80 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-2.5">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-xl transition-all"
          >
            Cancel
          </button>
          <button
            onClick={handleUseMode}
            className={`px-5 py-2 text-xs font-semibold text-white rounded-xl shadow-xs transition-all flex items-center gap-2 ${
              targetMode === 'modify'
                ? 'bg-amber-600 hover:bg-amber-700'
                : targetMode === 'explore'
                ? 'bg-blue-600 hover:bg-blue-700'
                : 'bg-indigo-600 hover:bg-indigo-700'
            }`}
          >
            <Check className="w-4 h-4" />
            <span>{isCurrent ? 'Continue with This Mode' : 'Use This Mode'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
