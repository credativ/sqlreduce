SQLreduce on SQLsmith bugreports
================================

https://github.com/anse1/sqlsmith/wiki#score-list

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


# Failed Assertion about PolymorphicType

* URL: https://www.postgresql.org/message-id/CAJGNTeMbhtsCUZgJJ8h8XxAJbK7U2ipsX8wkHRtZRz-NieT8RA@mail.gmail.com
* Git hash: 580a446c21

Original query:
```
SELECT pg_catalog.array_in(CAST(pg_catalog.regoperatorout(CAST((CAST((NULL) AS regoperator)) AS regoperator)) AS cstring),
                           CAST((SELECT pronamespace
                                 FROM pg_catalog.pg_proc
                                 LIMIT 1
                                 OFFSET 1) AS oid),
                           CAST(subq_1.pid AS int4)) AS c0
FROM pg_catalog.pg_stat_progress_analyze AS subq_1
```

Reduced query:
```
SELECT pg_catalog.array_in(NULL,
                           (SELECT pronamespace
                            FROM pg_catalog.pg_proc),
                           NULL)
```

# Performance issue in foreign-key-aware join estimation

* https://www.postgresql.org/message-id/87y30r8sls.fsf@ansel.ydns.eu
* 3373c7155350

Query:
```
select
    max(date_mii(now()::date, 42)) over (partition by subq_1.c9 order by c3),
    min(c3) over (partition by subq_1.c8 )
from
  (select 1 as c3 from public.partr_def2 as ref_0
            left join public.num_exp_power_10_ln as sample_0
            on (ref_0.a = sample_0.id ) ) as subq_0
    right join (select 1 as c8, 1 as c9) as subq_1
    on (true);
```

Reduced:
```
SELECT max(NULL) OVER (ORDER BY c3),
       min(NULL) OVER (PARTITION BY NULL)
FROM (SELECT NULL AS c3
      FROM public.partr_def2 AS ref_0
           LEFT JOIN public.num_exp_power_10_ln AS sample_0 ON ref_0.a = sample_0.id) AS subq_0
     RIGHT JOIN (SELECT ) AS subq_1 ON NULL
```

# Crash in mcv_get_match_bitmap

* https://www.postgresql.org/message-id/8736jdhbhc.fsf@ansel.ydns.eu
* ff597b656f

Original:
```
select filler1 from mcv_lists where a is not null and (select 42) <= c
```

Reduced:
```
SELECT FROM mcv_lists WHERE (a IS NOT NULL) AND ((SELECT 42) <= c)
```

# Assert failed in snprintf.c

* https://www.postgresql.org/message-id/CAJGNTeP=-6Gyqq5TN9OvYEydi7Fv1oGyYj650LGTnW44oAzYCg@mail.gmail.com
* a6949ca34d3aca018870815cf6cb690024aeea04

Original:
```
select
  sample_0.a as c0,
  pg_catalog.has_column_privilege(
    cast(pg_catalog.pg_my_temp_schema() as oid),
    cast(sample_0.b as text),
    cast(sample_0.b as text)) as c1,
  (select slcolor from public.shoe_data limit 1 offset 5)
     as c2,

    pg_catalog.array_agg(
      cast(pg_catalog.pg_rotate_logfile() as anynonarray)) over (partition by sample_0.a,sample_0.b,sample_0.a,sample_0.b,sample_0.a order by sample_0.a) as c3
from
  public.rtest_nothn1 as sample_0 tablesample bernoulli (6.7)
where sample_0.b <= sample_0.b
```

# Assert failed in snprintf.c

* https://www.postgresql.org/message-id/CAJGNTeP=-6Gyqq5TN9OvYEydi7Fv1oGyYj650LGTnW44oAzYCg@mail.gmail.com
* Tested on e27453bd83

Original query contains TABLESAMPLE and doesn't always crash.
TABLESAMPLE removed manually

