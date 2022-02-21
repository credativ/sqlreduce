#!/usr/bin/python3

import pglast
from pglast.stream import RawStream
import psycopg2
from copy import copy, deepcopy
import time
import os
import sys
import yaml

def getattr_path(obj, path):
    if path == []:
        return obj
    if type(path[0]) == int:
        return getattr_path(obj[path[0]], path[1:])
    else:
        return getattr_path(getattr(obj, path[0]), path[1:])

def setattr_path(obj, path, node):
    if path == []:
        return node
    obj2 = deepcopy(obj)
    parent = getattr_path(obj2, path[:-1])
    if type(path[-1]) == int:
        return setattr_path(obj2, path[:-1], parent[:path[-1]] + (node,) + parent[path[-1]+1:])
    else:
        setattr(parent, path[-1], node)
    return obj2

def run_query(state, query):
    while True:
        try:
            conn = psycopg2.connect(state['database'], fallback_application_name='sqlreduce')
            cur = conn.cursor()
            cur.execute("set statement_timeout = %s", (state['timeout'],))
            break
        except Exception as e:
            print("Waiting for connection startup:", e)
            time.sleep(1)

    error = 'no error'
    try:
        cur.execute(query)
    except psycopg2.Error as e:
        if state['use_sqlstate']:
            error = e.pgcode
        else:
            error = e.pgerror.partition('\n')[0]
    except Exception as e:
        print(e)
        error = e
    try:
        conn.close()
    except:
        pass
    return error

def check_connection(database):
    conn = psycopg2.connect(database, fallback_application_name='sqlreduce')
    cur = conn.cursor()
    cur.execute('select')
    conn.close()

def try_reduce(state, path, node):
    """In the currently best parse tree, replace path by given node and run query.
    Returns True when successful."""

    parsetree2 = setattr_path(state['parsetree'], path, node)

    if state['debug']:
        print("Setting", path, "to", node)
        print(parsetree2)
    query = RawStream()(parsetree2)
    state['called'] += 1
    if query in state['seen']:
        if state['debug']:
            print('Query', query, 'was seen before, skipping\n')
        return False
    state['seen'].add(query)
    if state['verbose']:
        print(query, end='')

    error = run_query(state, query)
    # if running the reduced query yields a different result, stop recursion here
    if error != state['expected_error']:
        if state['verbose']:
            if state['terminal']:
                print(" \033[31m✘\033[0m", error)
            else:
                print(" ✘", error)
            if state['debug']: print()
        return False

    # found expected result
    if state['verbose']:
        if state['terminal']:
            print(" \033[32m✔\033[0m")
        else:
            print(" ✔")
        if state['debug']: print()

    state['parsetree'] = parsetree2

    return True

"""
rules_yaml: what to do when visiting a node type

When a parse tree is to be reduced, the enumerate_paths() function first
recursively visits all nodes to discover all nodes that are worth looking at
(pre-order DFS). The result is an iterator yielding paths (= arrays for input
to getattr_path/setattr_path) from the root to the node in question.

For each of the discovered nodes, try_reduce() is called, which can then decide what
reduction step to apply. Possible steps are configured in rules_yaml:
    * descend: visit attribute in enumerate_paths()
    * try_null: replace entire node with NULL (select 1 -> select NULL)
    * remove: replace a specific attribute with None (select limitCount=1 -> select limitCount=None)
    * pullup: pull up subnodes. If the subnode is a tuple, pull up individual elements
      (select a + b -> select a, select b; select func(a, b) -> a, b) (implies descend)
    * replace: replace entire tree with subnode (select ... (subquery) -> subquery)
      (implies descend)
    * doing nothing with this node

If the node is a tuple (i.e. not a specific class), and the tuple has more than
one element, try_reduce() tries to remove one tuple element. (If empty tuples
make sense in this context, "remove: attr" should be used on the parent node
next to the rule that descends into the node.)

Other keys in rules_yaml:
    * tests: List of pairs (query, expected) of test cases

If the reduction was successful (the reduced query yields the same result/error
as the original one), the parse tree to be reduced is replaced with the new
tree, and the path enumeration restarts at the root node. If none of the
enumerated nodes could be reduced, we are done and the current parse tree is
the minimal query.

Since each node (more precisely: each node attribute) can be reduced at most
once, and we are repeating the process until there are no more nodes to be
reduced, the complexity of the algorithm is O(Nodes²) (since O(Nodes) =
O(Attributes)). In practise, the algorithm is very fast since we are starting
reduction at the root and many steps will remove whole subtrees early without
visiting them.
"""

