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