Original:
```
select
  sample_0.a as c0,
  pg_catalog.has_column_privilege(
    cast(pg_catalog.pg_my_temp_schema() as oid),
    cast(sample_0.b as text),
    cast(sample_0.b as text)) as c1,
  (select slcolor from public.shoe_data limit 1 offset 5)
     as c2,

    pg_catalog.array_agg(
      cast(pg_catalog.pg_rotate_logfile() as anynonarray)) over (partition by sample_0.a,sample_0.b,sample_0.a,sample_0.b,sample_0.a order by sample_0.a) as c3
from
  public.rtest_nothn1 as sample_0 tablesample bernoulli (6.7)
where sample_0.b <= sample_0.b
```

Query without tablesample:
```
select
  sample_0.a as c0,
  pg_catalog.has_column_privilege(
    cast(pg_catalog.pg_my_temp_schema() as oid),
    cast(sample_0.b as text),
    cast(sample_0.b as text)) as c1,
  (select slcolor from public.shoe_data limit 1 offset 5)
     as c2,

    pg_catalog.array_agg(
      cast(pg_catalog.pg_rotate_logfile() as anynonarray)) over (partition by sample_0.a,sample_0.b,sample_0.a,sample_0.b,sample_0.a order by sample_0.a) as c3
from
  public.rtest_nothn1 as sample_0
where sample_0.b <= sample_0.b
```

Reduced:
```
SELECT pg_catalog.has_column_privilege(pg_catalog.pg_my_temp_schema(),
                                       sample_0.b,
                                       sample_0.b)
FROM public.rtest_nothn1 AS sample_0
```

# ERROR: plan should not reference subplan's variable

* https://www.postgresql.org/message-id/87va8g7vq0.fsf@ansel.ydns.eu
* 1b9d1b08fe

Original:
```
delete from public.prt1_l
where
EXISTS (
  select
    from
      public.xmltest as ref_10 ,
      lateral (select
            ref_10.data as c0
          from
            public.radix_text_tbl as ref_0,
            lateral (select
                  ref_11.name as c0
                from
                  public.equipment_r as ref_11
                limit 134) as subq_0
          limit 110) as subq_1
    where public.prt1_l.c is NULL)
returning 42;
```

Reduced:
```
DELETE FROM public.prt1_l
WHERE EXISTS (SELECT
              FROM public.xmltest AS ref_10,
                   LATERAL (SELECT ref_10.data) AS subq_1
              WHERE public.prt1_l.c IS NULL)
```

# ERROR: partition missing from subplans

* https://www.postgresql.org/message-id/87in4h98i0.fsf@ansel.ydns.eu
* 1b9d1b08fe

```
select * from public.fk_partitioned_fk as sample_0 tablesample system (9.4)
   inner join public.money_data as sample_1
      on ((select pg_catalog.min(int_two) from public.test_type_diff2_c3) <> sample_0.a)
    where (sample_0.b is NULL);
```

```
SELECT
FROM public.fk_partitioned_fk AS sample_0
     INNER JOIN public.money_data AS sample_1 ON (SELECT int_two
                                                  FROM public.test_type_diff2_c3) <> sample_0.a
WHERE sample_0.b IS NULL
```

# FailedAssertion on partprune

* https://www.postgresql.org/message-id/CAJGNTeOkdk%3DUVuMugmKL7M%3Dowgt4nNr1wjxMg1F%2BmHsXyLCzFA@mail.gmail.com
* 1b957e59b92dc44c14708762f882d7910463a9ac, but original error not reproducible

