import { ConfigsPage } from './pages/Configs';
import { ExperimentPage } from './pages/Experiment';
import { ExperimentsPage } from './pages/Experiments';
import { JudgePage } from './pages/Judge';
import { TasksPage } from './pages/Tasks';
import { TrialPage } from './pages/Trial';
import { href, useRoute } from './router';

const NAV = [
  ['experiments', 'Experiments'],
  ['configs', 'Configs'],
  ['tasks', 'Tasks'],
  ['judge', 'Judge'],
];

export function App() {
  const [page = 'experiments', id] = useRoute();
  return (
    <>
      <header>
        <h1>Agent Evals</h1>
        <nav>
          {NAV.map(([key, label]) => (
            <a key={key} href={href(key)} className={page === key ? 'active' : ''}>
              {label}
            </a>
          ))}
        </nav>
      </header>
      <main>{render(page, id)}</main>
    </>
  );
}

function render(page: string, id?: string) {
  if (page === 'experiment' && id) return <ExperimentPage id={id} />;
  if (page === 'trial' && id) return <TrialPage id={id} />;
  if (page === 'configs') return <ConfigsPage />;
  if (page === 'tasks') return <TasksPage />;
  if (page === 'judge') return <JudgePage />;
  return <ExperimentsPage />;
}
