import { describe, expect, it } from 'vitest';
import { pct, pp, tokens, trialOutcome, usd } from './format';

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
});
