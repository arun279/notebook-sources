import React, { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import useStore from '../store';
import { getProgress, getReferences, scrapeReferences, API_ROOT, downloadZip } from '../services/api';
import ReferenceTable from '../components/ReferenceTable';
import ProgressModal from '../components/ProgressModal';

const ReferencesPage: React.FC = () => {
  const {
    parseJobId,
    selectedIds,
    clearSelection,
    setScrapeJobId,
    scrapeJobId,
  } = useStore();
  const navigate = useNavigate();

  useEffect(() => {
    if (!parseJobId) navigate('/');
  }, [parseJobId, navigate]);

  const progressQuery = useQuery({
    queryKey: ['progress', parseJobId],
    queryFn: () => getProgress(parseJobId!),
    enabled: !!parseJobId,
    refetchInterval: 1000,
  });

  const refsQuery = useQuery({
    queryKey: ['references', parseJobId],
    queryFn: () => getReferences(parseJobId!),
    enabled: !!parseJobId,
    refetchInterval: 1000,
  });

  if (!parseJobId) return null;

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

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-4">References</h2>
      {!refsQuery.data && (
        <ProgressModal percent={progressQuery.data?.percent ?? 0} />
      )}
      {refsQuery.data && (
        <div className="mb-2 flex items-center gap-2">
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
        </div>
      )}
      {refsQuery.data && <ReferenceTable references={refsQuery.data.references} />}
    </div>
  );
};

export default ReferencesPage; 