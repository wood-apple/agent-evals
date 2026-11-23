import { api } from '../api';
import { pct } from '../format';
import { useData } from '../useData';

interface Item {
  id: string;
  task_id: string;
  human_pass: boolean;
  judge_pass: boolean;
  judge_score: number;
  reasoning: string;
  response: string;
}

interface Report {
  judge_model: string;
  n: number;
  agreement: number;
  kappa: number;
  confusion: Record<string, number>;
  cost_usd: number;
  disagreements: Item[];
}

export function JudgePage() {
  const report = useData(() => api.judgeValidation() as unknown as Promise<Report>, []);
  const r = report.data;
  return (
    <>
      <h2>Judge validation</h2>
      <p className="muted">
        The LLM judge is scored against labelled examples (judge-validation/labelled.jsonl). Re-run with{' '}
        <code>evals judge-validate</code>.
      </p>
      {report.error && <p className="error">{report.error}</p>}
      {r && (
        <>
          <dl className="facts">
            <dt>Judge model</dt>
            <dd className="mono">{r.judge_model}</dd>
            <dt>Examples</dt>
            <dd>{r.n}</dd>
            <dt>Agreement</dt>
            <dd>{pct(r.agreement, 1)}</dd>
            <dt>Cohen's κ</dt>
            <dd>{r.kappa.toFixed(2)}</dd>
            <dt>Confusion</dt>
            <dd className="mono">{JSON.stringify(r.confusion)}</dd>
          </dl>
          <h3>Disagreements</h3>
          {r.disagreements.map((d) => (
            <details key={d.id} className="card">
              <summary>
                {d.id} ({d.task_id}): labelled {d.human_pass ? 'pass' : 'fail'}, judge {d.judge_score}/5
              </summary>
              <h4>Response</h4>
              <pre>{d.response}</pre>
              <h4>Judge reasoning</h4>
              <pre>{d.reasoning}</pre>
            </details>
          ))}
        </>
      )}
    </>
  );
}
