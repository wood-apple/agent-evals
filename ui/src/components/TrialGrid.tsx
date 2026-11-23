import { configName, trialOutcome } from '../format';
import { href } from '../router';
import type { Config, Trial } from '../types';

interface Props {
  taskIds: string[];
  configs: Config[];
  trials: Trial[];
}

export function TrialGrid({ taskIds, configs, trials }: Props) {
  const byCell = new Map<string, Trial[]>();
  for (const trial of trials) {
    const key = `${trial.task_id}|${trial.config_id}`;
    byCell.set(key, [...(byCell.get(key) ?? []), trial]);
  }
  return (
    <table className="grid">
      <thead>
        <tr>
          <th>Task</th>
          {configs.map((c) => (
            <th key={c.id}>{configName(c)}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {taskIds.map((taskId) => (
          <tr key={taskId}>
            <td className="mono">{taskId}</td>
            {configs.map((c) => (
              <td key={c.id}>
                {(byCell.get(`${taskId}|${c.id}`) ?? [])
                  .sort((x, y) => x.trial_index - y.trial_index)
                  .map((trial) => {
                    const outcome = trialOutcome(trial);
                    return (
                      <a
                        key={trial.id}
                        href={href('trial', trial.id)}
                        className={`dot ${outcome}`}
                        title={`trial ${trial.trial_index}: ${outcome}${trial.failure_category ? ` (${trial.failure_category})` : ''}`}
                      >
                        {outcome === 'pass' ? '✓' : outcome === 'fail' ? '✗' : '!'}
                      </a>
                    );
                  })}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
