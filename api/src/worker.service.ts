import { BadRequestException, Logger } from '@nestjs/common';
import { execFile, spawn } from 'node:child_process';
import { createWriteStream, mkdirSync } from 'node:fs';
import * as path from 'node:path';
import { createInterface } from 'node:readline';
import { promisify } from 'node:util';
import { settings } from './settings';

const exec = promisify(execFile);

export interface RunRequest {
  name: string;
  configIds: string[];
  taskIds?: string[];
  category?: string;
  trials: number;
  budgetUsd: number;
  concurrency: number;
}

export interface RunningExperiment {
  experimentId: string;
  pid: number;
  startedAt: string;
  log: string;
}

export class WorkerService {
  private readonly logger = new Logger(WorkerService.name);
  private readonly running = new Map<string, RunningExperiment>();

  constructor(private readonly command: string[]) {}

  async json<T>(...args: string[]): Promise<T> {
    const [bin, ...base] = this.command;
    try {
      const { stdout } = await exec(bin, [...base, ...args], { maxBuffer: 64 * 1024 * 1024 });
      return JSON.parse(stdout) as T;
    } catch (error) {
      const stderr = (error as { stderr?: string }).stderr ?? String(error);
      throw new BadRequestException(stderr.trim().split('\n').slice(-3).join('\n'));
    }
  }

  async exec(...args: string[]): Promise<string> {
    const [bin, ...base] = this.command;
    const { stdout } = await exec(bin, [...base, ...args]);
    return stdout;
  }

  isRunning(experimentId: string): RunningExperiment | undefined {
    return this.running.get(experimentId);
  }

  start(request: RunRequest): Promise<RunningExperiment> {
    const [bin, ...base] = this.command;
    const args = [
      ...base,
      'run',
      '--name', request.name,
      '--trials', String(request.trials),
      '--budget', String(request.budgetUsd),
      '--concurrency', String(request.concurrency),
      ...request.configIds.flatMap((id) => ['--config', id]),
      ...(request.taskIds?.length ? ['--tasks', request.taskIds.join(',')] : []),
      ...(request.category ? ['--category', request.category] : []),
    ];
    mkdirSync(settings.runsDir, { recursive: true });
    const child = spawn(bin, args, { stdio: ['ignore', 'pipe', 'pipe'] });
    const startedAt = new Date().toISOString();

    return new Promise((resolve, reject) => {
      let started: RunningExperiment | undefined;
      const stderr: string[] = [];
      child.stderr.on('data', (chunk: Buffer) => stderr.push(chunk.toString()));
      createInterface({ input: child.stdout }).on('line', (line) => {
        if (!started) {
          const event = safeParse(line);
          if (event?.event !== 'start') return;
          const log = path.join(settings.runsDir, `${event.experiment_id}.log`);
          started = { experimentId: event.experiment_id, pid: child.pid ?? -1, startedAt, log };
          this.running.set(started.experimentId, started);
          const file = createWriteStream(log, { flags: 'a' });
          child.stderr.pipe(file);
          resolve(started);
        }
      });
      child.on('error', reject);
      child.on('exit', (code) => {
        if (started) {
          this.running.delete(started.experimentId);
          this.logger.log(`experiment ${started.experimentId} finished with exit code ${code}`);
        } else {
          reject(new BadRequestException(stderr.join('').trim().split('\n').slice(-3).join('\n') || `worker exited ${code}`));
        }
      });
    });
  }
}

function safeParse(line: string): { event?: string; experiment_id: string } | undefined {
  try {
    return JSON.parse(line);
  } catch {
    return undefined;
  }
}