```
DROP TABLE IF EXISTS public.actualizar_sistema;
DROP TABLE IF EXISTS public.anexos;
DROP TABLE IF EXISTS public.radicado;

CREATE TABLE public.actualizar_sistema (
    actu_codi integer NOT NULL,
    sentencia character varying,
    sentencia_verificacion character varying,
    estado smallint DEFAULT 0,
    observacion character varying,
    svn character varying,
    num_registros_total bigint DEFAULT 0,
    num_registros_restantes bigint DEFAULT 0,
    num_registros_bloque integer DEFAULT 0
);

CREATE TABLE public.anexos (
    anex_radi_nume numeric(20,0) NOT NULL,
    anex_codigo character varying(50) NOT NULL,
    anex_tipo smallint NOT NULL,
    anex_desc character varying(512),
    anex_numero numeric(5,0) NOT NULL,
    anex_path character varying(200),
    anex_borrado character varying(1) NOT NULL,
    anex_fecha timestamp with time zone,
    anex_nombre character varying(100),
    anex_usua_codi integer,
    anex_tamano numeric,
    anex_fisico smallint DEFAULT 0,
    anex_fecha_firma timestamp with time zone,
    anex_datos_firma character varying,
    arch_codi bigint DEFAULT 0,
    arch_codi_firma bigint DEFAULT 0
);


CREATE TABLE public.radicado (
    radi_nume_temp numeric(20,0) NOT NULL,
    radi_fech_radi timestamp with time zone NOT NULL,
    radi_texto integer,
    radi_usua_ante integer,
    radi_usua_radi integer,
    radi_inst_actu integer,
    radi_imagen character varying(50)
)
PARTITION BY RANGE (radi_fech_radi);

CREATE TABLE public.radicado2012 PARTITION OF public.radicado
FOR VALUES FROM ('2012-01-01 00:00:00-05') TO ('2013-01-01 00:00:00-05');

CREATE TABLE public.radicado2013 PARTITION OF public.radicado
FOR VALUES FROM ('2013-01-01 00:00:00-05') TO ('2014-01-01 00:00:00-05')
PARTITION BY HASH (radi_inst_actu);

CREATE TABLE public.radicado2013_part00 PARTITION OF public.radicado2013
FOR VALUES WITH (modulus 2, remainder 0);

CREATE TABLE public.radicado2013_part01 PARTITION OF public.radicado2013
FOR VALUES WITH (modulus 2, remainder 1);

CREATE TABLE public.radicado2014 PARTITION OF public.radicado
FOR VALUES FROM ('2014-01-01 00:00:00-05') TO ('2015-01-01 00:00:00-05')
PARTITION BY HASH (radi_inst_actu);

CREATE TABLE public.radicado2014_part00 PARTITION OF public.radicado2014
FOR VALUES WITH (modulus 2, remainder 0);

CREATE TABLE public.radicado2014_part01 PARTITION OF public.radicado2014
FOR VALUES WITH (modulus 2, remainder 1);

CREATE TABLE public.radicado2015 PARTITION OF public.radicado
FOR VALUES FROM ('2015-01-01 00:00:00-05') TO ('2016-01-01 00:00:00-05')
PARTITION BY HASH (radi_inst_actu);

CREATE TABLE public.radicado2015_part00 PARTITION OF public.radicado2015
FOR VALUES WITH (modulus 2, remainder 0);

CREATE TABLE public.radicado2015_part01 PARTITION OF public.radicado2015
FOR VALUES WITH (modulus 2, remainder 1);

CREATE TABLE public.radicado2016 PARTITION OF public.radicado
FOR VALUES FROM ('2016-01-01 00:00:00-05') TO ('2017-01-01 00:00:00-05')
PARTITION BY HASH (radi_inst_actu);

CREATE TABLE public.radicado2016_part00 PARTITION OF public.radicado2016
FOR VALUES WITH (modulus 2, remainder 0);

CREATE TABLE public.radicado2016_part01 PARTITION OF public.radicado2016
FOR VALUES WITH (modulus 2, remainder 1);

CREATE TABLE public.radicado2017 PARTITION OF public.radicado
FOR VALUES FROM ('2017-01-01 00:00:00-05') TO ('2018-01-01 00:00:00-05');


insert into radicado
select (random() * 51245787878787878787)::numeric(20), '2012-01-01'::date + ((random()*1800) || ' days')::interval,
       random()*25000, random()*25000, random()*25000, random()*25000,md5((random()*51245787878787878787)::text)
  from generate_series(1, 1000000);

select
  (select pg_catalog.avg(actu_codi) from public.actualizar_sistema)
     as c0,
  sample_0.radi_nume_temp as c1,
  sample_0.radi_usua_ante as c2,
  (select anex_borrado from public.anexos limit 1 offset 4)
     as c3,
  pg_catalog.pg_stat_get_buf_alloc() as c4
from
  public.radicado as sample_0 tablesample bernoulli (9.7)
where (sample_0.radi_texto = cast(nullif(sample_0.radi_inst_actu, sample_0.radi_usua_radi) as int4))
   or (cast(null as jsonb) ?& case when sample_0.radi_imagen is not NULL then cast(null as _text) else cast(null as _text) end)
limit 33;
```

