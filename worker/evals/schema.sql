create table if not exists configs (
    id text primary key,
    harness text not null,
    model text not null,
    settings text not null,
    label text not null default '',
    created_at text not null
);

create table if not exists experiments (
    id text primary key,
    name text not null,
    task_ids text not null,
    config_ids text not null,
    n_trials integer not null,
    seed integer not null,
    status text not null,
    created_at text not null
);

create table if not exists trials (
    id text primary key,
    experiment_id text not null references experiments(id),
    task_id text not null,
    task_version text not null,
    config_id text not null references configs(id),
    trial_index integer not null,
    status text not null,
    passed integer,
    score real,
    input_tokens integer not null default 0,
    output_tokens integer not null default 0,
    cost_usd real not null default 0,
    latency_ms integer not null default 0,
    error text,
    failure_category text,
    finished_at text not null,
    unique(experiment_id, task_id, config_id, trial_index)
);

create table if not exists traces(
    trial_id text primary key references trials(id),
    events text not null,
    grades text not null
);

create table if not exists archived_experiments (
    experiment_id text primary key references experiments(id),
    archived_at text not null
);
