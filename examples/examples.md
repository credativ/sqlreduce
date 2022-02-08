# Planner error on lateral joins

* URL: https://www.postgresql.org/message-id/87blfgqa4t.fsf@aurora.ydns.eu
* Fix: http://git.postgresql.org/pg/commitdiff/b1738ff6ab73203cbbc02d7fb82941dbc061d301

Original query: ERROR:  XX000: failed to build any 6-way joins
```
SELECT *
FROM (SELECT sample_1.a AS c0
      FROM fkpart5.fk2 AS sample_1) AS subq_0,
     LATERAL (SELECT 1
              FROM (SELECT subq_0.c0 AS c3,
                           subq_5.c0 AS c7,
                           sample_2.b AS c9
                    FROM public.brin_test AS sample_2,
                         LATERAL (SELECT subq_3.c1 AS c0
                                  FROM fkpart5.pk3 AS sample_3,
                                       LATERAL (SELECT sample_2.a AS c0,
                                                       sample_3.a AS c1
                                                FROM public.rtest_interface AS ref_0) AS subq_1,
                                       LATERAL (SELECT subq_1.c1 AS c1
                                                FROM public.alter_table_under_transition_tables AS ref_1) AS subq_3) AS subq_5) AS subq_6
                   RIGHT JOIN public.gtest30_1 AS sample_6 ON TRUE
              WHERE subq_6.c7 = subq_6.c3) AS subq_7
```

Reduced query using --sqlstate: ERROR:  XX000: failed to build any 4-way joins
```
SELECT
FROM (SELECT sample_1.a AS c0
      FROM fkpart5.fk2 AS sample_1) AS subq_0,
     LATERAL (SELECT
              FROM (SELECT subq_0.c0 AS c3,
                           subq_5.c0 AS c7
                    FROM LATERAL (SELECT subq_3.c1 AS c0
                                  FROM fkpart5.pk3 AS sample_3,
                                       LATERAL (SELECT sample_3.a AS c1) AS subq_1,
                                       LATERAL (SELECT subq_1.c1
                                                FROM public.alter_table_under_transition_tables AS ref_1) AS subq_3) AS subq_5) AS subq_6
                   RIGHT JOIN public.gtest30_1 AS sample_6 ON NULL
              WHERE subq_6.c7 = subq_6.c3) AS subq_7

Seen: 222 items, 95545 Bytes
Iterations: 281
Runtime: 1.718 s, 129.2 q/s
```


# parallel worker errors "subplan ... was not initialized"

* URL: https://www.postgresql.org/message-id/87v9doorz7.fsf@aurora.ydns.eu
* Fix: https://git.postgresql.org/gitweb/?p=postgresql.git;a=commitdiff;h=86b7cca72d4d0a4e043fac0a2cdd56218ff2f258

Original query: ERROR:  subplan "InitPlan 3 (returns $3)" was not initialized
```
SET min_parallel_table_scan_size TO '8kB';

SET parallel_setup_cost TO 1;

SELECT sample_0.a AS c0,
       sample_0.a AS c1,
       pg_catalog.pg_stat_get_bgwriter_requested_checkpoints() AS c2,
       sample_0.b AS c3
FROM public.itest6 AS sample_0
WHERE EXISTS (SELECT CAST(COALESCE(CAST((NULLIF(sample_1.z, sample_1.x)) AS int4),
                                   sample_1.x) AS int4) AS c0,
                     pg_catalog.macaddr_cmp(CAST(CASE
                                                   WHEN (FALSE)
                                                     THEN CAST((NULL) AS macaddr)
                                                   ELSE CAST((NULL) AS macaddr)
                                                 END AS macaddr),
                                            CAST(CAST((NULL) AS macaddr) AS macaddr)) AS c1
              FROM public.insert_tbl AS sample_1
              WHERE (SELECT timestamptzcol
                     FROM public.brintest
                     LIMIT 1
                     OFFSET 29) < pg_catalog.date_larger(CAST(((SELECT d
                                                                FROM public.nv_child_2011
                                                                LIMIT 1
                                                                OFFSET 6)) AS date),
                                                         CAST(((SELECT pg_catalog.min(filler3)
                                                                FROM public.mcv_lists)) AS date)))
```

