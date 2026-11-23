import { useEffect, useState } from 'react';
import { api } from '../api';
import { CiBar } from '../components/CiBar';
import { TrialGrid } from '../components/TrialGrid';
import { configName, pct, pp, runDuration, seconds, tokens, usd } from '../format';
import { useData } from '../useData';
import type { Comparison, Config, ConfigSummary } from '../types';

export function ExperimentPage({ id }: { id: string }) {
  const experiment = useData(() => api.experiment(id), [id], 5000);
  const e = experiment.data;
  const [a, setA] = useState<string>();
  const [b, setB] = useState<string>();

  useEffect(() => {
    if (e && !a) {
      setA(e.config_ids[0]);
      setB(e.config_ids[1] ?? e.config_ids[0]);
    }
  }, [e, a]);

  if (experiment.error) return <p className="error">{experiment.error}</p>;
  if (!e) return <p className="muted">Loading…</p>;
  const finished = e.trials.length;

  return (
    <>
      <h2>{e.name}</h2>
      <p className="muted mono">
        {e.id} · {e.task_ids.length} tasks × {e.config_ids.length} configs × {e.n_trials} trials ·{' '}
        <span className={`badge status-${e.running ? 'running' : e.status}`}>{e.running ? 'running' : e.status}</span> ·{' '}
        {finished} / {e.planned} done · ran {runDuration(e)} · <a href={api.exportUrl(id, 'json')}>export JSON</a> ·{' '}
        <a href={api.exportUrl(id, 'csv')}>export CSV</a>
      </p>
      <progress value={finished} max={e.planned} className="wide" />

      {e.config_ids.length > 1 && a && b && (
        <section className="card">
          <div className="row">
            <ConfigPicker label="A (baseline)" configs={e.configs} value={a} onChange={setA} />
            <ConfigPicker label="B (candidate)" configs={e.configs} value={b} onChange={setB} />
          </div>
          <ComparisonView experimentId={id} a={a} b={b} configs={e.configs} refreshKey={finished} />
        </section>
      )}

      <section className="card">
        <h3>Trials</h3>
        <p className="muted">✓ passed · ✗ failed (counts against the config) · ! infrastructure error (excluded and retried on resume). Click a trial to see its trajectory.</p>
        <TrialGrid taskIds={e.task_ids} configs={e.configs} trials={e.trials} />
      </section>
      {e.running && <RunLog id={id} />}
    </>
  );
}

function ConfigPicker(props: { label: string; configs: Config[]; value: string; onChange: (id: string) => void }) {
  return (
    <label>
      {props.label}
      <select value={props.value} onChange={(e) => props.onChange(e.target.value)}>
        {props.configs.map((c) => (
          <option key={c.id} value={c.id}>
            {configName(c)}
          </option>
        ))}
      </select>
    </label>
  );
}

function ComparisonView(props: { experimentId: string; a: string; b: string; configs: Config[]; refreshKey: number }) {
  const { experimentId, a, b, refreshKey } = props;
  const comparison = useData(() => api.compare(experimentId, a, b), [experimentId, a, b, refreshKey]);
  const c = comparison.data;
  if (comparison.error) return <p className="error">{comparison.error}</p>;
  if (!c) return <p className="muted">Computing…</p>;
  const name = (id: string) => configName(props.configs.find((x) => x.id === id));
  return (
    <>
      <Verdict comparison={c} />
      <table>
        <thead>
          <tr>
            <th />
            <th>Pass rate</th>
            <th>Mean score</th>
            <th>Cost / trial</th>
            <th>Total cost</th>
            <th>Latency</th>
            <th>Tokens in / out</th>
            <th>Infra errors</th>
          </tr>
        </thead>
        <tbody>
          <SummaryRow label={`A · ${name(c.config_a)}`} s={c.a} />
          <SummaryRow label={`B · ${name(c.config_b)}`} s={c.b} />
        </tbody>
      </table>
      <FailureTable a={c.a} b={c.b} />
      <h4>Per-task deltas</h4>
      <p className="muted">Fisher exact test per task. With few trials a single task rarely reaches significance, and testing many tasks at once will throw up some false positives.</p>
      <table>
        <thead>
          <tr>
            <th>Task</th>
            <th>A</th>
            <th>B</th>
            <th>Δ</th>
            <th>p</th>
            <th>Reading</th>
          </tr>
        </thead>
        <tbody>
          {c.per_task.map((row) => (
            <tr key={row.task_id} className={row.signal === 'likely real' ? 'highlight' : ''}>
              <td className="mono">{row.task_id}</td>
              <td>{pct(row.pass_rate_a)}</td>
              <td>{pct(row.pass_rate_b)}</td>
              <td className={row.delta > 0 ? 'good' : row.delta < 0 ? 'bad' : ''}>{pp(row.delta)}</td>
              <td>{row.p_value.toFixed(2)}</td>
              <td className="muted">{row.signal}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Verdict({ comparison: c }: { comparison: Comparison }) {
  if (c.delta === undefined || !c.ci95 || !c.mcnemar) return <p className="verdict">{c.verdict}</p>;
  const [low, high] = c.ci95;
  return (
    <div className="verdict-box">
      <div>
        <p className="verdict">{c.verdict}</p>
        <p>
          Pass rate B − A: <strong>{pp(c.delta)}</strong>, 95% CI [{pp(low)}, {pp(high)}] (paired bootstrap over {c.tasks} tasks,{' '}
          {c.pairs} trial pairs)
        </p>
        <p className="muted">
          McNemar on paired trials: {c.mcnemar.only_a_passed} pairs only A passed, {c.mcnemar.only_b_passed} only B passed, p ={' '}
          {c.mcnemar.p_value.toFixed(3)}. With this many tasks and trials, differences smaller than about ±
          {((c.detectable_delta ?? 0) * 100).toFixed(0)} pp can't be told apart from noise.
        </p>
      </div>
      <CiBar delta={c.delta} low={low} high={high} />
    </div>
  );
}

function SummaryRow({ label, s }: { label: string; s: ConfigSummary }) {
  return (
    <tr>
      <th>{label}</th>
      <td>{pct(s.pass_rate, 1)}</td>
      <td>{s.mean_score?.toFixed(2) ?? '—'}</td>
      <td>{usd(s.mean_cost_usd)}</td>
      <td>{usd(s.total_cost_usd)}</td>
      <td>{seconds(s.mean_latency_ms)}</td>
      <td>
        {tokens(s.mean_input_tokens)} / {tokens(s.mean_output_tokens)}
      </td>
      <td>{s.errors}</td>
    </tr>
  );
}

function FailureTable({ a, b }: { a: ConfigSummary; b: ConfigSummary }) {
  const categories = [...new Set([...Object.keys(a.failure_categories), ...Object.keys(b.failure_categories)])].sort();
  if (categories.length === 0) return null;
  return (
    <>
      <h4>Why trials failed</h4>
      <table className="compact">
        <thead>
          <tr>
            <th>Category</th>
            <th>A</th>
            <th>B</th>
          </tr>
        </thead>
        <tbody>
          {categories.map((category) => (
            <tr key={category}>
              <td>{category.replaceAll('_', ' ')}</td>
              <td>{a.failure_categories[category] ?? 0}</td>
              <td>{b.failure_categories[category] ?? 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function RunLog({ id }: { id: string }) {
  const log = useData(() => api.log(id), [id], 5000);
  if (!log.data?.log) return null;
  return (
    <details className="card">
      <summary>Worker log</summary>
      <pre>{log.data.log}</pre>
    </details>
  );
}
