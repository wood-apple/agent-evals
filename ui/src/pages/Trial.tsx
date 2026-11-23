import { api } from '../api';
import { Timeline } from '../components/Timeline';
import { configName, seconds, tokens, trialOutcome, usd } from '../format';
import { href } from '../router';
import { useData } from '../useData';

export function TrialPage({ id }: { id: string }) {
  const trial = useData(() => api.trial(id), [id]);
  const t = trial.data;
  if (trial.error) return <p className="error">{trial.error}</p>;
  if (!t) return <p className="muted">Loading…</p>;
  const outcome = trialOutcome(t);
  const skills = t.events.filter((e) => e.type === 'skill_load').map((e) => String(e.name));
  const toolCalls = t.events.filter((e) => e.type === 'tool_result').length;
  return (
    <>
      <p>
        <a href={href('experiment', t.experiment_id)}>← experiment</a>
      </p>
      <h2>
        <span className={`badge ${outcome}`}>{outcome}</span> {t.task_id} · trial {t.trial_index}
      </h2>
      <dl className="facts">
        <dt>Config</dt>
        <dd>
          {configName(t.config)} <span className="muted mono">{t.config.harness} · {t.config.model}</span>
        </dd>
        <dt>Settings</dt>
        <dd className="mono">{JSON.stringify(t.config.settings)}</dd>
        <dt>Status</dt>
        <dd>
          {t.status}
          {t.failure_category && <span className="badge bad">{t.failure_category.replaceAll('_', ' ')}</span>}
        </dd>
        <dt>Score</dt>
        <dd>{t.score?.toFixed(2) ?? '—'}</dd>
        <dt>Usage</dt>
        <dd>
          {tokens(t.input_tokens)} in / {tokens(t.output_tokens)} out · {usd(t.cost_usd)} · {seconds(t.latency_ms)} · {toolCalls} tool calls
        </dd>
        <dt>Skills used</dt>
        <dd>{skills.length ? skills.join(', ') : 'none'}</dd>
        <dt>Task version</dt>
        <dd className="mono">{t.task_version}</dd>
        {t.error && (
          <>
            <dt>Error</dt>
            <dd className="error">{t.error}</dd>
          </>
        )}
      </dl>
      <section className="card">
        <h3>Grades</h3>
        {t.grades.length === 0 && <p className="muted">Not graded ({t.status}).</p>}
        {t.grades.map((g, i) => (
          <div key={i} className={`grade ${g.passed ? 'pass' : 'fail'}`}>
            <strong>
              {g.passed ? '✓' : '✗'} {g.grader}
            </strong>{' '}
            score {g.score.toFixed(2)} {!g.required && <span className="badge">advisory</span>}
            <pre>{g.reasoning}</pre>
          </div>
        ))}
      </section>
      <section className="card">
        <h3>Trajectory</h3>
        <Timeline events={t.events} />
      </section>
    </>
  );
}
