import { create } from 'zustand';

interface State {
  parseJobId?: string;
  setParseJobId: (jobId: string) => void;
  selectedIds: Set<string>;
  toggleSelection: (id: string) => void;
  clearSelection: () => void;
  scrapeJobId?: string;
  setScrapeJobId: (jobId: string | undefined) => void;
}

const useStore = create<State>(set => ({
  parseJobId: undefined,
  setParseJobId: jobId => set({ parseJobId: jobId }),
  selectedIds: new Set(),
  toggleSelection: id =>
    set(state => {
      const next = new Set(state.selectedIds);
      next.has(id) ? next.delete(id) : next.add(id);
      return { selectedIds: next };
    }),
  clearSelection: () => set({ selectedIds: new Set() }),
  scrapeJobId: undefined,
  setScrapeJobId: jobId => set({ scrapeJobId: jobId }),
}));

export default useStore; 