rules_yaml = """
A_Const: # Replace constant with NULL
    try_null:
    tests:
        - select '1,1'::point = '1,1'
        - SELECT CAST((NULL) AS point) = NULL

A_Expr: # Pull up expression subtree
    try_null:
    pullup:
        - lexpr
        - rexpr
    tests:
        - select 1+moo
        - SELECT moo

AlterDatabaseSetStmt:
    tests:
        - alter database foo reset all
        - ALTER DATABASE foo RESET ALL

AlterRoleSetStmt:
    tests:
        - alter role foo reset all
        - ALTER ROLE foo RESET ALL
        - alter role foo in database bar reset all
        - ALTER ROLE foo IN DATABASE bar RESET ALL

BoolExpr:
    try_null:
    pullup:
        - args
    tests:
        - select moo and foo
        - SELECT moo
        - select true and (foo or false)
        - SELECT foo
        - select set_config('a.b', 'blub', true) = 'blub' and set_config('work_mem', current_setting('a.b'), true) = '' and true
        - SELECT (set_config('a.b', 'blub', NULL) = 'blub') AND (set_config('work_mem', current_setting('a.b'), NULL) = '')

BooleanTest:
    try_null:
    pullup:
        - arg
    tests:
        - select foo is true
        - SELECT foo

#CaseExpr:
#    try_null:
#    pullup:
#        - args
#        - defresult

CoalesceExpr:
    try_null:
    pullup:
        - args
    tests:
        - select coalesce(1, bar)
        - SELECT bar
        - select coalesce(1, '', 2)
        - SELECT COALESCE('', 2)

ColumnRef:
    try_null:
    tests:
        - select 'TODO'
        - "SELECT "

CommonTableExpr:
    replace:
        - ctequery
    tests:
        - with a as (select moo) select from a
        - SELECT moo

CreateStmt: # do nothing
    tests:
        - create table foo (a int)
        - CREATE TABLE foo (a integer)

CreateTableAsStmt:
    replace:
        - query
    tests:
        - create table foo as select 1, moo
        - SELECT moo
        - create table foo as select 1, 2
        - CREATE TABLE foo AS SELECT NULL, NULL

DeleteStmt:
    descend:
        - whereClause
        - usingClause
        - returningList
    remove:
        - whereClause
        - usingClause
        - returningList
    tests:
        - delete from foo where bar
        - DELETE FROM foo
        - delete from foo using bar
        - DELETE FROM foo
        - delete from foo returning bar
        - DELETE FROM foo
        - delete from pg_database where bar and foo
        - DELETE FROM pg_database WHERE bar

DropStmt:
    tests:
        - drop table foo
        - DROP TABLE foo

FuncCall:
    try_null:
    pullup:
        - args
        - agg_order
    descend:
        - over
    remove:
        - args
        - agg_order
        - over
    tests:
        - select foo(bar)
        - SELECT bar
        - select foo() over ()
        - SELECT foo()
        - select lag(1) over (partition by bar, foo)
        - SELECT lag(1) OVER (PARTITION BY bar)
        - select foo(1 order by moo)
        - SELECT foo(1)
        - select count(1 order by moo, bar)
        - SELECT moo
        - select foo(1 + 1)
        - SELECT foo(1)

InsertStmt:
    replace:
        - selectStmt
    remove:
        - onConflictClause
        - cols
    descend:
        - onConflictClause
    tests:
        - insert into bar select from bar
        - SELECT FROM bar
        - create table bar(id int); insert into bar values(foo)
        - VALUES (foo)
        - insert into foo (id) select bar
        - "INSERT INTO foo SELECT "
        - insert into foo values (1) on conflict do nothing
        - "INSERT INTO foo SELECT "

JoinExpr: # TODO: pull up quals correctly
    pullup:
        - larg
        - rarg
        - quals
    tests:
        - select from foo join bar on true
        - SELECT FROM foo
        - select from pg_database join pg_database on moo
        - SELECT FROM pg_database INNER JOIN pg_database ON NULL

"Null":
    tests: # doesn't actually test if NULL is left alone
        - select null
        - "SELECT "

NullTest:
    pullup:
        - arg
    tests:
        - select moo is null
        - SELECT moo

OnConflictClause:
    remove:
        - whereClause
        - infer # works only with DO NOTHING
    descend:
        - targetList
        - whereClause
        # FIXME: don't reduce ResTarget so b doesn't end up as "a" or "b"
    tests:
        - create table foo(id int primary key); insert into foo values (1) on conflict (id) do update set a=1 where true
        - CREATE TABLE foo (id integer PRIMARY KEY); INSERT INTO foo SELECT ON CONFLICT (id) DO UPDATE SET a = NULL
        - create table foo(id int primary key); insert into foo values (1) on conflict (id) do update set id=1, b=1
        - CREATE TABLE foo (id integer PRIMARY KEY); INSERT INTO foo SELECT ON CONFLICT (id) DO UPDATE SET b = NULL
        - create table foo(id int primary key); insert into foo (id) values (1) on conflict (a) do update set id=1
        - CREATE TABLE foo (id integer PRIMARY KEY); INSERT INTO foo SELECT ON CONFLICT (a) DO NOTHING

RangeFunction:
    remove:
        - lateral
    # TODO: descent into node.functions[0][0]
    tests:
        - select from lateral foo()
        - SELECT FROM foo()
        - select from foo(1 + 1)
        - SELECT FROM foo(1 + 1) # FIXME: 1

RangeSubselect:
    replace:
        - subquery
    tests:
        - select from (select bar) sub
        - SELECT bar

RangeTableSample:
    pullup:
        - relation
    tests:
        - select from bar tablesample system(1)
        - SELECT FROM bar

RangeVar: # no need to simplify table, we try removing altogether it elsewhere
    tests:
        - select from moo
        - SELECT FROM moo

RawStmt:
    descend:
        - stmt
    tests:
        - select
        - "SELECT "

ResTarget: # pulling up val is actually only necessary if 'name' is present, but it doesn't hurt
    try_null:
    pullup:
        - val
    tests:
        - select foo as bar
        - SELECT foo

SelectStmt:
    descend:
        - limitCount
        - limitOffset
        - distinctClause
        - sortClause # TODO: leaves DESC behind when removing sort arg
        - targetList
        - valuesLists
        - fromClause
        - whereClause
        - groupClause
        - withClause
    replace: # union
        - larg
        - rarg
    remove:
        - limitCount
        - limitOffset
        - distinctClause
        - sortClause # TODO: leaves DESC behind when removing sort arg
        - targetList
        - whereClause
        - valuesLists
        - withClause
    tests:
        - select limit 1
        - "SELECT "
        - select offset 1
        - "SELECT "
        - select 1
        - "SELECT "
        - select foo, bar
        - SELECT foo
        - select where true
        - "SELECT "
        - select from foo union select from bar
        - SELECT FROM foo
        - select from foo, bar
        - SELECT FROM foo
        - select order by foo, bar
        - SELECT ORDER BY foo
        - select group by foo, bar
        - SELECT GROUP BY foo
        - values (1)
        - "SELECT "
        - values(1), (moo), (foo)
        - VALUES (moo)
        - select from (values (moo)) sub
        - VALUES (moo)
        - with moo as (select) select from foo
        - SELECT FROM foo
        - select distinct foo
        - SELECT foo
        - select distinct on (a, b) NULL
        - SELECT DISTINCT ON (a) NULL

SortBy:
    remove:
        - sortby_dir
    tests:
        # TODO: real test needed
        - select foo(1 order by moo desc)
        - SELECT foo(1)
        - select avg(1 order by foo)
        - SELECT foo

SubLink:
    replace:
        - subselect
    tests:
        - select (select moo)
        - SELECT moo
        - select exists(select moo)
        - SELECT moo

TypeCast:
    try_null:
    pullup:
        - arg
    tests:
        - select foo::int
        - SELECT foo

VariableSetStmt:
    tests:
        - set work_mem = '100MB'
        - SET work_mem TO '100MB'

UpdateStmt:
    remove:
        - whereClause
    descend:
        - whereClause
        - targetList
        # FIXME: don't reduce ResTarget so b doesn't end up as "a" or "b"
    tests:
        - update foo set a=b, c=d
        - UPDATE foo SET c = NULL
        - update foo set a=b where true
        - UPDATE foo SET a = NULL

WindowDef:
    # we cannot pull anything up here since we are a sub-node of the actual query
    remove:
        - partitionClause
        - orderClause
    descend:
        - partitionClause
        - orderClause
    tests:
        - select count(*) over (partition by bar, foo)
        - SELECT count(*) OVER (PARTITION BY bar)
        - select count(*) over (order by bar, foo)
        - SELECT count(*) OVER (ORDER BY bar)
        - select count(*) over (partition by bar order by bar, foo)
        - SELECT count(*) OVER (ORDER BY bar)

WithClause:
    descend:
        - ctes
    tests:
        - with a(a) as (select 5), whatever as (select), b(b) as (select '') select a = b from a, b
        - WITH a(a) AS (SELECT 5), b(b) AS (SELECT NULL) SELECT a = b FROM a, b
"""

