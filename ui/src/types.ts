export interface Settings {
  temperature: number;
  max_steps: number;
  max_tokens: number;
  token_budget: number;
  memory: boolean;
  skills: string[];
  tools: string[];
  thinking: boolean | null;
  verify?: boolean | null;
  fresh_workspace?: boolean | null;
}

export interface Config {
  id: string;
  harness: string;
  model: string;
  label: string;
  settings: Partial<Settings>;
  created_at?: string;
}

export interface Trial {
  id: string;
  experiment_id: string;
  task_id: string;
  task_version: string;
  config_id: string;
  trial_index: number;
  status: 'ok' | 'timeout' | 'error';
  passed: boolean | null;
  score: number | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
  error: string | null;
  failure_category: string | null;
  finished_at: string;
}

export interface Experiment {
  id: string;
  name: string;
  task_ids: string[];
  config_ids: string[];
  n_trials: number;
  seed: number;
  status: string;
  created_at: string;
  planned: number;
  running: boolean;
  finished?: number;
  errors?: number;
  cost_usd?: number;
  last_finished_at?: string | null;
  archived?: boolean;
}

export interface ExperimentDetail extends Experiment {
  configs: Config[];
  trials: Trial[];
}

export interface ConfigSummary {
  trials: number;
  errors: number;
  pass_rate: number | null;
  mean_score: number | null;
  mean_cost_usd: number | null;
  total_cost_usd: number;
  mean_latency_ms: number | null;
  mean_input_tokens: number | null;
  mean_output_tokens: number | null;
  failure_categories: Record<string, number>;
}

export interface TaskRow {
  task_id: string;
  n: number;
  pass_rate_a: number;
  pass_rate_b: number;
  delta: number;
  p_value: number;
  signal: string;
}

export interface Comparison {
  config_a: string;
  config_b: string;
  a: ConfigSummary;
  b: ConfigSummary;
  pairs: number;
  tasks: number;
  verdict: string;
  delta?: number;
  ci95?: [number, number];
  mcnemar?: { only_a_passed: number; only_b_passed: number; p_value: number };
  detectable_delta?: number;
  per_task: TaskRow[];
}

export interface TraceEvent {
  type: string;
  t_ms?: number;
  session?: number;
  step?: number;
  [key: string]: unknown;
}

export interface Grade {
  grader: string;
  passed: boolean;
  score: number;
  reasoning: string;
  required: boolean;
}

export interface TrialDetail extends Trial {
  events: TraceEvent[];
  grades: Grade[];
  config: Config;
}

export interface TaskInfo {
  id: string;
  title: string;
  category: string;
  version: string;
  sessions: string[];
  graders: string[];
  timeout_s: number;
}
