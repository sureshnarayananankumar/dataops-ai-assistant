# Data Warehouse Layers: Raw, Staging, Intermediate, Marts

Our warehouse is organised in layers. Each layer has one job, which keeps transformations easy to
understand, test and debug.

## Raw layer

Data loaded as-is from source systems (databases, APIs, files). No business logic is applied.
The raw layer is the "source of truth" copy and makes it possible to rebuild everything downstream.

## Staging layer

The **purpose of the staging layer** is to clean and standardize raw data **one source table at a
time**, so that every downstream model starts from consistent, well-named data. Typical staging
work:

- Renaming columns to a consistent naming convention (e.g. `snake_case`, `customer_id`).
- Casting data types (strings to dates, cents to decimal amounts).
- Basic cleaning: trimming whitespace, standardizing booleans and null values.
- Deduplicating records from the source.

Staging models do **not** join different sources or apply business rules. In dbt they are usually
named `stg_<source>__<table>` and materialized as views.

## Intermediate layer

Intermediate models join and reshape staging models to prepare reusable building blocks, for
example combining orders with payments. They are not exposed to business users.

## Marts layer

Marts contain business-ready **fact** and **dimension** tables (for example `fct_orders`,
`dim_customers`) used by dashboards and analysts. They are usually materialized as tables or
incremental models for performance.

## Why layers matter

- **Debugging**: when a number is wrong, you can check each layer in order.
- **Reuse**: many marts can build on the same staging models.
- **Testing**: tests can be added at each layer (e.g. unique and not_null on staging primary keys).
