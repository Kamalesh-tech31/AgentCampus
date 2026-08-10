import React from 'react';
import { X, Code2, Copy, Check } from 'lucide-react';

interface JsonViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  jsonData: any;
}

export const JsonViewerModal: React.FC<JsonViewerModalProps> = ({
  isOpen,
  onClose,
  title,
  jsonData
}) => {
  const [copied, setCopied] = React.useState(false);

  if (!isOpen) return null;

  const jsonString = JSON.stringify(jsonData, null, 2);

  const handleCopy = () => {
    navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 bg-gray-900/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white border border-gray-200 rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-xl overflow-hidden font-sans">
        <div className="p-4 bg-white border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Code2 className="w-4 h-4 text-blue-600" />
            <h3 className="text-xs font-semibold text-gray-900">{title}</h3>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-2.5 py-1 bg-gray-100 hover:bg-gray-200 text-xs font-medium text-gray-700 rounded-lg border border-gray-200 transition-all cursor-pointer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-blue-600" /> : <Copy className="w-3.5 h-3.5 text-gray-500" />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>

            <button
              onClick={onClose}
              className="p-1 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 p-4 overflow-y-auto bg-gray-50 custom-scrollbar">
          <pre className="text-xs text-blue-600 leading-relaxed overflow-x-auto font-mono">
            {jsonString}
          </pre>
        </div>
      </div>
    </div>
  );
};

