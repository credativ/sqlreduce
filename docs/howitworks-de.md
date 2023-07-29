SQLreduce: Große SQL-Queries auf Minimum reduzieren
===================================================

![SQLreduce logo](sqlreduce.png)

Entwicklern begegnen oft große SQL-Queries, die einen Fehler werfen. SQLreduce
ist ein Tool, mit dem diese Komplexität auf eine minimale Query reduziert wird.

## SQLsmith generiert zufällige SQL-Queries

[SQLsmith](https://github.com/anse1/sqlsmith) ist ein Tool, das zufällige
SQL-Queries generiert und diese gegen einen PostgreSQL-Server laufen lässt (und
andere DBMS-Typen). Die Idee ist, dass im Query-Parser und -Executor mit
Fuzz-Testing Corner-Case-Bugs gefunden werden können, die mit manuellen Testen
oder der festen Menge an Queries aus der PostgreSQL-Regression-Testsuite nicht
gefunden wären. Es hat sich als
[effektives Tool](https://github.com/anse1/sqlsmith/wiki#score-list)
bewährt, das seit 2015 über 100 Bugs in verschiedenen Teilen des
PostgreSQL-Servers und anderen Produkten gefunden hat, darunter Security-Bugs,
von Executor-Bugs bis zu Segfaults in Typ- und Index-Methoden.

2018 fand SQLsmith beispielsweise, dass die folgende Query
[einen Segfault in PostgreSQL verursacht](https://www.postgresql.org/message-id/flat/87woxi24uw.fsf%40ansel.ydns.eu):

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

Allerdings sind die zufälligen Queries von SQLsmith wie in diesem 40-Zeilen,
2,2kB Beispiel oft sehr groß und enthalten viel Rauschen, das zum eigentlichen
Fehler nicht beiträgt. Bisher musste die Query manuell inspiziert und aufwändig
bearbeitet werden, um das Beispiel auf einen minimalen Reproducer zu
reduzieren, der von Entwicklern benutzt werden kann, das Problem zu beheben.

## Komplexität reduzieren mit SQLreduce

Dieses Problem wird von [SQLreduce](https://github.com/df7cb/sqlreduce)
gelöst. SQLreduce nimmt eine beliebige SQL-Query als Eingabe und lässt sie
gegen einen PostgreSQL-Server laufen. Verschiedene Vereinfachungsschritte
werden angewandt und nach jedem Schritt überprüft, ob die vereinfachte Query
immer noch den gleichen Fehler im PostgreSQL-Server verursacht. Das Endergebnis
ist eine Query mit minimaler Komplexität.

SQLreduce kann die Queries aus
[den Original-Bugreports von SQLsmith](https://github.com/anse1/sqlsmith/wiki#score-list)
effektiv auf Queries reduzieren, die manuell reduzierten Queries gleichen.
Beispielsweise kann SQLreduce die riesen Query von oben auf diese Zeile
reduzieren:

```
SELECT pg_catalog.stddev(NULL) OVER () AS c5 FROM public.mlparted3 AS ref_0
```

Dabei versucht SQLreduce nicht, eine Query zu erzeugen, die semantisch
identisch zum Original ist, oder das gleiche Query-Ergebnis liefert. Die
Eingabequery ist sowieso fehlerbehaftet, und es wird eine minimale Query
gesucht, die die gleiche Fehlermeldung provoziert, wenn sie gegen PostgreSQL
läuft. Sollte die Eingabequery keinen Fehler werfen, so findet SQLreduce
einfach `SELECT` als minimale Query.

## Wie es funktioniert

Wir benutzen eine einfachere Query, um zu zeigen, wie SQLreduce arbeitet, und
welche Schritte genommen werden, um das Rauschen aus der Eingabe zu entfernen.
Diese Query ist fehlerhaft und enthält einige Teile, die entfernt werden sollen:

```
$ psql -c 'select pg_database.reltuples / 1000 from pg_database, pg_class where 0 < pg_database.reltuples / 1000 order by 1 desc limit 10'
ERROR:  column pg_database.reltuples does not exist
```

Wir geben die Query an SQLreduce:

```
$ sqlreduce 'select pg_database.reltuples / 1000 from pg_database, pg_class where 0 < pg_database.reltuples / 1000 order by 1 desc limit 10'
```

SQLreduce parst die Eingabe mit
[pglast](https://github.com/lelit/pglast) und
[libpg_query](https://github.com/pganalyze/libpg_query), die den original
PostgreSQL-Parse als Bibliothek mit Python-Bindings bereitstellen. Das Ergebnis
ist ein Parsetree, der die Basis für die nächsten Schritte bildet. Der
Parsetree sieht so aus:

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

Pglast enthält außerdem einen Query-Renderer, der den Parsetree wieder in SQL
übersetzen kann, unten als regenerierte Query gezeigt. Die Eingabequery wird
mit PostgreSQL ausgeführt, um das Ergebnis zu erhalten, in diesem Fall
`ERROR:  column pg_database.reltuples does not exist`.

```
Input query: select pg_database.reltuples / 1000 from pg_database, pg_class where 0 < pg_database.reltuples / 1000 order by 1 desc limit 10
Regenerated: SELECT pg_database.reltuples / 1000 FROM pg_database, pg_class WHERE 0 < ((pg_database.reltuples / 1000)) ORDER BY 1 DESC LIMIT 10
Query returns: ✔ ERROR:  column pg_database.reltuples does not exist
```

SQLreduce erzeugt neue Parsetrees, die strukturell einfacher sind, generiert
davon SQL, und lässt diese Queries mit PostgreSQL laufen. Die ersten
Vereinfachungsschritte passieren auf dem Toplevel-Knoten, wo SQLreduce
versucht, ganze Teilbäume zu entfernen, um schnell zu Ergebnissen zu kommen.
Der erste Reduktions-Versuch ist, `LIMIT 10` zu entfernen:

```
SELECT pg_database.reltuples / 1000 FROM pg_database, pg_class WHERE 0 < ((pg_database.reltuples / 1000)) ORDER BY 1 DESC ✔
```

Das Query-Ergebnis ist immer noch `ERROR:  column pg_database.reltuples does
not exist`, angezeigt durch ein ✔ Häkchen. Als nächstes wird `ORDER BY 1`
entfernt, wiederum erfolgreich:

```
SELECT pg_database.reltuples / 1000 FROM pg_database, pg_class WHERE 0 < ((pg_database.reltuples / 1000)) ✔
```

Nun wird die gesamte Target-Liste entfernt:

```
SELECT FROM pg_database, pg_class WHERE 0 < ((pg_database.reltuples / 1000)) ✔
```

Bezogen auf die Fehlermeldung von PostgreSQL ist diese kürzere Query immer noch
äquivalent zur Original-Query. Nun wird der erste nicht erfolgreiche
Reduktionsschritt versucht, das Entfernen der `FROM`-Klausel:

```
SELECT WHERE 0 < ((pg_database.reltuples / 1000)) ✘ ERROR:  missing FROM-clause entry for table "pg_database"
```

Diese Query ist ebenfalls fehlerhaft, aber verursacht eine andere
Fehlermeldung, daher wird der bisherige Parsetree beibehalten. Wiederrum wird
ein ganzer Teilbaum entfernt, diesmal die `WHERE`-Klausel:

```
SELECT FROM pg_database, pg_class ✘ no error
```

Wir haben die Eingabe nun so weit reduziert, dass gar kein Fehler mehr entsteht. Der bisherige Parsetree wird
weiter beibehalten. Er sieht nun so aus:

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

SQLreduce beginnt nun, in den Baum abzusteigen. In der `FROM`-Klausel sind
mehrere Einträge, also versucht es, die Liste zu kürzen. Als erstes wird
`pg_database` entfernt, was nicht funktioniert, also wird stattdessen
`pg_class` entfernt:

```
SELECT FROM pg_class WHERE 0 < ((pg_database.reltuples / 1000)) ✘ ERROR:  missing FROM-clause entry for table "pg_database"
SELECT FROM pg_database WHERE 0 < ((pg_database.reltuples / 1000)) ✔
```

Da wir nun eine neue minimale Query gefunden haben, beginnt die Rekursion
erneut beim Toplevel mit einem neuen Versuch, die `WHERE`-Klausel zu entfernen.
Da das nicht funktioniert, versucht es, den Ausdruck durch `NULL` zu ersetzen,
aber das funktioniert auch nicht:

```
SELECT FROM pg_database ✘ no error
SELECT FROM pg_database WHERE NULL ✘ no error
```

Nun wird eine neue Art von Schritt versucht: Expression Pull-Up. Wir steigen in
die `WHERE`-Klausel ab, wo wir `A < B` zunächst durch `A` und dann durch `B`
ersetzen:

```
SELECT FROM pg_database WHERE 0 ✘ ERROR:  argument of WHERE must be type boolean, not type integer
SELECT FROM pg_database WHERE pg_database.reltuples / 1000 ✔
SELECT WHERE pg_database.reltuples / 1000 ✘ ERROR:  missing FROM-clause entry for table "pg_database"
```

Der erste Versuch funktionierte nicht, aber der zweite. Da die Query
vereinfacht wurde, beginnen wir erneut beim Toplevel mit einem Versuch, die
`FROM`-Klausel zu entfernen, aber die wird weiterhin benötigt.

In `A / B` können wir nun `A` hochziehen:

```
SELECT FROM pg_database WHERE pg_database.reltuples ✔
SELECT WHERE pg_database.reltuples ✘ ERROR:  missing FROM-clause entry for table "pg_database"
```

SQLreduce hat die minimale Query gefunden, die immer noch `ERROR:  column
pg_database.reltuples does not exist` verursacht. Der Parsetree ist nun:

```
selectStmt
├── fromClause
│   └── pg_database
└── whereClause
    └── pg_database.reltuples
```

Am Ende des Laufs wird die Query mit ein paar Statistiken ausgedruckt:

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

Diese minimale Query kann nun benutzt werden, um den Bug in PostgreSQL oder der Anwendung zu fixen.
