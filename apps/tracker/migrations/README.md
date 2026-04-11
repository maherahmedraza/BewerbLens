# Database Migrations

Migraciones SQL organizadas cronológicamente. Ejecutar en Supabase SQL Editor en orden.

## Orden de ejecución

| # | Archivo | Descripción |
|---|---------|-------------|
| 1 | `schema.sql` | Schema base — tables `applications`, `ai_processing_logs`, `raw_emails` |
| 2 | `schema_v2.sql` | Añade campos `location`, `salary_range`, `source_email_id` a applications + `raw_emails` table |
| 3 | `schema_orchestration_v3.sql` | Pipeline orchestration — `pipeline_runs`, `pipeline_config`, `pipeline_config_audit`, `pipeline_tasks` |
| 4 | `migration_v4_steps_logs.sql` | Añade `pipeline_run_steps` y `pipeline_run_logs` para tracking granular |
| 5 | `migration_v4_durability_final.sql` | Adds `heartbeat_at`, `task_id` FK to pipeline_runs + config audit trigger |
| 6 | `migration_0006_atomic_claim.sql` | `claim_next_task()` SQL function con `FOR UPDATE SKIP LOCKED` para claiming atómico |

## Notas

- Cada migración es **idempotente** (`IF NOT EXISTS`, `CREATE OR REPLACE`)
- La tabla `pipeline_config` es un singleton — solo permite una fila
- El trigger `tr_audit_config` registra automáticamente cambios en `pipeline_config_audit`
- La función `claim_next_task()` usa bloqueo a nivel de fila para prevenir race conditions
