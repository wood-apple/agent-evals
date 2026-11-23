export function pct(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(digits)}%`;
}

export function pp(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  const points = value * 100;
  return `${points > 0 ? '+' : ''}${points.toFixed(1)} pp`;
}

export function usd(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return value < 0.01 ? `$${value.toFixed(4)}` : `$${value.toFixed(2)}`;
}

export function seconds(ms: number | null | undefined): string {
  return ms === null || ms === undefined ? '—' : `${(ms / 1000).toFixed(1)}s`;
}

export function tokens(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return value >= 1000 ? `${(value / 1000).toFixed(1)}k` : String(Math.round(value));
}

export function configName(config: { label: string; id: string } | undefined): string {
  if (!config) return '?';
  return config.label || config.id;
}

export function trialOutcome(trial: { status: string; passed: boolean | null }): 'pass' | 'fail' | 'error' {
  if (trial.status === 'error') return 'error';
  return trial.passed ? 'pass' : 'fail';
}
