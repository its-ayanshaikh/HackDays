"""
TPC-H schema context for the LLM.

This description is injected into the SQL-generation prompt so Cortex knows
exactly which tables, columns and join keys exist. Keeping it accurate is the
single biggest lever for text-to-SQL accuracy.

The TPC-H sample dataset ships free with every Snowflake account under
SNOWFLAKE_SAMPLE_DATA.TPCH_SF1. It models a wholesale supplier's orders.
Order dates range from 1992-01-01 to 1998-08-02.
"""

SCHEMA_CONTEXT = """
DATABASE.SCHEMA: SNOWFLAKE_SAMPLE_DATA.TPCH_SF1
Domain: a wholesale supplier — customers place orders, orders contain line
items of parts supplied by suppliers. Order dates span 1992 to 1998.

TABLES AND COLUMNS:

REGION(R_REGIONKEY, R_NAME, R_COMMENT)
  - 5 world regions (e.g. 'ASIA', 'EUROPE', 'AMERICA').

NATION(N_NATIONKEY, N_NAME, N_REGIONKEY, N_COMMENT)
  - 25 nations. N_REGIONKEY -> REGION.R_REGIONKEY.

CUSTOMER(C_CUSTKEY, C_NAME, C_ADDRESS, C_NATIONKEY, C_PHONE, C_ACCTBAL,
         C_MKTSEGMENT, C_COMMENT)
  - C_NATIONKEY -> NATION.N_NATIONKEY.
  - C_MKTSEGMENT values include 'AUTOMOBILE','BUILDING','FURNITURE',
    'MACHINERY','HOUSEHOLD'.
  - C_ACCTBAL is the account balance.

ORDERS(O_ORDERKEY, O_CUSTKEY, O_ORDERSTATUS, O_TOTALPRICE, O_ORDERDATE,
       O_ORDERPRIORITY, O_CLERK, O_SHIPPRIORITY, O_COMMENT)
  - O_CUSTKEY -> CUSTOMER.C_CUSTKEY.
  - O_TOTALPRICE is the order total. O_ORDERDATE is a DATE (1992-1998).
  - O_ORDERSTATUS in ('O','F','P').

LINEITEM(L_ORDERKEY, L_PARTKEY, L_SUPPKEY, L_LINENUMBER, L_QUANTITY,
         L_EXTENDEDPRICE, L_DISCOUNT, L_TAX, L_RETURNFLAG, L_LINESTATUS,
         L_SHIPDATE, L_COMMITDATE, L_RECEIPTDATE, L_SHIPINSTRUCT, L_SHIPMODE,
         L_COMMENT)
  - L_ORDERKEY -> ORDERS.O_ORDERKEY.
  - L_PARTKEY -> PART.P_PARTKEY. L_SUPPKEY -> SUPPLIER.S_SUPPKEY.
  - Net revenue for a line = L_EXTENDEDPRICE * (1 - L_DISCOUNT).
  - L_SHIPMODE values include 'TRUCK','MAIL','SHIP','AIR','RAIL','FOB','REG AIR'.

PART(P_PARTKEY, P_NAME, P_MFGR, P_BRAND, P_TYPE, P_SIZE, P_CONTAINER,
     P_RETAILPRICE, P_COMMENT)

SUPPLIER(S_SUPPKEY, S_NAME, S_ADDRESS, S_NATIONKEY, S_PHONE, S_ACCTBAL,
         S_COMMENT)
  - S_NATIONKEY -> NATION.N_NATIONKEY.

PARTSUPP(PS_PARTKEY, PS_SUPPKEY, PS_AVAILQTY, PS_SUPPLYCOST, PS_COMMENT)
  - PS_PARTKEY -> PART.P_PARTKEY. PS_SUPPKEY -> SUPPLIER.S_SUPPKEY.

USEFUL NOTES:
  - "Revenue" almost always means SUM(L_EXTENDEDPRICE * (1 - L_DISCOUNT)).
  - To get revenue by customer/nation/region, join
    LINEITEM -> ORDERS -> CUSTOMER -> NATION -> REGION.
  - Use YEAR(O_ORDERDATE) to filter/group by year.
  - Fully-qualify tables as SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.<TABLE>.
"""

# A few starter questions surfaced in the UI to guide first-time users.
SAMPLE_QUESTIONS = [
    "Top 5 customers by total revenue, and which nation are they from?",
    "How did total revenue trend year by year from 1993 to 1997?",
    "Which market segment generates the most revenue?",
    "What are the top 5 nations by order value in the ASIA region?",
    "Which ship mode is used most often, and what is its average discount?",
]
