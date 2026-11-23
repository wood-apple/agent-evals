import { useState } from 'react';
import { api } from '../api';
import { useData } from '../useData';

const SKILLS = ['acme-finance', 'acme-release-notes', 'acme-shipping', 'git-commit-style', 'qlog-format'];

export function ConfigsPage() {
  const configs = useData(api.configs, []);
  return (
    <>
      <h2>Configs</h2>
      <p className="muted">
        A config is harness × model × settings. Its id is a hash of everything except the label, so the same settings
        always map to the same id and past results stay reproducible.
      </p>
      <table>
        <thead>
          <tr>
            <th>Label</th>
            <th>Harness</th>
            <th>Model</th>
            <th>Settings</th>
            <th>Id</th>
          </tr>
        </thead>
        <tbody>
          {(configs.data ?? []).map((c) => (
            <tr key={c.id}>
              <td>{c.label}</td>
              <td>{c.harness}</td>
              <td className="mono">{c.model}</td>
              <td className="mono small">{JSON.stringify(c.settings)}</td>
              <td className="mono muted">{c.id}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <ConfigForm onSaved={configs.reload} />
    </>
  );
}

function ConfigForm({ onSaved }: { onSaved: () => void }) {
  const [label, setLabel] = useState('');
  const [harness, setHarness] = useState('baseline');
  const [model, setModel] = useState('groq/openai/gpt-oss-120b');
  const [temperature, setTemperature] = useState(0);
  const [maxSteps, setMaxSteps] = useState(15);
  const [tokenBudget, setTokenBudget] = useState(300000);
  const [memory, setMemory] = useState(false);
  const [thinking, setThinking] = useState('default');
  const [skills, setSkills] = useState<string[]>([]);
  const [message, setMessage] = useState<string>();

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      const saved = await api.createConfig({
        label,
        harness,
        model,
        settings: {
          temperature,
          max_steps: maxSteps,
          token_budget: tokenBudget,
          memory,
          skills,
          ...(thinking === 'default' ? {} : { thinking: thinking === 'on' }),
        },
      });
      setMessage(`Saved ${saved.id}`);
      onSaved();
    } catch (e) {
      setMessage((e as Error).message);
    }
  };

  return (
    <details className="card">
      <summary className="section-toggle">Define a config</summary>
      <form onSubmit={submit}>
        <div className="row">
          <label>
            Label <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="hermes · memory on" />
          </label>
          <label>
            Harness
            <select value={harness} onChange={(e) => setHarness(e.target.value)}>
              <option value="baseline">baseline (tool-calling loop)</option>
              <option value="hermes">hermes (Hermes Agent)</option>
            </select>
          </label>
          <label>
            Model (LiteLLM string)
            <input value={model} onChange={(e) => setModel(e.target.value)} list="models" />
            <datalist id="models">
              <option value="groq/openai/gpt-oss-120b" />
              <option value="groq/openai/gpt-oss-20b" />
              <option value="gemini/gemini-3.5-flash" />
              <option value="anthropic/claude-haiku-5-5" />
              <option value="ollama/qwen2.5:7b" />
            </datalist>
          </label>
        </div>
        <div className="row">
          <label>
            Temperature <input type="number" step={0.1} min={0} max={2} value={temperature} onChange={(e) => setTemperature(Number(e.target.value))} />
          </label>
          <label>
            Max steps per session <input type="number" min={1} value={maxSteps} onChange={(e) => setMaxSteps(Number(e.target.value))} />
          </label>
          <label>
            Token budget per trial <input type="number" min={1000} step={1000} value={tokenBudget} onChange={(e) => setTokenBudget(Number(e.target.value))} />
          </label>
        </div>
        <label>
          Thinking (reasoning before each step; applied to local Ollama models)
          <select value={thinking} onChange={(e) => setThinking(e.target.value)}>
            <option value="default">model default</option>
            <option value="off">off</option>
            <option value="on">on</option>
          </select>
        </label>
        <label className="check">
          <input type="checkbox" checked={memory} onChange={(e) => setMemory(e.target.checked)} /> Memory (persists across
          sessions within one trial only)
        </label>
        <fieldset>
          <legend>Skills</legend>
          {SKILLS.map((s) => (
            <label key={s} className="check">
              <input
                type="checkbox"
                checked={skills.includes(s)}
                onChange={() => setSkills((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]))}
              />
              {s}
            </label>
          ))}
        </fieldset>
        <button>Save config</button>
        {message && <p className="muted">{message}</p>}
      </form>
    </details>
  );
}
