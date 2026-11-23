#!/usr/bin/env node
const [command, ...args] = process.argv.slice(2);
if (command === 'tasks') {
  console.log(JSON.stringify([{ id: 't1', title: 'Task one', category: 'c' }]));
} else if (command === 'config') {
  const config = JSON.parse(args[1]);
  console.log(JSON.stringify({ id: 'cfg-new', ...config }));
} else if (command === 'compare') {
  console.log(JSON.stringify({ verdict: 'no detectable difference (within noise)', args }));
} else if (command === 'archive') {
  console.log(JSON.stringify({ id: args[0], archived: !args.includes('--undo') }));
} else if (command === 'run') {
  console.log(JSON.stringify({ event: 'start', experiment_id: 'exp-new', planned_trials: 2 }));
  setTimeout(() => console.log(JSON.stringify({ event: 'done' })), 200);
} else {
  console.error(`unknown command ${command}`);
  process.exit(2);
}
