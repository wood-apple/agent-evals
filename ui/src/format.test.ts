import { describe, expect, it } from 'vitest';
import { duration, pct, pp, runDuration, tokens, trialOutcome, usd } from './format';

describe('format', () => {
  it('formats rates and deltas', () => {
    expect(pct(0.756, 1)).toBe('75.6%');
    expect(pct(null)).toBe('—');
    expect(pp(0.123)).toBe('+12.3 pp');
    expect(pp(-0.05)).toBe('-5.0 pp');
  });

  it('keeps small costs readable', () => {
    expect(usd(0.0004)).toBe('$0.0004');
    expect(usd(1.234)).toBe('$1.23');
  });

  it('abbreviates token counts', () => {
    expect(tokens(950)).toBe('950');
    expect(tokens(21663)).toBe('21.7k');
  });

  it('treats infrastructure errors separately from failures', () => {
    expect(trialOutcome({ status: 'error', passed: null })).toBe('error');
    expect(trialOutcome({ status: 'timeout', passed: false })).toBe('fail');
    expect(trialOutcome({ status: 'ok', passed: true })).toBe('pass');
  });

  it('formats experiment durations', () => {
    expect(duration(42_000)).toBe('42s');
    expect(duration(754_000)).toBe('12m 34s');
    expect(duration(3_900_000)).toBe('1h 5m');
    const base = { created_at: '2026-11-23T01:00:00Z', running: false, status: 'done' };
    expect(runDuration({ ...base, last_finished_at: '2026-11-23T01:31:10Z' })).toBe('31m 10s');
    expect(runDuration({ ...base, running: true }, Date.parse('2026-11-23T01:05:00Z'))).toBe('5m 0s so far');
  });
});
