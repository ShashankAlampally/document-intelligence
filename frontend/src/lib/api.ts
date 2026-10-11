export type Citation = { file: string; folder_name?: string | null; discovery_id?: string | null; page?: number | null; section?: string | null; chunk_id?: string | null; table_id?: string | null; table_complete?: boolean | null; similarity?: number | null; retrieval_score?: number | null; rerank_score?: number | null; keyword_score?: number | null; text: string };
export type Reply = { answer: string; sources: Citation[] };
export type ProcessingJob = { id: string; status: 'processing' | 'ready' | 'failed'; session_id?: string; discovery_id?: string; detail?: string };

// Connected HTTP routes use the core adapter installed by FastAPI.
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    if (response.status === 501) throw new Error('The API routes are ready, but document processing is not connected yet. Your selected documents are kept in this chat.');
    const error = await response.json().catch(() => null);
    if (typeof error?.detail === 'string') throw new Error(error.detail);
    throw new Error(`Request failed (${response.status}). Please try again.`);
  }
  return response.json() as Promise<T>;
}
export async function uploadFolder(files: File[]): Promise<ProcessingJob> {
  const body = new FormData();
  files.forEach(file => body.append('files', file, file.webkitRelativePath || file.name));
  return request('/api/sessions', { method: 'POST', body });
}
export const getProcessingJob = (id: string) => request<ProcessingJob>(`/api/jobs/${encodeURIComponent(id)}`);
export async function queryDocuments(discoveryIds: string[], question: string, mode: 'ask' | 'search'): Promise<Reply> {
  return request(`/api/sessions/${mode}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, discovery_ids: discoveryIds }),
  });
}

export type IndexedFolder = {
  discovery_id: string;
  folder_name: string;
  stored_chunks: number;
  files: { relative_path: string; issues: unknown[] }[];
};
export const getIndexedFolder = (id: string) =>
  request<IndexedFolder>(`/api/sessions/${encodeURIComponent(id)}`);
