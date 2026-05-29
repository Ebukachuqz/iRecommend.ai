# Database Migrations

This document covers the migration runner, active migrations, and manual fallback options.

---

## Prerequisites

Add `SUPABASE_DB_URL` to `.env`. See [SETUP.md](SETUP.md) for connection string guidance.

Check connectivity before running migrations:

```powershell
python scripts/check_db_connection.py
```

If this command times out and Supabase says the direct connection string is not IPv4 compatible, replace `SUPABASE_DB_URL` with the Session Pooler connection string from Supabase Dashboard -> Connect.

---

## Running Migrations

Preview the active migration order without connecting or changing schema:

```powershell
python scripts/run_migrations.py --dry-run
```

Run all active stable migrations:

```powershell
python scripts/run_migrations.py
```

Run a specific range:

```powershell
python scripts/run_migrations.py --from 003 --to 007
```

---

## Reset (Destructive)

The reset migration drops all tables and is skipped by default. To run only the reset, you must be explicit:

```powershell
python scripts/run_migrations.py --include-reset --confirm-reset --from 000 --to 000
```

> **Warning:** This is destructive. Only use for clean rebuilds on a non-production database.

---

## Active Stable Migrations

```text
src/db/sql/000_reset_database.sql                       optional destructive reset
src/db/sql/001_core_schema.sql                          product metadata, reviews, personas
src/db/sql/002_task_a_schema.sql                        review simulation storage
src/db/sql/003_task_b_schema.sql                        recommendation tables and vector columns
src/db/sql/004_pgvector_functions.sql                   pgvector RPC functions
src/db/sql/005_indexes.sql                              relational and vector indexes
src/db/sql/006_product_metadata_optional_fields.sql     safe metadata image/related-product backfill columns
src/db/sql/007_rename_user_preference_vectors.sql       safe preference-vector table/function rename
```

Old development migrations are archived in `src/db/sql/archive/`. Use only the stable migrations above for any rebuild.

---

## Manual Fallback

If direct DB access is unavailable, run the same SQL files manually in the Supabase SQL Editor. Use `000_reset_database.sql` only for clean rebuilds.

Supabase remains hosted externally. Docker Compose does not start a local database.