rules = yaml.safe_load(rules_yaml)

def enumerate_paths(node, path=[]):
    """For a node, recursively enumerate all subpaths that are reduction targets"""

    assert node != None

    # the path itself
    yield path

    # now enumerate all subnodes that are interesting to look at as reduction points
    classname = type(node).__name__

    if isinstance(node, tuple):
        for i in range(len(node)):
            for p in enumerate_paths(node[i], path+[i]): yield p

    elif classname in rules:
        rule = rules[classname]

        # recurse into subnodes
        for key in ('descend', 'pullup', 'replace'):
            if key in rule:
                for attr in rule[key]:
                    if subnode := getattr(node, attr):
                        for p in enumerate_paths(subnode, path+[attr]): yield p

    elif isinstance(node, pglast.ast.CaseExpr):
        if node.args:
            for p in enumerate_paths(node.args, path+['args']): yield p
        if node.defresult:
            for p in enumerate_paths(node.defresult, path+['defresult']): yield p

    else:
        print("enumerate_paths: don't know what to do with the node at path", path)
        print(node)
        print("Please submit this as a bug report")
        if state['debug']:
            raise Exception("enumerate_paths: don't know what to do with the node at path" + path)

def reduce_step(state, path):
    """Given a parse tree and a path, try to reduce the node at that path"""

    node = getattr_path(state['parsetree'], path)
    classname = type(node).__name__

    # we are looking at a tuple, try removing one tuple element
    if isinstance(node, tuple):
        if len(node) > 1: # don't remove the only element
            for i in range(len(node)):
                if try_reduce(state, path, node[:i] + node[i+1:]): return True

    # we are looking at a class mentioned in rules_yaml
    elif classname in rules:
        rule = rules[classname]

        # try running the subquery as new top-level query
        # TODO: try pulling up to intermediate levels?
        if 'replace' in rule:
            for attr in rule['replace']:
                if subnode := getattr(node, attr):
                    # leave top list of RawStmt in place
                    assert path[1] == 'stmt'
                    if try_reduce(state, path[:2], subnode): return True

        # try replacing the node with NULL
        if 'try_null' in rule:
            if try_reduce(state, path, pglast.ast.Null()): return True

        # try removing some attribute
        if 'remove' in rule:
            for attr in rule['remove']:
                if getattr_path(state['parsetree'], path+[attr]) is not None:
                    if try_reduce(state, path+[attr], None): return True

        # try pulling up subexpressions
        if 'pullup' in rule:
            for attr in rule['pullup']:
                if subnode := getattr(node, attr):
                    # if subnode is a tuple, pull up individual elements
                    if isinstance(subnode, tuple):
                        for subnodeelement in subnode:
                            if try_reduce(state, path, subnodeelement): return True
                    else:
                        if try_reduce(state, path, subnode): return True

    elif isinstance(node, pglast.ast.CaseExpr):
        if try_reduce(state, path, pglast.ast.Null()): return True
        for arg in node.args:
            if try_reduce(state, path, arg.expr): return True
            if try_reduce(state, path, arg.result): return True
        if node.defresult:
            if try_reduce(state, path, node.defresult): return True

    else:
        print("reduce_step: don't know what to do with the node at path", path)
        print(node)
        print("Please submit this as a bug report")
        if state['debug']:
            raise Exception("reduce_step: don't know what to do with the node at path" + path)

    # additional actions
    # ON CONFLICT DO UPDATE -> DO NOTHING
    if isinstance(node, pglast.ast.OnConflictClause) and node.action == 2: # OnConflictAction.ONCONFLICT_UPDATE: 2
        if try_reduce(state, path+['action'], 1): return True