```
CREATE TABLE public.radicado (
  radi_nume_temp numeric(20, 0) NOT NULL,
  radi_fech_radi timestamp with time zone NOT NULL,
  radi_texto integer,
  radi_usua_ante integer,
  radi_usua_radi integer,
  radi_inst_actu integer,
  radi_imagen varchar(50)
) PARTITION BY range (radi_fech_radi);

INSERT INTO radicado
SELECT
```

# Failed assertion on pfree() via perform_pruning_combine_step

* https://www.postgresql.org/message-id/87in923lyw.fsf@ansel.ydns.eu
* 039eb6e92f

```
select
  sample_0.dd as c0,
  subq_1.c3 as c1,
  subq_1.c0 as c2,
  subq_1.c2 as c3,
  subq_1.c3 as c4,
  sample_0.bb as c5,
  subq_1.c0 as c6,
  pg_catalog.pg_current_wal_flush_lsn() as c7,
  public.func_with_bad_set() as c8,
  sample_0.bb as c9,
  sample_0.aa as c10,
  sample_0.dd as c11
from
  public.d as sample_0 tablesample bernoulli (2.8) ,
  lateral (select
	subq_0.c1 as c0,
	sample_0.aa as c1,
	subq_0.c0 as c2,
	sample_0.cc as c3,
	subq_0.c0 as c4,
	subq_0.c1 as c5
      from
	(select
	      sample_1.a as c0,
	      (select s from public.reloptions_test limit 1 offset 2)
		 as c1
	    from
	      public.pagg_tab_ml as sample_1 tablesample system (3.6)
	    where ((((select c from public.test_tbl3 limit 1 offset 2)
		       <= cast(null as test_type3))
		  or (((select n from testxmlschema.test2 limit 1 offset 1)
			 <= true)
		    or (sample_0.bb is not NULL)))
		and ((true)
		  or ((cast(null as varbit) >= (select varbitcol from public.brintest limit 1 offset 3)
			)
		    and ((select macaddrcol from public.brintest limit 1 offset 6)
			 <> cast(null as macaddr)))))
	      or ((sample_1.a is NULL)
		and ((sample_1.c is not NULL)
		  or (sample_1.c is NULL)))) as subq_0
      where (select salary from public.rtest_emp limit 1 offset 3)
	   = (select pg_catalog.min(newsal) from public.rtest_emplog)


      limit 13) as subq_1
where sample_0.aa is NULL
limit 140;
```

```
SELECT
FROM public.pagg_tab_ml AS sample_1
WHERE ((SELECT n
        FROM testxmlschema.test2)
   OR (    (sample_1.a IS NULL)
       AND ((   (sample_1.c IS NOT NULL)
             OR (sample_1.c IS NULL)))))
```

# Failed assertion in create_gather_path

* https://www.postgresql.org/message-id/87po3a3n46.fsf@ansel.ydns.eu
* 039eb6e92f

