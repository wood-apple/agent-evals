import type { Comparison, Config, Experiment, ExperimentDetail, TaskInfo, TrialDetail } from './types';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.message ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  experiments: () => request<Experiment[]>('/experiments'),
  experiment: (id: string) => request<ExperimentDetail>(`/experiments/${id}`),
  compare: (id: string, a: string, b: string) =>
    request<Comparison>(`/experiments/${id}/compare?a=${a}&b=${b}`),
  log: (id: string) => request<{ log: string }>(`/experiments/${id}/log`),
  startExperiment: (body: unknown) =>
    request<{ experimentId: string }>('/experiments', { method: 'POST', body: JSON.stringify(body) }),
  configs: () => request<Config[]>('/configs'),
  createConfig: (body: unknown) => request<Config>('/configs', { method: 'POST', body: JSON.stringify(body) }),
  tasks: () => request<TaskInfo[]>('/tasks'),
  trial: (id: string) => request<TrialDetail>(`/trials/${id}`),
  judgeValidation: () => request<Record<string, unknown>>('/judge-validation'),
  exportUrl: (id: string, format: 'json' | 'csv') => `/api/experiments/${id}/export?format=${format}`,
};
