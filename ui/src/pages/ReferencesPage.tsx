import React, { useEffect, useState, useMemo, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import useStore from '../store';
import { getProgress, getReferences, getReferencesByPage, scrapeReferences, API_ROOT, downloadZip } from '../services/api';
import ReferenceTable from '../components/ReferenceTable';
import ProgressModal from '../components/ProgressModal';

function getDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return '';
  }
}

const ReferencesPage: React.FC = () => {
  const {
    parseJobId,
    selectedIds,
    clearSelection,
    setScrapeJobId,
  } = useStore();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const pageId = params.get('page');

  const toolbarRef = useRef<HTMLDivElement>(null);

  // update CSS variable for toolbar height for sticky header offset
  useEffect(() => {
    function updateVar() {
      if (toolbarRef.current) {
        document.documentElement.style.setProperty('--nr-toolbar-h', `${toolbarRef.current.offsetHeight}px`);
      }
    }
    updateVar();
    window.addEventListener('resize', updateVar);
    return () => window.removeEventListener('resize', updateVar);
  }, []);

  useEffect(() => {
    if (!parseJobId && !pageId) navigate('/');
  }, [parseJobId, pageId, navigate]);

  const progressQuery = useQuery({
    queryKey: ['progress', parseJobId],
    queryFn: () => getProgress(parseJobId!),
    enabled: !!parseJobId,
    refetchInterval: 1000,
  });

  const refsQuery = useQuery({
    queryKey: ['references', parseJobId ?? pageId],
    queryFn: () => {
      if (pageId) return getReferencesByPage(pageId);
      return getReferences(parseJobId!);
    },
    enabled: !!parseJobId || !!pageId,
    refetchInterval: 1000,
  });

  // -----------------------------------------------------------------
  // Derived state: filter + scraped helpers
  // -----------------------------------------------------------------
  const [search, setSearch] = useState('');

  const filteredRefs = useMemo(() => {
    if (!refsQuery.data) return [];
    const q = search.toLowerCase();
    return refsQuery.data.references.filter(r => {
      if (!q) return true;
      return (
        r.title.toLowerCase().includes(q) ||
        r.url.toLowerCase().includes(q) ||
        getDomain(r.url).includes(q)
      );
    });
  }, [search, refsQuery.data]);

  const scrapedIds = useMemo(() => filteredRefs.filter(r => r.status === 'scraped').map(r => r.id), [filteredRefs]);

  const handleScrape = async () => {
    if (selectedIds.size === 0) return;
    try {
      const { job_id } = await scrapeReferences(Array.from(selectedIds), false);
      setScrapeJobId(job_id);
      clearSelection();
      // open websocket
      const ws = new WebSocket(`${API_ROOT.replace('http', 'ws')}/api/v1/ws/progress/${job_id}`);
      ws.onmessage = evt => {
        const msg = JSON.parse(evt.data);
        if (msg.event === 'reference_done') {
          refsQuery.refetch();
        }
        if (msg.event === 'job_complete') {
          ws.close();
        }
      };
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error(e);
    }
  };

  const handleDownloadScraped = () => {
    if (scrapedIds.length === 0) return;
    downloadZip(scrapedIds);
  };

  if (!parseJobId && !pageId) return null;

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-4">References</h2>
      {!refsQuery.data && (
        <ProgressModal percent={progressQuery.data?.percent ?? 0} />
      )}
      {refsQuery.data && (
        <div
          ref={toolbarRef}
          className="mb-2 flex flex-wrap items-center gap-2 sticky top-0 bg-gray-50 dark:bg-gray-900 py-2 z-20 shadow-sm"
        >
          <input
            type="text"
            placeholder="Search title, domain, url…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="px-2 py-1 border rounded-md dark:bg-gray-700 dark:border-gray-600"
          />
          <button
            className="px-3 py-1 bg-accent text-white rounded disabled:opacity-50"
            disabled={selectedIds.size === 0}
            onClick={handleScrape}
          >
            Scrape Selected ({selectedIds.size})
          </button>
          <button
            className="px-3 py-1 bg-primary text-white rounded disabled:opacity-50"
            disabled={selectedIds.size === 0}
            onClick={() => downloadZip(Array.from(selectedIds))}
          >
            Download ZIP
          </button>
          <button
            className="px-3 py-1 bg-primary/80 text-white rounded disabled:opacity-50"
            disabled={scrapedIds.length === 0}
            onClick={handleDownloadScraped}
            title="Download all scraped PDFs currently in view"
          >
            Download Scraped ({scrapedIds.length})
          </button>
        </div>
      )}
      {refsQuery.data && <ReferenceTable references={filteredRefs} />}
    </div>
  );
};

export default ReferencesPage; 