import * as path from 'node:path';

const root = process.env.EVALS_ROOT ?? path.resolve(__dirname, '../..');

export const settings = {
  root,
  dbPath: process.env.EVALS_DB ?? path.join(root, 'results/evals.db'),
  runsDir: path.join(root, 'results/runs'),
  judgeReport: path.join(root, 'results/judge-validation.json'),
  uiDist: process.env.UI_DIST ?? path.join(root, 'ui/dist'),
  workerCommand: (process.env.EVALS_WORKER ?? `uv --directory ${path.join(root, 'worker')} run --frozen evals`)
    .split(' ')
    .filter(Boolean),
  port: Number(process.env.PORT ?? 3000),
};
