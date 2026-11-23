import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { Config, Trial } from '../types';
import { TrialGrid } from './TrialGrid';

const config = (id: string, label: string): Config => ({ id, label, harness: 'baseline', model: 'm', settings: {} });

const trial = (task: string, configId: string, index: number, status: Trial['status'], passed: boolean | null): Trial => ({
  id: `${task}-${configId}-${index}`,
  experiment_id: 'e',
  task_id: task,
  task_version: 'v',
  config_id: configId,
  trial_index: index,
  status,
  passed,
  score: null,
  input_tokens: 0,
  output_tokens: 0,
  cost_usd: 0,
  latency_ms: 0,
  error: null,
  failure_category: passed === false ? 'wrong_answer' : null,
  finished_at: '',
});

describe('TrialGrid', () => {
  it('shows one linked marker per trial in task order', () => {
    render(
      <TrialGrid
        taskIds={['t1']}
        configs={[config('A', 'model a'), config('B', 'model b')]}
        trials={[trial('t1', 'A', 1, 'ok', false), trial('t1', 'A', 0, 'ok', true), trial('t1', 'B', 0, 'error', null)]}
      />,
    );
    expect(screen.getByText('model a')).toBeTruthy();
    const links = screen.getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual(['✓', '✗', '!']);
    expect(links[1].getAttribute('href')).toBe('#/trial/t1-A-1');
    expect(links[1].getAttribute('title')).toBe('trial 1: fail (wrong_answer)');
  });
});
