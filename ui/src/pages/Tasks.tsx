import { api } from '../api';
import { useData } from '../useData';

export function TasksPage() {
  const tasks = useData(api.tasks, []);
  return (
    <>
      <h2>Tasks</h2>
      {tasks.error && (
        <p className="error">
          Couldn't load tasks: {tasks.error}{' '}
          <button type="button" className="link" onClick={tasks.reload}>
            Try again
          </button>
        </p>
      )}
      {!tasks.data && !tasks.error && <p className="muted">Loading tasks…</p>}
      <table>
        <thead>
          <tr>
            <th>Task</th>
            <th>Category</th>
            <th>Graders</th>
            <th>Sessions</th>
            <th>Version</th>
          </tr>
        </thead>
        <tbody>
          {(tasks.data ?? []).map((t) => (
            <tr key={t.id}>
              <td>
                <strong className="mono">{t.id}</strong>
                <details>
                  <summary>{t.title}</summary>
                  {t.sessions.map((s, i) => (
                    <pre key={i}>{s}</pre>
                  ))}
                </details>
              </td>
              <td>{t.category}</td>
              <td>{t.graders.join(', ')}</td>
              <td>{t.sessions.length}</td>
              <td className="mono muted">{t.version}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
