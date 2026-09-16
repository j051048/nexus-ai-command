// Scratch PostgreSQL/WASM verification only. Never connects to a deployed DB.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const modulePath = process.argv[2];
const { PGlite } = await import(modulePath ? pathToFileURL(path.resolve(modulePath)).href : '@electric-sql/pglite');
const db = new PGlite();
const org = '10000000-0000-0000-0000-000000000001';
const otherOrg = '10000000-0000-0000-0000-000000000002';
const owner = '20000000-0000-0000-0000-000000000001';
const peer = '20000000-0000-0000-0000-000000000002';
const outsider = '20000000-0000-0000-0000-000000000003';
const artifact = '30000000-0000-0000-0000-000000000001';
const version = '40000000-0000-0000-0000-000000000001';
const doc = '50000000-0000-0000-0000-000000000001';
let assertions = 0;
async function identity(user) {
  await db.exec('RESET ROLE');
  await db.query("SELECT set_config('request.jwt.claim.sub', $1, false)", [user]);
  await db.exec('SET ROLE authenticated');
}
async function denied(sql, args = []) {
  await assert.rejects(db.query(sql, args));
  assertions++;
}
try {
  await db.exec([
    'CREATE ROLE authenticated; CREATE ROLE anon; CREATE ROLE service_role BYPASSRLS;',
    'CREATE SCHEMA auth;',
    "CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql AS $$ SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid $$;",
    'GRANT USAGE ON SCHEMA public, auth TO authenticated, service_role, anon;',
    'CREATE TABLE organizations(id uuid PRIMARY KEY);',
    'CREATE TABLE users(id uuid PRIMARY KEY, organization_id uuid, department text);',
    'CREATE TABLE organization_members(organization_id uuid, user_id uuid, role text);',
    'CREATE TABLE documents(id uuid PRIMARY KEY, organization_id uuid, owner_id uuid, source_version text, status text, review_status text, valid_until timestamptz, visibility text, department text);',
    'CREATE TABLE agent_runs(id uuid);',
    'CREATE TABLE user_token_usage(user_id uuid, org_id uuid, date date, total_tokens bigint DEFAULT 0, estimated_cost_usd numeric DEFAULT 0, request_count int DEFAULT 0, department_id uuid, project_id uuid, updated_at timestamptz, UNIQUE(user_id,date));',
    'CREATE TABLE memory_persistence_jobs(id uuid DEFAULT gen_random_uuid(), organization_id uuid, user_id uuid, session_id text, idempotency_key text UNIQUE, payload jsonb, status text);',
    'ALTER TABLE memory_persistence_jobs ENABLE ROW LEVEL SECURITY;',
    'CREATE POLICY memory_owner_read ON memory_persistence_jobs FOR SELECT USING(user_id = auth.uid());',
    'CREATE FUNCTION current_tenant_id_text() RETURNS text LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog AS $$ SELECT organization_id::text FROM public.users WHERE id=auth.uid() $$;',
  ].join('\n'));
  await db.query('INSERT INTO organizations VALUES ($1), ($2)', [org, otherOrg]);
  await db.query("INSERT INTO users VALUES ($1,$2,'sales'),($3,$2,'support'),($4,$5,'sales')", [owner, org, peer, outsider, otherOrg]);
  await db.query("INSERT INTO organization_members VALUES ($1,$2,'employee'),($1,$3,'employee'),($4,$5,'employee')", [org, owner, peer, otherOrg, outsider]);
  // Older schema fixture only; the two migrations under test run unmodified.
  const schema = await readFile(path.join(root, 'supabase/migrations/20260722_artifact_delivery_pipeline.sql'), 'utf8');
  await db.exec(schema.replace('CREATE EXTENSION IF NOT EXISTS pgcrypto;', ''));
  await db.exec('GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated, service_role;');
  for (const file of ['20260916_001_runtime_contract_repair.sql', '20260916_002_artifact_review_boundary.sql']) {
    await db.exec(await readFile(path.join(root, 'supabase/migrations', file), 'utf8'));
  }
  await db.query("INSERT INTO documents VALUES($1,$2,$3,'v1','ready','verified',NULL,'private','sales')", [doc, org, owner]);
  await db.query("INSERT INTO artifacts(id,organization_id,created_by,artifact_code,title,artifact_type,status) VALUES($1,$2,$3,'ART-TEST','Test','customer_solution','review')", [artifact, org, owner]);
  await db.query("INSERT INTO artifact_versions(id,organization_id,artifact_id,version_number,content_markdown,quality_snapshot,evidence_snapshot,created_by) VALUES($1,$2,$3,1,'# Test', '{\"ready\":true}', $4::jsonb,$5)",
    [version, org, artifact, JSON.stringify({ records: [{ document_id: doc, source_version: 'v1' }] }), owner]);
  await identity(owner);
  assert.equal((await db.query('SELECT * FROM organization_members')).rows.length, 2); assertions++;
  assert.equal((await db.query('SELECT * FROM artifact_versions')).rows.length, 1); assertions++;
  await db.query("UPDATE organization_members SET role='admin' WHERE user_id=$1", [owner]);
  assert.equal((await db.query('SELECT role FROM organization_members WHERE user_id=$1', [owner])).rows[0].role, 'employee'); assertions++;
  await denied("UPDATE artifacts SET approval_status='approved' WHERE id=$1", [artifact]);
  await denied("SELECT review_artifact_version($1,$2,'approved','{}',NULL)", [artifact, version]);
  await denied("SELECT review_artifact_version($1,$2,'approved','{\"facts\":true,\"promises\":true}',NULL)", [artifact, doc]);
  await db.query("SELECT review_artifact_version($1,$2,'approved','{\"facts\":true,\"promises\":true}',NULL)", [artifact, version]);
  assert.equal((await db.query('SELECT approval_status FROM artifacts')).rows[0].approval_status, 'approved'); assertions++;
  await denied("UPDATE artifact_versions SET content_markdown='changed' WHERE id=$1", [version]);
  const job = { organization_id: org, user_id: owner, session_id: 'session', idempotency_key: 'memory-key', payload: { ciphertext: 'test-encrypted' } };
  const first = await db.query('SELECT enqueue_memory_persistence_job($1) AS id', [JSON.stringify(job)]);
  const second = await db.query('SELECT enqueue_memory_persistence_job($1) AS id', [JSON.stringify(job)]);
  assert.equal(first.rows[0].id, second.rows[0].id); assertions++;
  await denied('SELECT enqueue_memory_persistence_job($1)', [JSON.stringify({ ...job, user_id: peer })]);
  await denied('SELECT upsert_daily_token_usage_v2($1,$2,CURRENT_DATE,1,0,NULL,NULL)', [owner, org]);
  await identity(peer);
  for (const table of ['artifacts', 'artifact_versions', 'artifact_reviews']) {
    assert.equal((await db.query('SELECT * FROM ' + table)).rows.length, 0); assertions++;
  }
  await identity(outsider);
  assert.equal((await db.query('SELECT * FROM artifact_versions')).rows.length, 0); assertions++;
  await db.exec('RESET ROLE');
  await db.query("UPDATE documents SET source_version='v2' WHERE id=$1", [doc]);
  await identity(owner);
  assert.equal((await db.query('SELECT * FROM artifact_versions')).rows.length, 0); assertions++;
  await db.exec('RESET ROLE; SET ROLE service_role');
  await db.query('SELECT upsert_daily_token_usage_v2($1,$2,CURRENT_DATE,7,0.1,NULL,NULL)', [owner, org]);
  assert.equal(Number((await db.query('SELECT total_tokens FROM user_token_usage')).rows[0].total_tokens), 7); assertions++;
  console.log(JSON.stringify({ status: 'PASS', mode: 'scratch-postgres-wasm', assertions, production_verified: false }));
} finally { await db.close(); }