def reduce_loop(state):
    """Try running reduce steps until no reduction is found"""

    found = True
    while found:
        found = False

        # enumerate all places that might be reduced, and try running a step on them
        for path in enumerate_paths(state['parsetree']):
            if reduce_step(state, path):
                found = True
                break

def run_reduce(query, database='', verbose=False, use_sqlstate=False, timeout='500ms', debug=False):
    """Set up state object for running reduce steps"""

    # parse query
    parsed_query = pglast.parse_sql(query)
    parsetree = parsed_query
    regenerated_query = RawStream()(parsetree)

    state = {
            'called': 0,
            'database': database,
            'debug': debug,
            'parsetree': parsetree,
            'seen': set(),
            'terminal': sys.stdout.isatty() and os.environ.get('TERM') != 'dumb',
            'timeout': timeout,
            'use_sqlstate': use_sqlstate,
            'verbose': verbose,
            }

    state['expected_error'] = run_query(state, query)

    if verbose:
        print("Input query:", query)
        print("Regenerated:", regenerated_query)
        print("Query returns:", end=' ')
        if state['terminal']:
            print(f"\033[32m✔\033[0m \033[1m{state['expected_error']}\033[0m")
        else:
            print("✔", state['expected_error'])
        if state['debug']:
            print("Parse tree:", state['parsetree'])
        print()

    regenerated_query_error = run_query(state, regenerated_query)
    assert(state['expected_error'] == regenerated_query_error)

    reduce_loop(state)

    return RawStream()(state['parsetree']), state

if __name__ == "__main__":
    reduce("", "select 1, moo, 3")