Original:
```
set min_parallel_table_scan_size to 0;
select
  66 as c0,
  ref_1.cid as c1,
    pg_catalog.min(
      cast((select timetzcol from public.brintest limit 1 offset 3)
	 as timetz)) over (partition by ref_1.name order by ref_1.name) as c2,
  ref_0.c as c3
from
  public.prt1_l as ref_0
    right join public.my_property_normal as ref_1
    on (ref_0.a <= ref_0.a)
where EXISTS (
  select
      ref_2.y as c0,
      ref_2.y as c1,
      sample_0.random as c2,
      ref_1.tel as c3,
      ref_0.a as c4,
      sample_0.random as c5,
      ref_2.y as c6,
      ref_2.x as c7,
      case when (true <> (select pg_catalog.bool_and(n) from testxmlschema.test2)
	      )
	  and (sample_0.seqno = (select int_four from public.test_type_diff2_c3 limit 1 offset 1)
	      ) then ref_2.y else ref_2.y end
	 as c8,
      sample_0.seqno as c9,
      ref_1.name as c10,
      ref_0.a as c11,
      (select nslots from public.hub limit 1 offset 2)
	 as c12,
      ref_1.name as c13
    from
      public.hash_name_heap as sample_0 tablesample system (8.2)
	left join public.tt6 as ref_2
	on ((((cast(null as tinterval) <= (select f1 from public.tinterval_tbl limit 1 offset 79)
		    )
		and (ref_2.y is not NULL))
	      or (((false)
		  and ((cast(null as tsquery) > (select keyword from public.test_tsquery limit 1 offset 34)
			)
		    or ((((select pg_catalog.jsonb_agg(sl_name) from public.shoelace_obsolete)
			     <@ cast(null as jsonb))
			or (EXISTS (
			  select
			      100 as c0,
			      ref_0.a as c1,
			      sample_0.seqno as c2,
			      ref_0.a as c3,
			      sample_0.seqno as c4,
			      ref_0.a as c5,
			      (select a from public.prt3_n limit 1 offset 30)
				 as c6,
			      ref_2.y as c7,
			      ref_1.cid as c8,
			      ref_2.y as c9
			    from
			      public.num_exp_mul as sample_1 tablesample system (7.1)
			    where true
			    limit 89)))
		      and (cast(null as _aclitem) @> cast(null as aclitem)))))
		and ((select timecol from public.brintest limit 1 offset 96)
		     > cast(null as "time"))))
	    and (cast(null as timestamptz) < cast(null as "timestamp")))
    where ((EXISTS (
	  select
	      sample_2.int_four as c0,
	      sample_0.seqno as c1,
	      43 as c2
	    from
	      public.test_type_diff2_c1 as sample_2 tablesample bernoulli (2.3)
	    where (sample_0.random ~~ ref_1.name)
	      and (ref_2.y <> ref_2.y)
	    limit 98))
	and (sample_0.random is NULL))
      and (cast(null as point) <@ (select b from public.quad_box_tbl limit 1 offset 5)
	  )
    limit 61);
```

```
Pretty-printed minimal query:
SET min_parallel_table_scan_size TO 0;

SELECT
FROM public.prt1_l AS ref_0
     RIGHT JOIN public.my_property_normal AS ref_1 ON NULL
WHERE EXISTS (SELECT
              FROM public.hash_name_heap AS sample_0
                   LEFT JOIN public.tt6 AS ref_2 ON EXISTS (SELECT ref_1.cid AS c8)
              WHERE EXISTS (SELECT
                            WHERE sample_0.random ~~ ref_1.name))

Seen: 314 items, 216469 Bytes
Iterations: 498
Runtime: 85.834 s, 3.7 q/s
```

# Segfault in expand_tuple

* https://www.postgresql.org/message-id/87woxi24uw.fsf@ansel.ydns.eu
* 039eb6e92f

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

```
Pretty-printed minimal query:
SELECT pg_catalog.stddev(NULL) OVER () AS c5
FROM public.mlparted3 AS ref_0

Seen: 51 items, 17026 Bytes
Iterations: 67
Runtime: 32.475 s, 1.6 q/s
```

# Parallel worker executor crash on master

* https://www.postgresql.org/message-id/87mv2ju6zx.fsf@ansel.ydns.eu
* 699bf7d05c

Does not compile with today's compiler.

# Failed assertion in adjust_appendrel_attrs_mutator

* https://www.postgresql.org/message-id/87r2tvt9f1.fsf@ansel.ydns.eu
* 7c981590c2

Does not compile with today's compiler.

