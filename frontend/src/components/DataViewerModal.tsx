import React, { useState } from 'react';
import { X, Database, Search, Download, Code, ArrowUpDown } from 'lucide-react';
import { StudentRecord } from '../types';

interface DataViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  students: StudentRecord[];
  sqlQuery?: string;
  onExportCsv: () => void;
}

export const DataViewerModal: React.FC<DataViewerModalProps> = ({
  isOpen,
  onClose,
  students,
  sqlQuery,
  onExportCsv
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDept, setSelectedDept] = useState('All');
  const [sortField, setSortField] = useState<keyof StudentRecord>('cgpa');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [activeTab, setActiveTab] = useState<'table' | 'sql'>('table');

  if (!isOpen) return null;

  const departments = ['All', 'Computer Science', 'Electronics', 'Mechanical', 'Civil', 'Data Science', 'AI & ML'];

  let filtered = students.filter(s => {
    const matchesDept = selectedDept === 'All' || s.department === selectedDept;
    const matchesSearch = 
      s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.rollNumber.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.email.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesDept && matchesSearch;
  });

  filtered.sort((a, b) => {
    const valA = a[sortField] ?? '';
    const valB = b[sortField] ?? '';
    if (valA < valB) return sortOrder === 'asc' ? -1 : 1;
    if (valA > valB) return sortOrder === 'asc' ? 1 : -1;
    return 0;
  });

  const handleSort = (field: keyof StudentRecord) => {
    if (sortField === field) {
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-gray-900/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white border border-gray-200 rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col shadow-xl overflow-hidden font-sans">
        {/* Modal Header */}
        <div className="p-4 bg-white border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-blue-50 border border-blue-200 text-blue-600">
              <Database className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-gray-900">Campus Student Database</h2>
              <p className="text-xs text-gray-500">
                Showing {filtered.length} of {students.length} student records
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center bg-gray-100 rounded-lg p-0.5 border border-gray-200 text-xs">
              <button
                onClick={() => setActiveTab('table')}
                className={`px-3 py-1 rounded-md transition-all cursor-pointer font-medium ${
                  activeTab === 'table' ? 'bg-white text-blue-600 shadow-xs' : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Data Grid
              </button>
              <button
                onClick={() => setActiveTab('sql')}
                className={`px-3 py-1 rounded-md transition-all cursor-pointer font-medium ${
                  activeTab === 'sql' ? 'bg-white text-blue-600 shadow-xs' : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                SQL Query
              </button>
            </div>

            <button
              onClick={onExportCsv}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 border border-gray-200 rounded-lg text-xs font-medium text-gray-700 transition-all cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export CSV</span>
            </button>

            <button
              onClick={onClose}
              className="p-1.5 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Filters Bar */}
        {activeTab === 'table' && (
          <div className="p-3 bg-gray-50/50 border-b border-gray-200 flex flex-wrap items-center justify-between gap-3 text-xs">
            {/* Search input */}
            <div className="relative flex-1 min-w-[200px]">
              <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Search student name, roll number, or email..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-white border border-gray-200 rounded-lg pl-8 pr-3 py-1.5 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-blue-600"
              />
            </div>

            {/* Department Filter */}
            <div className="flex items-center gap-1 overflow-x-auto pb-1 max-w-full custom-scrollbar">
              {departments.map((dept) => (
                <button
                  key={dept}
                  onClick={() => setSelectedDept(dept)}
                  className={`px-2.5 py-1 rounded-lg text-[11px] whitespace-nowrap transition-all cursor-pointer font-medium ${
                    selectedDept === dept
                      ? 'bg-blue-50 text-blue-600 border border-blue-200'
                      : 'bg-white text-gray-600 border border-gray-200 hover:text-gray-900'
                  }`}
                >
                  {dept}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
          {activeTab === 'table' ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50 text-gray-500 text-[11px] font-semibold">
                    <th className="p-2.5 cursor-pointer hover:text-gray-800" onClick={() => handleSort('rollNumber')}>
                      <div className="flex items-center gap-1">Roll No <ArrowUpDown className="w-3 h-3" /></div>
                    </th>
                    <th className="p-2.5 cursor-pointer hover:text-gray-800" onClick={() => handleSort('name')}>
                      <div className="flex items-center gap-1">Name <ArrowUpDown className="w-3 h-3" /></div>
                    </th>
                    <th className="p-2.5 cursor-pointer hover:text-gray-800" onClick={() => handleSort('department')}>
                      <div className="flex items-center gap-1">Department <ArrowUpDown className="w-3 h-3" /></div>
                    </th>
                    <th className="p-2.5 cursor-pointer hover:text-gray-800" onClick={() => handleSort('cgpa')}>
                      <div className="flex items-center gap-1">CGPA <ArrowUpDown className="w-3 h-3" /></div>
                    </th>
                    <th className="p-2.5 cursor-pointer hover:text-gray-800" onClick={() => handleSort('attendance')}>
                      <div className="flex items-center gap-1">Attendance <ArrowUpDown className="w-3 h-3" /></div>
                    </th>
                    <th className="p-2.5 cursor-pointer hover:text-gray-800" onClick={() => handleSort('status')}>
                      <div className="flex items-center gap-1">Status <ArrowUpDown className="w-3 h-3" /></div>
                    </th>
                    <th className="p-2.5">Email</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filtered.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="p-8 text-center text-gray-400">
                        No students match the selected search or filter criteria.
                      </td>
                    </tr>
                  ) : (
                    filtered.map((s) => (
                      <tr key={s.id} className="hover:bg-gray-50/80 transition-colors">
                        <td className="p-2.5 font-semibold text-gray-800">{s.rollNumber}</td>
                        <td className="p-2.5 font-semibold text-gray-900">{s.name}</td>
                        <td className="p-2.5 text-gray-600">{s.department}</td>
                        <td className="p-2.5 font-semibold text-blue-600">{s.cgpa.toFixed(2)}</td>
                        <td className="p-2.5">
                          <span className={s.attendance < 75 ? 'text-red-600 font-semibold' : 'text-gray-700'}>
                            {s.attendance}%
                          </span>
                        </td>
                        <td className="p-2.5">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            s.status === 'Active' ? 'bg-blue-50 text-blue-600 border border-blue-200' :
                            s.status === 'Probation' ? 'bg-red-50 text-red-600 border border-red-200' :
                            'bg-gray-100 text-gray-700 border border-gray-200'
                          }`}>
                            {s.status}
                          </span>
                        </td>
                        <td className="p-2.5 text-gray-400 text-[11px]">{s.email}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <div className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
                  <Code className="w-4 h-4 text-blue-600" />
                  <span>Executed SQL Query</span>
                </div>
                <pre className="p-4 bg-gray-50 border border-gray-200 rounded-xl text-blue-600 text-xs font-mono overflow-x-auto leading-relaxed">
                  {sqlQuery || 'SELECT * FROM students ORDER BY cgpa DESC;'}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

