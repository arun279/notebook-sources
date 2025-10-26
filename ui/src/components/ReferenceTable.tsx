import React from 'react';
import { Reference } from '../services/api';
import useStore from '../store';
import { downloadPdf } from '../services/api';

interface Props {
  references: Reference[];
  onReset: (id: string) => void;
}

function getDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return '';
  }
}

const ReferenceTable: React.FC<Props> = ({ references, onReset }) => {
  const { selectedIds, toggleSelection, clearSelection } = useStore();
  if (!references.length) {
    return <p>No references found.</p>;
  }
  return (
    <table className="min-w-full border border-gray-300 text-sm">
      <thead
        className="bg-gray-100 dark:bg-gray-800 dark:text-gray-100 sticky z-10"
        style={{ top: 'var(--nr-toolbar-h, 56px)' }}
      >
        <tr>
          <th className="p-2 w-8">
            <input
              type="checkbox"
              checked={selectedIds.size === references.length}
              onChange={() => {
                if (selectedIds.size === references.length) {
                  clearSelection();
                } else {
                  references.forEach(r => toggleSelection(r.id));
                }
              }}
            />
          </th>
          <th className="p-2 text-left">Title</th>
          <th className="p-2 text-left">Domain</th>
          <th className="p-2 text-left">URL</th>
          <th className="p-2 text-left">Status</th>
        </tr>
      </thead>
      <tbody>
        {references.map(ref => {
          const isScraping = ref.status === 'scraping';
          const isSelected = selectedIds.has(ref.id);
          const rowClass = isScraping
            ? 'animate-pulse bg-yellow-50 dark:bg-yellow-900'
            : isSelected
            ? 'bg-blue-50 dark:bg-blue-900/50'
            : '';
          return (
            <tr key={ref.id} className={`border-t ${rowClass}`}>
              <td className="p-2 w-8 text-center">
                <input
                  type="checkbox"
                  checked={selectedIds.has(ref.id)}
                  onChange={() => toggleSelection(ref.id)}
                />
              </td>
              <td className="p-2 max-w-xs truncate" title={ref.title}>{ref.title}</td>
              <td className="p-2 max-w-xs truncate" title={getDomain(ref.url)}>{getDomain(ref.url)}</td>
              <td className="p-2 max-w-xs truncate" title={ref.url}>
                <a href={ref.url} target="_blank" rel="noreferrer" className="text-primary underline">
                  {ref.url}
                </a>
              </td>
              <td className="p-2 capitalize">
                {ref.status}
                {ref.status === 'scraped' && (
                  <>
                    <button
                      className="ml-2 text-primary hover:text-primary/80"
                      onClick={() => downloadPdf(ref.id)}
                      title="Download PDF"
                    >
                      ⬇️
                    </button>
                    <button
                      className="ml-2 text-primary hover:text-primary/80"
                      onClick={() => onReset(ref.id)}
                      title="Reset"
                    >
                      🔄
                    </button>
                  </>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
};

export default ReferenceTable;