Reduced query:
```
SET min_parallel_table_scan_size TO '8kB';

SET parallel_setup_cost TO 1;

SELECT
WHERE EXISTS (SELECT
              FROM public.insert_tbl AS sample_1
              WHERE (SELECT timestamptzcol
                     FROM public.brintest
                     LIMIT 1) < pg_catalog.date_larger((SELECT d
                                                        FROM public.nv_child_2011),
                                                       (SELECT pg_catalog.min(filler3)
                                                        FROM public.mcv_lists)))

Seen: 103 items, 31796 Bytes
Iterations: 145
Runtime: 0.775 s, 132.9 q/s
```

Reduced query using --sqlstate: XX000: subplan "InitPlan 2 (returns $2)" was not initialized
```
SET min_parallel_table_scan_size TO '8kB';

SET parallel_setup_cost TO 1;

SELECT
WHERE EXISTS (SELECT
              FROM public.insert_tbl AS sample_1
              WHERE (SELECT timestamptzcol
                     FROM public.brintest
                     LIMIT 1) < (SELECT pg_catalog.min(filler3)
                                 FROM public.mcv_lists))

Seen: 67 items, 19940 Bytes
Iterations: 88
Runtime: 0.491 s, 136.5 q/s
```


# right join with partitioned table crash

* URL: https://www.postgresql.org/message-id/20210915230959.GB17635%40ahch-to
* Fix: https://git.postgresql.org/gitweb/?p=postgresql.git;a=commitdiff;h=a21049fd3f64518c8a7227cf07c56f2543241db2

Original query: server closed the connection unexpectedly
```
DROP TABLE IF EXISTS fkpart3_pk5 CASCADE;

DROP TABLE IF EXISTS inet_tbl;

CREATE TABLE fkpart3_pk5 (
  a integer NOT NULL PRIMARY KEY
) PARTITION BY range (a);

CREATE TABLE fkpart3_pk51 PARTITION OF fkpart3_pk5
  FOR VALUES FROM (4000) TO (4500);

CREATE TABLE inet_tbl (
  c cidr,
  i inet
);

SELECT 1 AS c0
FROM (SELECT CAST(NULL AS integer) AS c9,
             ref_0.a AS c24
      FROM fkpart3_pk5 AS ref_0) AS subq_0
     RIGHT JOIN public.inet_tbl AS sample_0 ON CAST((NULL) AS cidr) = c
WHERE subq_0.c9 <= subq_0.c24
```

Reduced query:
```
DROP TABLE IF EXISTS inet_tbl;

CREATE TABLE fkpart3_pk5 (
  a integer NOT NULL PRIMARY KEY
) PARTITION BY range (a);

CREATE TABLE fkpart3_pk51 PARTITION OF fkpart3_pk5
  FOR VALUES FROM (4000) TO (4500);

CREATE TABLE inet_tbl (
  c cidr,
  i inet
);

SELECT
FROM (SELECT CAST(NULL AS integer) AS c9,
             ref_0.a AS c24
      FROM fkpart3_pk5 AS ref_0) AS subq_0
     RIGHT JOIN public.inet_tbl AS sample_0 ON NULL
WHERE subq_0.c9 <= subq_0.c24

Seen: 44 items, 16777 Bytes
Iterations: 52
Runtime: 8.896 s, 4.9 q/s
```


# Failed assertion during partition pruning

* URL: https://www.postgresql.org/message-id/flat/87sg8tqhsl.fsf%40aurora.ydns.eu
* PostgreSQL git hash: 3df51ca8

Original query:
```
SELECT myaggp05a(a) OVER (PARTITION BY a
                          ORDER BY a)
FROM trigger_parted
WHERE pg_trigger_depth() <> a
LIMIT 40
```

Reduced query:
```
SELECT myaggp05a(NULL) OVER (ORDER BY a)
FROM trigger_parted
WHERE pg_trigger_depth() <> a
LIMIT 40
```

Query manually reduced by Tom Lane:
```
SELECT a
FROM trigger_parted
WHERE pg_trigger_depth() <> a
ORDER BY a
LIMIT 40
```

Query further reduced by sqlreduce:
```
SELECT
FROM trigger_parted
WHERE pg_trigger_depth() <> a
ORDER BY a
LIMIT 40
```
