import { useState } from 'react';
import { api } from '../api';
import { configName, runDuration, usd } from '../format';
import { href } from '../router';
import { useData } from '../useData';

export function ExperimentsPage() {
  const experiments = useData(api.experiments, [], 5000);
  const [status, setStatus] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const [archiveError, setArchiveError] = useState<string>();
  const statusOf = (e: { running: boolean; status: string }) => (e.running ? 'running' : e.status);
  const statuses = [...new Set((experiments.data ?? []).map(statusOf))].sort();
  const shown = (experiments.data ?? []).filter(
    (e) => (!status || statusOf(e) === status) && (showArchived || !e.archived),
  );
  const toggleArchived = (id: string, archived: boolean) =>
    api
      .archive(id, archived)
      .then(experiments.reload)
      .catch((e: Error) => setArchiveError(e.message));
  return (
    <>
      <h2>Experiments</h2>
      {experiments.error && <p className="error">{experiments.error}</p>}
      <label>
        Status{' '}
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">all</option>
          {statuses.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </label>{' '}
      <label className="check">
        <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} /> Show archived
      </label>
      {archiveError && <p className="error">{archiveError}</p>}
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Progress</th>
            <th>Errors</th>
            <th>Agent cost</th>
            <th>Duration</th>
            <th>Created</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {shown.map((e) => (
            <tr key={e.id} className={e.archived ? 'muted' : undefined}>
              <td>
                <a href={href('experiment', e.id)}>{e.name}</a>
                <div className="muted mono">{e.id}</div>
              </td>
              <td>
                <span className={`badge status-${statusOf(e)}`}>{statusOf(e)}</span>
              </td>
              <td>
                {e.finished} / {e.planned}
                <progress value={e.finished} max={e.planned} />
              </td>
              <td>{e.errors}</td>
              <td>{usd(e.cost_usd)}</td>
              <td>{runDuration(e)}</td>
              <td className="muted">{new Date(e.created_at).toLocaleString()}</td>
              <td>
                <button type="button" className="link" onClick={() => toggleArchived(e.id, !e.archived)}>
                  {e.archived ? 'Unarchive' : 'Archive'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {experiments.data?.length === 0 && <p className="muted">No experiments yet.</p>}
      <NewExperimentForm />
    </>
  );
}

function NewExperimentForm() {
  const configs = useData(api.configs, []);
  const tasks = useData(api.tasks, []);
  const [name, setName] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [category, setCategory] = useState('');
  const [trials, setTrials] = useState(3);
  const [budget, setBudget] = useState(2);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const categories = [...new Set((tasks.data ?? []).map((t) => t.category))].sort();
  const taskCount = (tasks.data ?? []).filter((t) => !category || t.category === category).length;

  const toggle = (id: string) =>
    setSelected((current) => (current.includes(id) ? current.filter((c) => c !== id) : [...current, id]));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      const { experimentId } = await api.startExperiment({
        name,
        configIds: selected,
        category: category || undefined,
        trials,
        budgetUsd: budget,
      });
      window.location.hash = href('experiment', experimentId);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <details className="card">
      <summary className="section-toggle">New experiment</summary>
      <form onSubmit={submit}>
        <p className="muted">
          Pick two configs that differ in one thing. The first one you pick is the baseline (A).
        </p>
        <label>
          Name <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="memory on vs off" />
        </label>
        <fieldset>
          <legend>Configs</legend>
          {(configs.data ?? []).map((c) => (
            <label key={c.id} className="check">
              <input type="checkbox" checked={selected.includes(c.id)} onChange={() => toggle(c.id)} />
              {selected.includes(c.id) && <span className="badge">{String.fromCharCode(65 + selected.indexOf(c.id))}</span>}
              {configName(c)} <span className="muted mono">{c.harness} · {c.model}</span>
            </label>
          ))}
          {configs.data?.length === 0 && (
            <p className="muted">
              No configs yet. <a href={href('configs')}>Define one first.</a>
            </p>
          )}
        </fieldset>
        <div className="row">
          <label>
            Tasks
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">all categories</option>
              {categories.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label>
            Trials per task <input type="number" min={1} max={50} value={trials} onChange={(e) => setTrials(Number(e.target.value))} />
          </label>
          <label>
            Budget (USD) <input type="number" min={0.01} step={0.5} value={budget} onChange={(e) => setBudget(Number(e.target.value))} />
          </label>
        </div>
        <p className="muted">
          {tasks.data ? `${taskCount} tasks` : 'Loading tasks…'} × {selected.length} configs × {trials} trials ={' '}
          {taskCount * selected.length * trials} runs.
          The run stops starting new trials once the budget is spent.
        </p>
        {error && <p className="error">{error}</p>}
        <button disabled={busy || selected.length === 0 || !name}>{busy ? 'Starting…' : 'Run'}</button>
      </form>
    </details>
  );
}
