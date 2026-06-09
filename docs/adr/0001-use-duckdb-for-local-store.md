# ADR 0001: Use DuckDB for the Local Analytical Store

## Status

Accepted

## Context

The assignment needs to run locally and be easy for reviewers to reproduce without cloud credentials or managed infrastructure. The solution still needs durable storage, SQL transformations, exportable artifacts, and a shape that maps cleanly to a production lakehouse.

## Decision

Use DuckDB as the local analytical store. Bronze, control, and gold tables are created in a local DuckDB database, and dbt uses the DuckDB adapter for curated transformations.

## Consequences

- Reviewers can run the full pipeline with only local files and Python dependencies.
- SQL models and tests stay close to a warehouse/lakehouse implementation.
- DuckDB is not the intended production serving layer. In production, the same logical layers would move to managed object storage and Delta tables, as described in `docs/production_notes.md`.
