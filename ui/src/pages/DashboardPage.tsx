import React, { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { listPages, PageSummary, parseReferences, deletePage, renamePage, refreshPage, downloadPageZip } from '../services/api';
import { Link, useNavigate } from 'react-router-dom';
import useStore from '../store';

const DashboardPage: React.FC = () => {
  const { setParseJobId } = useStore();
  const navigate = useNavigate();
  const [url, setUrl] = useState('');

  const pagesQuery = useQuery({
    queryKey: ['pages'],
    queryFn: listPages,
    refetchInterval: 5000,
  });

  const parseMut = useMutation({
    mutationFn: parseReferences,
    onSuccess: data => {
      setParseJobId(data.job_id);
      navigate('/references');
    },
  });

  const deleteMut = useMutation({
    mutationFn: deletePage,
    onSuccess: () => pagesQuery.refetch(),
  });

  const renameMut = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => renamePage(id, title),
    onSuccess: () => pagesQuery.refetch(),
  });

  const refreshMut = useMutation({
    mutationFn: refreshPage,
    onSuccess: () => pagesQuery.refetch(),
  });

  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState('');

  /**
   * Tracks the ids of pages that are currently being refreshed so that we can
   * apply the row-level pulse animation.  We also need to know the counts that
   * were returned *before* the refresh call was issued.
   */
  const [refreshingIds, setRefreshing] = useState<Set<string>>(new Set());
  const refreshBaselines = React.useRef<Record<string, { total: number; scraped: number }>>({});

  const addPage = (e: React.FormEvent) => {
    e.preventDefault();
    if (url) parseMut.mutate(url);
  };

  /* ---------------------------------------------------------------------------
   * Keep the pulse animation until the background parse job updates the page
   * entry.  We consider the refresh completed when either the *total_refs* or
   * *scraped_refs* figure differs from what we had right before the refresh
   * call was issued.
   * ------------------------------------------------------------------------- */
  useEffect(() => {
    if (!pagesQuery.data) return;

    setRefreshing(prev => {
      const next = new Set(prev);
      pagesQuery.data.forEach(p => {
        if (next.has(p.id)) {
          const baseline = refreshBaselines.current[p.id];
          // Unknown baseline → keep the pulse (should not happen)
          if (!baseline) return;

          const changed =
            p.total_refs !== baseline.total || p.scraped_refs !== baseline.scraped;
          if (changed) {
            next.delete(p.id);
            delete refreshBaselines.current[p.id];
          }
        }
      });
      return next;
    });
  }, [pagesQuery.data]);

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-4">Wikipedia Pages</h2>
      <form onSubmit={addPage} className="flex gap-2 mb-4 max-w-xl">
        <input
          type="url"
          required
          value={url}
          onChange={e => setUrl(e.target.value)}
          placeholder="https://en.wikipedia.org/wiki/LLM"
          className="flex-1 p-2 border rounded dark:bg-gray-700 dark:text-gray-100 dark:border-gray-600"
        />
        <button className="px-3 py-2 bg-primary text-white rounded" disabled={parseMut.isLoading}>
          {parseMut.isLoading ? 'Parsing…' : 'Add'}
        </button>
      </form>

      {pagesQuery.isLoading && <p>Loading…</p>}
      {pagesQuery.data && (
        <table className="min-w-full border text-sm">
          <thead className="bg-gray-100 dark:bg-gray-800 dark:text-gray-100 sticky top-0">
            <tr>
              <th className="p-2 text-left">Title</th>
              <th className="p-2 text-left">URL</th>
              <th className="p-2 text-left">Refs</th>
              <th className="p-2 text-left">Scraped</th>
              <th className="p-2 text-left">%</th>
              <th className="p-2 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {pagesQuery.data.map(p => {
              const isRefreshing = refreshingIds.has(p.id);
              const rowCls = isRefreshing ? 'animate-pulse bg-blue-50 dark:bg-blue-900' : '';
              return (
                <tr key={p.id} className={`border-t ${rowCls}`}>
                  <td className="p-2 max-w-xs truncate" title={p.title ?? p.url}>
                    {editingId === p.id ? (
                      <input
                        className="border p-1 text-sm dark:bg-gray-700 dark:text-gray-100"
                        value={draftTitle}
                        autoFocus
                        onChange={e => setDraftTitle(e.target.value)}
                        onBlur={() => {
                          if (draftTitle.trim()) renameMut.mutate({ id: p.id, title: draftTitle.trim() });
                          setEditingId(null);
                        }}
                        onKeyDown={e => {
                          if (e.key === 'Enter') {
                            (e.target as HTMLInputElement).blur();
                          }
                        }}
                      />
                    ) : (
                      <Link to={`/references?page=${p.id}`} className="text-primary underline">
                        {p.title || 'Untitled'}
                      </Link>
                    )}
                  </td>
                  <td className="p-2 max-w-xs truncate" title={p.url}> {p.url}</td>
                  <td className="p-2">{p.total_refs}</td>
                  <td className="p-2">{p.scraped_refs}</td>
                  <td className="p-2">{p.percent_scraped.toFixed(0)}%</td>
                  <td className="p-2 space-x-2">
                    <button
                      title="Refresh"
                      disabled={isRefreshing}
                      className={isRefreshing ? 'opacity-50 cursor-not-allowed' : ''}
                      onClick={() => {
                        // Record baseline counts so we know when something has
                        // actually changed.
                        refreshBaselines.current[p.id] = {
                          total: p.total_refs,
                          scraped: p.scraped_refs,
                        };

                        setRefreshing(prev => new Set(prev).add(p.id));
                        refreshMut.mutate(p.id);
                      }}
                    >
                      {isRefreshing ? '⏳' : '🔄'}
                    </button>
                    <button title="Rename" onClick={() => {
                      setDraftTitle(p.title || '');
                      setEditingId(p.id);
                    }}>✏️</button>
                    <button
                      title="Download ZIP"
                      disabled={p.scraped_refs === 0}
                      className={p.scraped_refs === 0 ? 'opacity-40 cursor-not-allowed' : ''}
                      onClick={() => p.scraped_refs !== 0 && downloadPageZip(p.id)}
                    >📦</button>
                    <button title="Delete" onClick={() => {
                      if (confirm('Delete page and its references?')) deleteMut.mutate(p.id);
                    }}>🗑️</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default DashboardPage; 