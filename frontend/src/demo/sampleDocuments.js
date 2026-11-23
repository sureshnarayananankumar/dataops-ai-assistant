// Generated from sample_documents/ for the in-browser demo. Do not edit by hand.
export const SAMPLE_DOCUMENTS = [
 {
  "filename": "data_quality_checklist.pdf",
  "file_type": "pdf",
  "size_bytes": 3087,
  "pages": [
   {
    "page": 1,
    "text": "# Data Quality Checklist for New Pipelines\n\nUse this checklist before a new pipeline goes to production. Every item should be checked by the\ndeveloper and reviewed by a second engineer.\n\n\n# Completeness\n\nCompare row counts between source and target after each load. A difference of more than 1\npercent must raise an alert. Check that mandatory columns contain no null values.\n\n\n# Uniqueness\n\nEvery table must have a primary key. Add a dbt unique test and a not_null test on the primary key\ncolumn of every staging and mart model.\n\n\n# Freshness\n\nConfigure dbt source freshness with warn_after of 12 hours and error_after of 24 hours for daily\nsources. Freshness checks should run before the main dbt build."
   },
   {
    "page": 2,
    "text": "# Validity\n\nUse accepted_values tests for status columns (for example order status must be one of placed,\nshipped, completed, returned). Use relationships tests to make sure foreign keys exist in the parent\ntable.\n\n\n# Monitoring and ownership\n\nEach pipeline must have a named owner, an alert channel, and a runbook link. Failed data quality\nchecks block downstream models from running.\n\n\n# Sign-off\n\nThe pipeline can be promoted to production only when all checks pass in the staging environment\nfor three consecutive days."
   }
  ]
 },
 {
  "filename": "data_warehouse_layers.md",
  "file_type": "md",
  "size_bytes": 1741,
  "pages": [
   {
    "page": null,
    "text": "# Data Warehouse Layers: Raw, Staging, Intermediate, Marts\n\nOur warehouse is organised in layers. Each layer has one job, which keeps transformations easy to\nunderstand, test and debug.\n\n## Raw layer\n\nData loaded as-is from source systems (databases, APIs, files). No business logic is applied.\nThe raw layer is the \"source of truth\" copy and makes it possible to rebuild everything downstream.\n\n## Staging layer\n\nThe **purpose of the staging layer** is to clean and standardize raw data **one source table at a\ntime**, so that every downstream model starts from consistent, well-named data. Typical staging\nwork:\n\n- Renaming columns to a consistent naming convention (e.g. `snake_case`, `customer_id`).\n- Casting data types (strings to dates, cents to decimal amounts).\n- Basic cleaning: trimming whitespace, standardizing booleans and null values.\n- Deduplicating records from the source.\n\nStaging models do **not** join different sources or apply business rules. In dbt they are usually\nnamed `stg_<source>__<table>` and materialized as views.\n\n## Intermediate layer\n\nIntermediate models join and reshape staging models to prepare reusable building blocks, for\nexample combining orders with payments. They are not exposed to business users.\n\n## Marts layer\n\nMarts contain business-ready **fact** and **dimension** tables (for example `fct_orders`,\n`dim_customers`) used by dashboards and analysts. They are usually materialized as tables or\nincremental models for performance.\n\n## Why layers matter\n\n- **Debugging**: when a number is wrong, you can check each layer in order.\n- **Reuse**: many marts can build on the same staging models.\n- **Testing**: tests can be added at each layer (e.g. unique and not_null on staging primary keys).\n"
   }
  ]
 },
 {
  "filename": "dbt_incremental_models.md",
  "file_type": "md",
  "size_bytes": 2219,
  "pages": [
   {
    "page": null,
    "text": "# dbt Incremental Models – Team Guide\n\n## What is an incremental model?\n\nAn incremental model is a dbt model that, after its first run, only processes **new or changed\nrows** instead of rebuilding the entire table. On the first run (or with `--full-refresh`) dbt\nbuilds the whole table. On later runs dbt inserts or merges only the rows selected by the\nincremental filter. This makes large fact tables much faster and cheaper to build.\n\n## How to configure one\n\nSet the materialization in the model's config block:\n\n```sql\n{{ config(\n    materialized = 'incremental',\n    unique_key   = 'order_id',\n    incremental_strategy = 'merge'\n) }}\n```\n\n- `materialized='incremental'` turns the model into an incremental model.\n- `unique_key` tells dbt which column identifies a row, so updated rows are merged instead of duplicated.\n- `incremental_strategy` controls how new data is applied. On Snowflake the default is `merge`;\n  other options include `append`, `delete+insert` and `insert_overwrite` (adapter dependent).\n\n## The is_incremental() macro\n\nInside the model, wrap the filter for new rows in `is_incremental()`. The macro returns true only\nwhen the target table already exists, the model is materialized as incremental, and the run is not\na full refresh.\n\n```sql\nselect * from {{ ref('stg_orders') }}\n{% if is_incremental() %}\n  where updated_at > (select max(updated_at) from {{ this }})\n{% endif %}\n```\n\n`{{ this }}` refers to the existing target table in the warehouse.\n\n## When to use incremental models\n\n- Event or log tables with millions of rows that grow every day.\n- Fact tables where only recent data changes.\n- When a full rebuild takes too long or costs too many warehouse credits.\n\nAvoid incremental models for small tables – a simple `table` materialization is easier to maintain.\n\n## Common problems\n\n- **Duplicates**: usually caused by a missing or non-unique `unique_key`.\n- **Missed late-arriving data**: if records arrive late, filter with a lookback window,\n  e.g. `updated_at > dateadd(day, -3, (select max(updated_at) from {{ this }}))`.\n- **Schema changes**: new columns are ignored by default. Use `on_schema_change='append_new_columns'`\n  or run `dbt run --full-refresh -s model_name`.\n"
   }
  ]
 },
 {
  "filename": "fct_orders.sql",
  "file_type": "sql",
  "size_bytes": 976,
  "pages": [
   {
    "page": null,
    "text": "-- fct_orders.sql\n-- Mart model: one row per order with payment totals.\n-- Materialized incrementally so only new or updated orders are processed on each run.\n\n{{ config(\n    materialized = 'incremental',\n    unique_key   = 'order_id',\n    incremental_strategy = 'merge',\n    on_schema_change = 'append_new_columns'\n) }}\n\nwith orders as (\n\n    select * from {{ ref('stg_shop__orders') }}\n\n    {% if is_incremental() %}\n      -- 3-day lookback window to catch late-arriving updates\n      where updated_at > dateadd(day, -3, (select max(updated_at) from {{ this }}))\n    {% endif %}\n\n),\n\npayments as (\n\n    select\n        order_id,\n        sum(amount) as total_paid\n    from {{ ref('stg_shop__payments') }}\n    where status = 'success'\n    group by order_id\n\n)\n\nselect\n    orders.order_id,\n    orders.customer_id,\n    orders.order_date,\n    orders.status,\n    coalesce(payments.total_paid, 0) as total_paid,\n    orders.updated_at\nfrom orders\nleft join payments using (order_id)\n"
   }
  ]
 },
 {
  "filename": "pipeline_troubleshooting_guide.txt",
  "file_type": "txt",
  "size_bytes": 2308,
  "pages": [
   {
    "page": null,
    "text": "DATA PIPELINE TROUBLESHOOTING GUIDE\n===================================\n\nUse this runbook when a scheduled data pipeline fails or produces wrong data.\n\nSTEP 1 - CHECK THE ORCHESTRATOR\nOpen the orchestrator (for example Airflow) and find the failed run. Note which task failed,\nthe start time, and the error message in the task log. Check whether upstream tasks succeeded.\n\nSTEP 2 - CLASSIFY THE FAILURE\nMost failures fall into one of these groups:\n  - Source issues: the source system was down, files arrived late, or credentials expired.\n  - Schema changes: a column was renamed, removed or changed type in the source.\n  - Data quality issues: nulls in a NOT NULL column, duplicates in a primary key,\n    or a failed dbt test (unique, not_null, accepted_values, relationships).\n  - Resource issues: warehouse timeout, out-of-memory, or query queueing.\n  - Code issues: a recent deployment introduced a SQL or Python bug.\n\nSTEP 3 - REPRODUCE AND FIX\nRe-run the failed task in a development environment with the same inputs.\nFor dbt failures, run \"dbt build --select model_name\" and read the compiled SQL in the target/ folder.\nFor schema changes, update the staging model and any downstream tests.\nFor resource issues, check query history for long-running queries and consider a larger warehouse\nor adding filters / clustering.\n\nSTEP 4 - BACKFILL\nAfter the fix, backfill the missed time window. Make sure the pipeline is idempotent:\nrunning it twice for the same window must not create duplicates. Incremental models with a\nunique_key and merge strategy help with this.\n\nSTEP 5 - PREVENT RECURRENCE\n  - Add a dbt test or data quality check that would have caught the issue.\n  - Add alerting (Slack or email) on task failure and on freshness checks (dbt source freshness).\n  - Write a short post-incident note: what failed, impact, root cause, fix, follow-up actions.\n\nCOMMON QUICK CHECKS\n  - Did credentials or API tokens expire?\n  - Is the source file present and complete (row counts compared with yesterday)?\n  - Are there locks or long-running transactions on the target table?\n  - Was a Snowflake task left suspended after a deployment?\n\nESCALATION\nIf the issue affects a business-critical dashboard and cannot be fixed within 2 hours,\nnotify the data platform on-call engineer and the dashboard owner.\n"
   }
  ]
 },
 {
  "filename": "snowflake_streams_and_tasks.md",
  "file_type": "md",
  "size_bytes": 2393,
  "pages": [
   {
    "page": null,
    "text": "# Snowflake Streams and Tasks – Internal Notes\n\n## Streams\n\nA **stream** is a Snowflake object that records **change data capture (CDC)** information for a\ntable: the rows that were inserted, updated or deleted since the stream was last consumed.\nA stream does not copy the data. It stores an offset (a point in the table's version history) and\nreturns the changes between that offset and the current table version.\n\nEach row returned by a stream includes extra metadata columns:\n\n- `METADATA$ACTION` – `INSERT` or `DELETE` (an update appears as a DELETE plus an INSERT).\n- `METADATA$ISUPDATE` – `TRUE` when the row is part of an update.\n- `METADATA$ROW_ID` – a unique, stable id for the row.\n\n```sql\ncreate or replace stream raw_orders_stream on table raw.orders;\n```\n\nWhen a DML statement (for example `INSERT INTO ... SELECT FROM raw_orders_stream`) consumes the\nstream inside a committed transaction, the offset moves forward and those changes are no longer\nreturned.\n\nStream types: **standard** (inserts, updates, deletes), **append-only** (inserts only, cheaper,\ngood for staging tables that only receive new rows) and **insert-only** (for external tables).\n\nA stream can become **stale** if it is not consumed within the table's data retention period.\nA stale stream must be recreated.\n\n## Tasks\n\nA **task** runs a SQL statement or stored procedure on a schedule (CRON or interval) or after\nanother task finishes. Tasks can be chained into a **task graph (DAG)** with a root task.\n\n```sql\ncreate or replace task load_orders_task\n  warehouse = transform_wh\n  schedule  = '5 minute'\nwhen\n  system$stream_has_data('raw_orders_stream')\nas\n  insert into analytics.orders select * from raw_orders_stream;\n\nalter task load_orders_task resume;   -- tasks are created suspended\n```\n\n## Streams + Tasks together\n\nCombining a stream with a task creates a simple continuous ELT pipeline: the stream captures the\nchanges, and the task periodically processes them. The `WHEN system$stream_has_data(...)`\ncondition skips the run when there are no changes, which saves warehouse credits.\n\n## Monitoring\n\n- `show tasks;` – lists tasks and their state (started/suspended).\n- `select * from table(information_schema.task_history()) order by scheduled_time desc;`\n  shows recent runs, errors and durations.\n- Remember: a newly created task is **suspended** until you run `alter task ... resume`.\n"
   }
  ]
 }
];
