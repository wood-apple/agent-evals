import { NotFoundException, OnModuleDestroy } from '@nestjs/common';
import { existsSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';

type Row = Record<string, unknown>;

const JSON_COLUMNS = new Set(['task_ids', 'config_ids', 'settings', 'events', 'grades']);

function decode(row: Row): Row {
  const out: Row = {};
  for (const [key, value] of Object.entries(row)) {
    if (JSON_COLUMNS.has(key) && typeof value === 'string') out[key] = JSON.parse(value);
    else if (key === 'passed' && value !== null) out[key] = Boolean(value);
    else out[key] = value;
  }
  return out;
}

export class DbService implements OnModuleDestroy {
  private db?: DatabaseSync;

  constructor(private readonly dbPath: string) {}

  private connection(): DatabaseSync | undefined {
    if (!this.db && existsSync(this.dbPath)) {
      this.db = new DatabaseSync(this.dbPath, { readOnly: true });
    }
    return this.db;
  }

  all(sql: string, ...params: (string | number)[]): Row[] {
    const db = this.connection();
    return db ? (db.prepare(sql).all(...params) as Row[]).map(decode) : [];
  }

  one(sql: string, ...params: (string | number)[]): Row {
    const row = this.connection()?.prepare(sql).get(...params) as Row | undefined;
    if (!row) throw new NotFoundException();
    return decode(row);
  }

  onModuleDestroy() {
    this.db?.close();
  }
}
