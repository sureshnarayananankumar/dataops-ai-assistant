-- fct_orders.sql
-- Mart model: one row per order with payment totals.
-- Materialized incrementally so only new or updated orders are processed on each run.

{{ config(
    materialized = 'incremental',
    unique_key   = 'order_id',
    incremental_strategy = 'merge',
    on_schema_change = 'append_new_columns'
) }}

with orders as (

    select * from {{ ref('stg_shop__orders') }}

    {% if is_incremental() %}
      -- 3-day lookback window to catch late-arriving updates
      where updated_at > dateadd(day, -3, (select max(updated_at) from {{ this }}))
    {% endif %}

),

payments as (

    select
        order_id,
        sum(amount) as total_paid
    from {{ ref('stg_shop__payments') }}
    where status = 'success'
    group by order_id

)

select
    orders.order_id,
    orders.customer_id,
    orders.order_date,
    orders.status,
    coalesce(payments.total_paid, 0) as total_paid,
    orders.updated_at
from orders
left join payments using (order_id)
