# dbt Incremental Models – Team Guide

## What is an incremental model?

An incremental model is a dbt model that, after its first run, only processes **new or changed
rows** instead of rebuilding the entire table. On the first run (or with `--full-refresh`) dbt
builds the whole table. On later runs dbt inserts or merges only the rows selected by the
incremental filter. This makes large fact tables much faster and cheaper to build.

## How to configure one

Set the materialization in the model's config block:

```sql
{{ config(
    materialized = 'incremental',
    unique_key   = 'order_id',
    incremental_strategy = 'merge'
) }}
```

- `materialized='incremental'` turns the model into an incremental model.
- `unique_key` tells dbt which column identifies a row, so updated rows are merged instead of duplicated.
- `incremental_strategy` controls how new data is applied. On Snowflake the default is `merge`;
  other options include `append`, `delete+insert` and `insert_overwrite` (adapter dependent).

## The is_incremental() macro

Inside the model, wrap the filter for new rows in `is_incremental()`. The macro returns true only
when the target table already exists, the model is materialized as incremental, and the run is not
a full refresh.

```sql
select * from {{ ref('stg_orders') }}
{% if is_incremental() %}
  where updated_at > (select max(updated_at) from {{ this }})
{% endif %}
```

`{{ this }}` refers to the existing target table in the warehouse.

## When to use incremental models

- Event or log tables with millions of rows that grow every day.
- Fact tables where only recent data changes.
- When a full rebuild takes too long or costs too many warehouse credits.

Avoid incremental models for small tables – a simple `table` materialization is easier to maintain.

## Common problems

- **Duplicates**: usually caused by a missing or non-unique `unique_key`.
- **Missed late-arriving data**: if records arrive late, filter with a lookback window,
  e.g. `updated_at > dateadd(day, -3, (select max(updated_at) from {{ this }}))`.
- **Schema changes**: new columns are ignored by default. Use `on_schema_change='append_new_columns'`
  or run `dbt run --full-refresh -s model_name`.
