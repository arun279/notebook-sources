import React from 'react';
import { Reference } from '../services/api';
import useStore from '../store';
import { downloadPdf } from '../services/api';

interface Props {
  references: Reference[];
}

const ReferenceTable: React.FC<Props> = ({ references }) => {
  const { selectedIds, toggleSelection, clearSelection } = useStore();
  if (!references.length) {
    return <p>No references found.</p>;
  }
  return (
    <table className="min-w-full border border-gray-300 text-sm">
      <thead className="bg-gray-100 dark:bg-gray-800 dark:text-gray-100 sticky top-0 z-10">
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
          <th className="p-2 text-left">URL</th>
          <th className="p-2 text-left">Status</th>
        </tr>
      </thead>
      <tbody>
        {references.map(ref => {
          const isScraping = ref.status === 'scraping';
          const rowClass = isScraping ? 'animate-pulse bg-yellow-50 dark:bg-yellow-900' : '';
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
              <td className="p-2 max-w-xs truncate" title={ref.url}>
                <a href={ref.url} target="_blank" rel="noreferrer" className="text-primary underline">
                  {ref.url}
                </a>
              </td>
              <td className="p-2 capitalize">
                {ref.status}
                {ref.status === 'scraped' && (
                  <button
                    className="ml-2 text-primary hover:text-primary/80"
                    onClick={() => downloadPdf(ref.id)}
                    title="Download PDF"
                  >
                    ⬇️
                  </button>
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