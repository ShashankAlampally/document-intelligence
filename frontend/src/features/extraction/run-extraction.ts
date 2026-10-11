import type { Reply } from '../../lib/api';

type Job = {
  id: string;
  status: 'running' | 'waiting' | 'paused' | 'completed';
  detail: string;
  completed_fields: number;
  fields: Record<string, { value: string | null; notes?: string | null }>;
  reply?: Reply;
};

async function request(path: string, body?: unknown): Promise<Job> {
  const response = await fetch(path, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw Object.assign(
    new Error(result.detail || 'Unable to load extraction job.'), { status: response.status },
  );
  return result;
}

export async function runExtraction(discoveryId: string, onProgress: (job: Job) => void): Promise<Reply> {
  const key = `extraction-job:${discoveryId}`;
  const saved = localStorage.getItem(key);
  let job: Job;
  if (saved) {
    try {
      job = await request(`/api/sessions/extractions/${encodeURIComponent(saved)}/resume`, {});
    } catch (error) {
      const status = (error as { status?: number }).status;
      if (status === 404 || status === 409) localStorage.removeItem(key);
      throw error;
    }
  } else {
    job = await request('/api/sessions/extractions', {
      discovery_ids: [discoveryId], question: 'Extract all 20 fields with citations.',
    });
    localStorage.setItem(key, job.id);
  }
  while (true) {
    onProgress(job);
    if (job.status === 'paused') throw new Error(`${job.detail} Click Extract fields to resume.`);
    if (job.status === 'completed') {
      if (!job.reply) throw new Error('Completed job has no answer.');
      localStorage.removeItem(key);
      return job.reply;
    }
    await new Promise(resolve => setTimeout(resolve, 2000));
    job = await request(`/api/sessions/extractions/${encodeURIComponent(job.id)}`);
  }
}
