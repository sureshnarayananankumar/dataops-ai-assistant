# Snowflake Streams and Tasks – Internal Notes

## Streams

A **stream** is a Snowflake object that records **change data capture (CDC)** information for a
table: the rows that were inserted, updated or deleted since the stream was last consumed.
A stream does not copy the data. It stores an offset (a point in the table's version history) and
returns the changes between that offset and the current table version.

Each row returned by a stream includes extra metadata columns:

- `METADATA$ACTION` – `INSERT` or `DELETE` (an update appears as a DELETE plus an INSERT).
- `METADATA$ISUPDATE` – `TRUE` when the row is part of an update.
- `METADATA$ROW_ID` – a unique, stable id for the row.

```sql
create or replace stream raw_orders_stream on table raw.orders;
```

When a DML statement (for example `INSERT INTO ... SELECT FROM raw_orders_stream`) consumes the
stream inside a committed transaction, the offset moves forward and those changes are no longer
returned.

Stream types: **standard** (inserts, updates, deletes), **append-only** (inserts only, cheaper,
good for staging tables that only receive new rows) and **insert-only** (for external tables).

A stream can become **stale** if it is not consumed within the table's data retention period.
A stale stream must be recreated.

## Tasks

A **task** runs a SQL statement or stored procedure on a schedule (CRON or interval) or after
another task finishes. Tasks can be chained into a **task graph (DAG)** with a root task.

```sql
create or replace task load_orders_task
  warehouse = transform_wh
  schedule  = '5 minute'
when
  system$stream_has_data('raw_orders_stream')
as
  insert into analytics.orders select * from raw_orders_stream;

alter task load_orders_task resume;   -- tasks are created suspended
```

## Streams + Tasks together

Combining a stream with a task creates a simple continuous ELT pipeline: the stream captures the
changes, and the task periodically processes them. The `WHEN system$stream_has_data(...)`
condition skips the run when there are no changes, which saves warehouse credits.

## Monitoring

- `show tasks;` – lists tasks and their state (started/suspended).
- `select * from table(information_schema.task_history()) order by scheduled_time desc;`
  shows recent runs, errors and durations.
- Remember: a newly created task is **suspended** until you run `alter task ... resume`.
