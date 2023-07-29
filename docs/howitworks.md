SQLreduce: Reduce verbose SQL queries to minimal examples
=========================================================

![SQLreduce logo](sqlreduce.png)

Developers often face very large SQL queries that raise some error. SQLreduce
is a tool to reduce that complexity to a minimal query.

## SQLsmith generates random SQL queries

[SQLsmith](https://github.com/anse1/sqlsmith) is a tool that generates random SQL
queries and runs them against a PostgreSQL server (and other DBMS types). The
idea is that by fuzz-testing the query parser and executor, corner-case bugs
can be found that would otherwise go unnoticed in manual testing or with the
fixed set of test cases in PostgreSQL's regression test suite. It has proven to
be an
[effective tool](https://github.com/anse1/sqlsmith/wiki#score-list)
with over 100 bugs found in different areas in the PostgreSQL server and
other products since 2015, including security bugs, ranging from executor
bugs to segfaults in type and index method implementations.
For example, in 2018, SQLsmith found that the following query
[triggered a segfault in PostgreSQL](https://www.postgresql.org/message-id/flat/87woxi24uw.fsf%40ansel.ydns.eu):

```
select
  case when pg_catalog.lastval() < pg_catalog.pg_stat_get_bgwriter_maxwritten_clean() then case when pg_catalog.circle_sub_pt(
          cast(cast(null as circle) as circle),
          cast((select location from public.emp limit 1 offset 13)
             as point)) ~ cast(nullif(case when cast(null as box) &> (select boxcol from public.brintest limit 1 offset 2)
                 then (select f1 from public.circle_tbl limit 1 offset 4)
               else (select f1 from public.circle_tbl limit 1 offset 4)
               end,
          case when (select pg_catalog.max(class) from public.f_star)
                 ~~ ref_0.c then cast(null as circle) else cast(null as circle) end
            ) as circle) then ref_0.a else ref_0.a end
       else case when pg_catalog.circle_sub_pt(
          cast(cast(null as circle) as circle),
          cast((select location from public.emp limit 1 offset 13)
             as point)) ~ cast(nullif(case when cast(null as box) &> (select boxcol from public.brintest limit 1 offset 2)
                 then (select f1 from public.circle_tbl limit 1 offset 4)
               else (select f1 from public.circle_tbl limit 1 offset 4)
               end,
          case when (select pg_catalog.max(class) from public.f_star)
                 ~~ ref_0.c then cast(null as circle) else cast(null as circle) end
            ) as circle) then ref_0.a else ref_0.a end
       end as c0,
  case when (select intervalcol from public.brintest limit 1 offset 1)
         >= cast(null as "interval") then case when ((select pg_catalog.max(roomno) from public.room)
             !~~ ref_0.c)
        and (cast(null as xid) <> 100) then ref_0.b else ref_0.b end
       else case when ((select pg_catalog.max(roomno) from public.room)
             !~~ ref_0.c)
        and (cast(null as xid) <> 100) then ref_0.b else ref_0.b end
       end as c1,
  ref_0.a as c2,
  (select a from public.idxpart1 limit 1 offset 5) as c3,
  ref_0.b as c4,
    pg_catalog.stddev(
      cast((select pg_catalog.sum(float4col) from public.brintest)
         as float4)) over (partition by ref_0.a,ref_0.b,ref_0.c order by ref_0.b) as c5,
  cast(nullif(ref_0.b, ref_0.a) as int4) as c6, ref_0.b as c7, ref_0.c as c8
from
  public.mlparted3 as ref_0
where true;
```

However, just like in this 40-line, 2.2kB example, the random queries generated
by SQLsmith that trigger some error are most often very large and contain a lot
of noise that does not contribute to the error. So far, manual inspection of
the query and tedious editing was required to reduce the example to a minimal
reproducer that developers can use to fix the problem.

## Reduce complexity with SQLreduce

This issue is solved by [SQLreduce](https://github.com/df7cb/sqlreduce).
SQLreduce takes as input an arbitrary SQL query which is then run against a
PostgreSQL server. Various simplification steps are applied, checking after
each step that the simplified query still triggers the same error from
PostgreSQL. The end result is a SQL query with minimal complexity.

SQLreduce is effective at reducing the queries from
[original error reports from SQLsmith](https://github.com/anse1/sqlsmith/wiki#score-list)
to queries that match manually-reduced queries. For example, SQLreduce can
effectively reduce the above monster query to just this:

```
SELECT pg_catalog.stddev(NULL) OVER () AS c5 FROM public.mlparted3 AS ref_0
```

Note that SQLreduce does not try to derive a query that is semantically identical
to the original, or produces the same query result - the input is assumed to be
faulty, and we are looking for the minimal query that produces the same error
message from PostgreSQL when run against a database. If the input query happens
to produce no error, the minimal query output by SQLreduce will just be
`SELECT`.

## How it works

We'll use a simpler query to demonstrate how SQLreduce works and which steps
are taken to remove noise from the input. The query is bogus and contains a bit
of clutter that we want to remove:

```
$ psql -c 'select pg_database.reltuples / 1000 from pg_database, pg_class where 0 < pg_database.reltuples / 1000 order by 1 desc limit 10'
ERROR:  column pg_database.reltuples does not exist
```

Let's pass the query to SQLreduce:

```
$ sqlreduce 'select pg_database.reltuples / 1000 from pg_database, pg_class where 0 < pg_database.reltuples / 1000 order by 1 desc limit 10'
```

SQLreduce starts by parsing the input using
[pglast](https://github.com/lelit/pglast) and
[libpg_query](https://github.com/pganalyze/libpg_query) which expose the
original PostgreSQL parser as a library with Python bindings. The result is a
parse tree that is the basis for the next steps.
The parse tree looks like this:

```
selectStmt
├── targetList
│   └── /
│       ├── pg_database.reltuples
│       └── 1000
├── fromClause
│   ├── pg_database
│   └── pg_class
├── whereClause
│   └── <
│       ├── 0
│       └── /
│           ├── pg_database.reltuples
│           └── 1000
├── orderClause
│   └── 1
└── limitCount
    └── 10
```

Pglast also contains a query renderer that can render back the parse tree as
SQL, shown as the regenerated query below. The input query is run against
PostgreSQL to determine the result, in this case
`ERROR:  column pg_database.reltuples does not exist`.

```
Input query: select pg_database.reltuples / 1000 from pg_database, pg_class where 0 < pg_database.reltuples / 1000 order by 1 desc limit 10
Regenerated: SELECT pg_database.reltuples / 1000 FROM pg_database, pg_class WHERE 0 < ((pg_database.reltuples / 1000)) ORDER BY 1 DESC LIMIT 10
Query returns: ✔ ERROR:  column pg_database.reltuples does not exist
```

SQLreduce works by deriving new parse trees that are structurally simpler,
generating SQL from that, and run these queries against the database. The first
simplification steps work on the top level node, where SQLreduce tries to
remove whole subtrees to quickly find a result. The first reduction tried is to
remove `LIMIT 10`:

```
SELECT pg_database.reltuples / 1000 FROM pg_database, pg_class WHERE 0 < ((pg_database.reltuples / 1000)) ORDER BY 1 DESC ✔
```

The query result is still `ERROR:  column pg_database.reltuples does not
exist`, indicated by a ✔ check mark. Next, `ORDER BY 1` is removed, again
successfully:

```
SELECT pg_database.reltuples / 1000 FROM pg_database, pg_class WHERE 0 < ((pg_database.reltuples / 1000)) ✔
```

Now the entire target list is removed:

```
SELECT FROM pg_database, pg_class WHERE 0 < ((pg_database.reltuples / 1000)) ✔
```

This shorter query is still equivalent to the original regarding the error
message returned when it is run against the database. Now the first unsuccessful
reduction step is tried, removing the entire `FROM` clause:

```
SELECT WHERE 0 < ((pg_database.reltuples / 1000)) ✘ ERROR:  missing FROM-clause entry for table "pg_database"
```

That query is also faulty, but triggers a different error message, so the
previous parse tree is kept for the next steps. Again a whole subtree is
removed, now the `WHERE` clause:

```
SELECT FROM pg_database, pg_class ✘ no error
```

We have now reduced the input query so much that it doesn't error out any more. The previous parse tree
is still kept which now looks like this:

```
selectStmt
├── fromClause
│   ├── pg_database
│   └── pg_class
└── whereClause
    └── <
        ├── 0
        └── /
            ├── pg_database.reltuples
            └── 1000
```

Now SQLreduce starts digging into the tree. There are several entries in the
`FROM` clause, so it tries to shorten the list. First, `pg_database` is
removed, but that doesn't work, so `pg_class` is removed:

```
SELECT FROM pg_class WHERE 0 < ((pg_database.reltuples / 1000)) ✘ ERROR:  missing FROM-clause entry for table "pg_database"
SELECT FROM pg_database WHERE 0 < ((pg_database.reltuples / 1000)) ✔
```

Since we have found a new minimal query, recursion restarts at top-level with
another try to remove the `WHERE` clause. Since that doesn't work, it tries to
replace the expression with `NULL`, but that doesn't work either.

```
SELECT FROM pg_database ✘ no error
SELECT FROM pg_database WHERE NULL ✘ no error
```

Now a new kind of step is tried: expression pull-up. We descend into `WHERE`
clause, where we replace `A < B` first by `A` and then by `B`.

```
SELECT FROM pg_database WHERE 0 ✘ ERROR:  argument of WHERE must be type boolean, not type integer
SELECT FROM pg_database WHERE pg_database.reltuples / 1000 ✔
SELECT WHERE pg_database.reltuples / 1000 ✘ ERROR:  missing FROM-clause entry for table "pg_database"
```

The first try did not work, but the second one did. Since we simplified the
query, we restart at top-level to check if the `FROM` clause can be removed,
but it is still required.

From `A / B`, we can again pull up `A`:

```
SELECT FROM pg_database WHERE pg_database.reltuples ✔
SELECT WHERE pg_database.reltuples ✘ ERROR:  missing FROM-clause entry for table "pg_database"
```

SQLreduce has found the minimal query that still raises `ERROR:  column
pg_database.reltuples does not exist` with this parse tree:

```
selectStmt
├── fromClause
│   └── pg_database
└── whereClause
    └── pg_database.reltuples
```

At the end of the run, the query is printed along with some statistics:

```
Minimal query yielding the same error:
SELECT FROM pg_database WHERE pg_database.reltuples

Pretty-printed minimal query:
SELECT
FROM pg_database
WHERE pg_database.reltuples

Seen: 15 items, 915 Bytes
Iterations: 19
Runtime: 0.107 s, 139.7 q/s
```

This minimal query can now be inspected to fix the bug in PostgreSQL or in the
application.
