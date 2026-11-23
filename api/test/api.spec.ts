import { INestApplication } from '@nestjs/common';
import assert from 'node:assert/strict';
import { after, before, describe, it } from 'node:test';
import { Test } from '@nestjs/testing';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import * as path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { DbService } from '../src/db.service';
import { WorkerService } from '../src/worker.service';

const schema = readFileSync(path.join(__dirname, '../../../worker/evals/schema.sql'), 'utf8');

function seed(dbPath: string) {
  const db = new DatabaseSync(dbPath);
  db.exec(schema);
  db.prepare(`insert into configs values ('A', 'baseline', 'm/a', '{"memory": false}', 'model a', 'now')`).run();
  db.prepare(`insert into configs values ('B', 'baseline', 'm/b', '{"memory": true}', 'model b', 'now')`).run();
  db.prepare(
    `insert into experiments values ('exp1', 'demo', '["t1","t2"]', '["A","B"]', 3, 0, 'running', 'now')`,
  ).run();
  db.prepare(
    `insert into trials (id, experiment_id, task_id, task_version, config_id, trial_index, status,
       passed, score, cost_usd, finished_at)
     values ('tr1', 'exp1', 't1', 'v', 'A', 0, 'ok', 1, 1.0, 0.01, 'now')`,
  ).run();
  db.prepare(`insert into traces values ('tr1', '[{"type": "session_start"}]', '[{"grader": "exact_match"}]')`).run();
  db.close();
}

describe('API', () => {
  let app: INestApplication;

  before(async () => {
    const dbPath = path.join(mkdtempSync(path.join(tmpdir(), 'api-')), 'evals.db');
    seed(dbPath);
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] })
      .overrideProvider(DbService)
      .useValue(new DbService(dbPath))
      .overrideProvider(WorkerService)
      .useValue(new WorkerService(['node', path.join(__dirname, '../../test/fake-worker.js')]))
      .compile();
    app = moduleRef.createNestApplication();
    app.setGlobalPrefix('api');
    await app.init();
  });

  after(() => app.close());

  it('lists experiments with progress', async () => {
    const res = await request(app.getHttpServer()).get('/api/experiments').expect(200);
    assert.equal(res.body.length, 1);
    const [experiment] = res.body;
    assert.deepEqual(
      [experiment.id, experiment.planned, experiment.finished, experiment.errors, experiment.task_ids],
      ['exp1', 12, 1, 0, ['t1', 't2']],
    );
    assert.equal(experiment.archived, false);
  });

  it('archives through the worker', async () => {
    const res = await request(app.getHttpServer()).post('/api/experiments/exp1/archive').send({ archived: false }).expect(201);
    assert.deepEqual(res.body, { id: 'exp1', archived: false });
    await request(app.getHttpServer()).post('/api/experiments/nope/archive').send({}).expect(404);
  });

  it('returns an experiment with its configs and trials', async () => {
    const res = await request(app.getHttpServer()).get('/api/experiments/exp1').expect(200);
    assert.deepEqual(res.body.configs.map((c: { label: string }) => c.label), ['model a', 'model b']);
    assert.equal(res.body.trials[0].id, 'tr1');
    assert.equal(res.body.trials[0].passed, true);
  });

  it('returns a trial with its trace', async () => {
    const res = await request(app.getHttpServer()).get('/api/trials/tr1').expect(200);
    assert.deepEqual(res.body.events, [{ type: 'session_start' }]);
    assert.deepEqual(res.body.config.settings, { memory: false });
  });

  it('404s on unknown ids', async () => {
    await request(app.getHttpServer()).get('/api/trials/nope').expect(404);
    await request(app.getHttpServer()).get('/api/experiments/nope').expect(404);
  });

  it('passes comparison through to the worker', async () => {
    const res = await request(app.getHttpServer()).get('/api/experiments/exp1/compare?a=B&b=A').expect(200);
    assert.deepEqual(res.body.args, ['exp1', '--json', '--a', 'B', '--b', 'A']);
  });

  it('validates new configs before calling the worker', async () => {
    await request(app.getHttpServer()).post('/api/configs').send({ harness: 'magic', model: 'x/y' }).expect(400);
    await request(app.getHttpServer()).post('/api/configs').send({ harness: 'baseline', model: 'nope' }).expect(400);
    const res = await request(app.getHttpServer())
      .post('/api/configs')
      .send({ harness: 'hermes', model: 'groq/x', label: 'h', settings: { memory: true } })
      .expect(201);
    assert.equal(res.body.id, 'cfg-new');
    assert.equal(res.body.harness, 'hermes');
    assert.deepEqual(res.body.settings, { memory: true });
  });

  it('starts a run and reports the experiment id', async () => {
    await request(app.getHttpServer()).post('/api/experiments').send({ name: '', configIds: ['A'] }).expect(400);
    await request(app.getHttpServer()).post('/api/experiments').send({ name: 'x', configIds: ['A'], trials: 0 }).expect(400);
    const res = await request(app.getHttpServer())
      .post('/api/experiments')
      .send({ name: 'new', configIds: ['A', 'B'], trials: 2, budgetUsd: 1 })
      .expect(201);
    assert.equal(res.body.experimentId, 'exp-new');
  });

  it('lists tasks from the worker', async () => {
    const res = await request(app.getHttpServer()).get('/api/tasks').expect(200);
    assert.equal(res.body[0].id, 't1');
  });
});
