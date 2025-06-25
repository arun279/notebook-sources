export interface Reference {
  id: string;
  title: string;
  url: string;
  status: string;
  suspected_paywall?: boolean;
}

export const API_ROOT = import.meta.env.VITE_API_ROOT || 'http://localhost:8000';

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