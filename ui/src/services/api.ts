export interface Reference {
  id: string;
  title: string;
  url: string;
  status: string;
  suspected_paywall?: boolean;
}

export const API_ROOT = import.meta.env.VITE_API_ROOT || 'http://localhost:8000';

export interface PageSummary {
  id: string;
  url: string;
  title?: string | null;
  total_refs: number;
  scraped_refs: number;
  percent_scraped: number;
  refreshing: boolean;
}

async function jsonFetch<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const res = await fetch(input, init);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function parseReferences(url: string) {
  return jsonFetch<{ job_id: string }>(`${API_ROOT}/api/v1/references`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
}

export async function getProgress(jobId: string) {
  return jsonFetch<{ percent: number }>(`${API_ROOT}/api/v1/progress/${jobId}`);
}

export async function getReferences(jobId: string) {
  try {
    return await jsonFetch<{ references: Reference[] }>(`${API_ROOT}/api/v1/references/${jobId}`);
  } catch (err: any) {
    if (err instanceof Error && /404/.test(err.message)) {
      return null; // not ready yet
    }
    throw err;
  }
}

export async function scrapeReferences(referenceIds: string[], aggressive: boolean = false) {
  return jsonFetch<{ job_id: string }>(`${API_ROOT}/api/v1/scrape`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reference_ids: referenceIds, aggressive }),
  });
}

export function downloadZipAll() {
  window.location.href = `${API_ROOT}/api/v1/download?all=true`;
}

export function downloadZip(ids: string[]) {
  if (ids.length === 0) return;
  window.location.href = `${API_ROOT}/api/v1/download?ids=${ids.join(',')}`;
}

export function downloadPdf(id: string) {
  window.location.href = `${API_ROOT}/api/v1/download?ids=${id}`;
}

export async function listPages() {
  return jsonFetch<PageSummary[]>(`${API_ROOT}/api/v1/pages`);
}

export async function getReferencesByPage(pageId: string) {
  return jsonFetch<{ references: Reference[] }>(`${API_ROOT}/api/v1/pages/${pageId}/references`);
}

export async function deletePage(pageId: string) {
  return fetch(`${API_ROOT}/api/v1/pages/${pageId}`, { method: 'DELETE' });
}

export async function renamePage(pageId: string, title: string) {
  return jsonFetch<PageSummary>(`${API_ROOT}/api/v1/pages/${pageId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
}

export async function refreshPage(pageId: string) {
  return fetch(`${API_ROOT}/api/v1/pages/${pageId}/refresh`, { method: 'POST' });
}

export function downloadPageZip(pageId: string) {
  window.location.href = `${API_ROOT}/api/v1/pages/${pageId}/download`;
} 