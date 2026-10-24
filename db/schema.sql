create extension if not exists pgcrypto;
create table if not exists stages (
 id serial primary key, position int not null unique, name text not null, purpose text not null,
 insight text, prospect_says jsonb not null default '[]', happened_options jsonb not null default '[]'
);
create table if not exists calls (
 id uuid primary key default gen_random_uuid(), prospect_name text, company text,
 started_at timestamptz not null default now(), ended_at timestamptz,
 current_stage_id int references stages(id), furthest_stage_id int references stages(id),
 outcome text check (outcome in ('agreed_to_receive_report','next_step_agreed','interested','follow_up','call_again','not_interested','do_not_call','wrong_person','moved_company','not_logged')),
 summary text
);
create table if not exists stage_results (
 id uuid primary key default gen_random_uuid(), call_id uuid not null references calls(id) on delete cascade,
 stage_id int not null references stages(id), happened_key text, prospect_words text, llm_read jsonb,
 created_at timestamptz not null default now()
);
create index if not exists stage_results_call_idx on stage_results (call_id, created_at);
create index if not exists calls_started_idx on calls (started_at desc);
