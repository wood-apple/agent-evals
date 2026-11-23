import { Module } from '@nestjs/common';
import { ServeStaticModule } from '@nestjs/serve-static';
import { existsSync } from 'node:fs';
import {
  ConfigsController,
  ExperimentsController,
  JudgeValidationController,
  TasksController,
  TrialsController,
} from './controllers';
import { DbService } from './db.service';
import { settings } from './settings';
import { WorkerService } from './worker.service';

const staticUi = existsSync(settings.uiDist)
  ? [ServeStaticModule.forRoot({ rootPath: settings.uiDist, exclude: ['/api/{*path}'] })]
  : [];

@Module({
  imports: staticUi,
  controllers: [
    TasksController,
    ConfigsController,
    ExperimentsController,
    TrialsController,
    JudgeValidationController,
  ],
  providers: [
    { provide: DbService, useFactory: () => new DbService(settings.dbPath) },
    { provide: WorkerService, useFactory: () => new WorkerService(settings.workerCommand) },
  ],
})
export class AppModule {}
