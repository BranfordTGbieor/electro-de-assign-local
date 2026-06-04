# Production Notes

| Local | Production |
| --- | --- |
| DuckDB | Azure Databricks / Delta Lake |
| Local CSV/API client | Databricks Job or orchestrated ingestion |
| Local DuckDB tables | ADLS Gen2 Delta tables |
| `.env` | Azure Key Vault |
| Local logs | Azure Monitor / Log Analytics |
| pytest / SQL assertions | CI/CD quality gates |
| DuckDB watermark table | Delta control table |
| Makefile | CI/CD pipeline / scheduled job |

Terraform would manage the cloud infrastructure: storage accounts, Databricks workspaces, Key Vault, identities, permissions, job definitions, and monitoring resources. Databricks jobs would run ingestion and transformation as scheduled tasks with job clusters.

ADLS Gen2 would store bronze, quarantine, duplicate, and gold Delta tables. Unity Catalog would manage table ownership, lineage, access policies, and environment separation. Secrets such as API keys would be read from Key Vault through managed identity rather than environment files.

The same quarantine and duplicate patterns would support operational review in production. Invalid records would be retained in a dead-letter Delta table with raw payloads and validation errors. Duplicate records would remain traceable in bronze while curated downstream models exclude them.

Observability should include records read, records valid, quarantined count, duplicate count, watermark freshness, job duration, retry counts, API failure rates, data volume, and cost metrics. Alerts should fire on freshness breaches, sudden quality regressions, failed jobs, and abnormal cost changes.

Cluster auto-termination and job clusters would control cost. CI/CD would run unit tests, SQL/dbt tests, static checks, and infrastructure policy checks before promoting changes.
