import {
  BadRequestException,
  Body,
  Controller,
  Get,
  NotFoundException,
  Param,
  Post,
  Query,
  Res,
} from '@nestjs/common';
import type { Response } from 'express';
import { existsSync, readFileSync } from 'node:fs';
import { mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import * as path from 'node:path';
import { DbService } from './db.service';
import { settings } from './settings';
import { RunRequest, WorkerService } from './worker.service';

const HARNESSES = ['baseline', 'hermes'];

@Controller('tasks')
export class TasksController {
  private cache?: unknown[];

  constructor(private readonly worker: WorkerService) {}

  @Get()
  async list() {
    this.cache ??= await this.worker.json<unknown[]>('tasks');
    return this.cache;
  }
}

@Controller('configs')
export class ConfigsController {
  constructor(
    private readonly db: DbService,
    private readonly worker: WorkerService,
  ) {}

  @Get()
  list() {
    return this.db.all('select * from configs order by created_at desc');
  }

  @Post()
  create(@Body() body: Record<string, unknown>) {
    if (!HARNESSES.includes(String(body.harness))) {
      throw new BadRequestException(`harness must be one of ${HARNESSES.join(', ')}`);
    }
    if (typeof body.model !== 'string' || !body.model.includes('/')) {
      throw new BadRequestException('model must be a LiteLLM model string such as groq/openai/gpt-oss-120b');
    }
    const config = {
      harness: body.harness,
      model: body.model,
      label: typeof body.label === 'string' ? body.label : '',
      settings: typeof body.settings === 'object' && body.settings ? body.settings : {},
    };
    return this.worker.json('config', 'add', JSON.stringify(config));
  }
}

@Controller('experiments')
export class ExperimentsController {
  constructor(
    private readonly db: DbService,
    private readonly worker: WorkerService,
  ) {}

  @Get()
  list() {
    return this.db
      .all(
        `select e.*, count(t.id) as finished,
                coalesce(sum(t.status = 'error'), 0) as errors,
                coalesce(sum(t.cost_usd), 0) as cost_usd,
                max(t.finished_at) as last_finished_at
         from experiments e left join trials t on t.experiment_id = e.id
         group by e.id order by e.created_at desc`,
      )
      .map((e) => this.withRunState(e));
  }

  @Get(':id')
  get(@Param('id') id: string) {
    const experiment = this.withRunState(this.db.one('select * from experiments where id = ?', id));
    const configIds = experiment.config_ids as string[];
    const configs = configIds.map((configId) => this.db.one('select * from configs where id = ?', configId));
    const trials = this.db.all(
      `select * from trials where experiment_id = ? order by task_id, trial_index, config_id`,
      id,
    );
    const last = trials.map((t) => String(t.finished_at)).sort().at(-1) ?? null;
    return { ...experiment, last_finished_at: last, configs, trials };
  }

  @Get(':id/compare')
  compare(@Param('id') id: string, @Query('a') a?: string, @Query('b') b?: string) {
    const args = ['compare', id, '--json'];
    if (a) args.push('--a', a);
    if (b) args.push('--b', b);
    return this.worker.json(...args);
  }

  @Get(':id/log')
  log(@Param('id') id: string) {
    const file = path.join(settings.runsDir, `${path.basename(id)}.log`);
    const text = existsSync(file) ? readFileSync(file, 'utf8') : '';
    return { log: text.split('\n').slice(-200).join('\n') };
  }

  @Get(':id/export')
  async export(@Param('id') id: string, @Query('format') format = 'json', @Res() res: Response) {
    if (!['json', 'csv'].includes(format)) throw new BadRequestException('format must be json or csv');
    this.db.one('select id from experiments where id = ?', id);
    const out = path.join(await mkdtemp(path.join(tmpdir(), 'export-')), `${id}.${format}`);
    await this.worker.exec('export', id, '--format', format, '--out', out);
    res.attachment(`${id}.${format}`).type(format).send(await readFile(out));
  }

  @Post()
  async create(@Body() body: Partial<RunRequest>) {
    const request: RunRequest = {
      name: String(body.name ?? '').trim(),
      configIds: Array.isArray(body.configIds) ? body.configIds.map(String) : [],
      taskIds: Array.isArray(body.taskIds) ? body.taskIds.map(String) : undefined,
      category: body.category ? String(body.category) : undefined,
      trials: Number(body.trials ?? 3),
      budgetUsd: Number(body.budgetUsd ?? 2),
      concurrency: Number(body.concurrency ?? 2),
    };
    if (!request.name) throw new BadRequestException('name is required');
    if (request.configIds.length < 1) throw new BadRequestException('pick at least one config');
    if (!Number.isInteger(request.trials) || request.trials < 1 || request.trials > 50) {
      throw new BadRequestException('trials must be between 1 and 50');
    }
    if (!(request.budgetUsd > 0)) throw new BadRequestException('budgetUsd must be positive');
    return this.worker.start(request);
  }

  private withRunState(experiment: Record<string, unknown>): Record<string, unknown> {
    const planned =
      (experiment.task_ids as string[]).length *
      (experiment.config_ids as string[]).length *
      Number(experiment.n_trials);
    const running = this.worker.isRunning(String(experiment.id));
    return { ...experiment, planned, running: Boolean(running) };
  }
}

@Controller('trials')
export class TrialsController {
  constructor(private readonly db: DbService) {}

  @Get(':id')
  get(@Param('id') id: string) {
    const trial = this.db.one('select * from trials where id = ?', id);
    const trace = this.db.all('select events, grades from traces where trial_id = ?', id)[0] ?? {
      events: [],
      grades: [],
    };
    const config = this.db.one('select * from configs where id = ?', String(trial.config_id));
    return { ...trial, ...trace, config };
  }
}

@Controller('judge-validation')
export class JudgeValidationController {
  @Get()
  get() {
    if (!existsSync(settings.judgeReport)) throw new NotFoundException('run `evals judge-validate` first');
    return JSON.parse(readFileSync(settings.judgeReport, 'utf8'));
  }
}
