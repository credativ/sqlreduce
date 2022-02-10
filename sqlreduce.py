#!/usr/bin/python3

import pglast
from pglast.stream import RawStream
import psycopg2
from copy import copy, deepcopy
import time
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

    query = RawStream()(parsetree2)
    state['called'] += 1
    if query in state['seen']:
        return False
    state['seen'].add(query)
    if state['verbose']:
        print(query, end='')

    error = run_query(state, query)
    # if running the reduced query yields a different result, stop recursion here
    if error != state['expected_error']:
        if state['verbose']:
            print(" ✘", error)
        return False

    # found expected result
    if state['verbose']:
        print(" ✔")

    state['parsetree'] = parsetree2

    return True

rules_yaml = """
A_Const: # Replace constant with NULL
    try_null:
    tests:
        - select '1,1'::point = '1,1'
        - SELECT CAST((NULL) AS point) = NULL

A_Expr: # Pull up expression subtree
    try_null:
    recurse:
        - lexpr
        - rexpr
    pullup:
        - lexpr
        - rexpr
    tests:
        - select 1+moo
        - SELECT moo

BoolExpr:
    try_null:
    recurse_list:
        - args
    tests:
        - select moo and foo
        - SELECT moo

#CaseExpr:
#    try_null:
#    recurse:
#        - args
#        - defresult

CoalesceExpr:
    try_null:
    recurse_list:
        - args
    tests:
        - select coalesce(1, bar)
        - SELECT bar

ColumnRef:
    try_null:
    tests:
        - select 'TODO'
        - "SELECT "

CommonTableExpr:
    replace:
        - ctequery
    recurse:
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
    recurse:
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
    recurse_list:
        - args
    descend:
        - over
    remove:
        - over
    tests:
        - select foo(bar)
        - SELECT bar
        - select foo() over ()
        - SELECT foo()
        - select lag(1) over (partition by bar, foo)
        - SELECT lag(1) OVER (PARTITION BY bar)

InsertStmt:
    replace:
        - selectStmt
    recurse:
        - selectStmt
    tests:
        - insert into bar select from bar
        - SELECT FROM bar
        - insert into foo select bar
        - "INSERT INTO foo SELECT "

JoinExpr: # TODO: pull up quals correctly
    recurse:
        - larg
        - rarg
        - quals
    tests:
        - select from a join b on true
        - SELECT FROM a
        - select from pg_database join pg_database on moo
        - SELECT FROM pg_database INNER JOIN pg_database ON NULL

"Null": # doesn't actually test if NULL is left alone
    tests:
        - select null
        - "SELECT "

NullTest:
    recurse:
        - arg
    tests:
        - select moo is null
        - SELECT moo

RangeSubselect:
    replace:
        - subquery
    recurse:
        - subquery
    tests:
        - select from (select bar) sub
        - SELECT bar

RangeTableSample:
    recurse:
        - relation
    tests:
        - select from bar tablesample system(1)
        - SELECT FROM bar

RangeVar: # no need to simplify table, we try removing altogether it elsewhere
    tests:
        - select from a
        - SELECT FROM a

RawStmt:
    recurse:
        - stmt
    tests:
        - select
        - "SELECT "

ResTarget: # pulling up val is actually only necessary if 'name' is present, but it doesn't hurt
    try_null:
    recurse:
        - val
    tests:
        - select foo as bar
        - SELECT foo

SelectStmt:
    descend:
        - limitCount
        - targetList
        - valuesLists
        - fromClause
        - whereClause
        - withClause
    replace:
        - larg
        - rarg
    remove:
        - limitCount
        - limitOffset
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

SubLink:
    replace:
        - subselect
    recurse:
        - subselect
    tests:
        - select exists(select moo)
        - SELECT moo

TypeCast:
    try_null:
    recurse:
        - arg
    tests:
        - select foo::int
        - SELECT foo

VariableSetStmt:
    tests:
        - set work_mem = '100MB'
        - SET work_mem TO '100MB'

WindowDef:
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

"""

rules = yaml.safe_load(rules_yaml)

def enumerate_paths(node, path=[]):
    """For a node, recursively enumerate all paths that are reduction targets"""

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
        for key in ('recurse', 'recurse_list', 'descend'):
            if key in rule:
                for attr in rule[key]:
                    if subnode := getattr(node, attr):
                        for p in enumerate_paths(subnode, path+[attr]): yield p

    elif isinstance(node, pglast.ast.CaseExpr):
        if node.args:
            for p in enumerate_paths(node.args, path+['args']): yield p
        if node.defresult:
            for p in enumerate_paths(node.defresult, path+['defresult']): yield p

    elif isinstance(node, pglast.ast.RangeFunction):
        pass # TODO: node structure is weird, check later

    elif isinstance(node, pglast.ast.SortBy):
        for p in enumerate_paths(node.node, path+['node']): yield p

    elif isinstance(node, pglast.ast.WithClause):
        for i in range(len(node.ctes)):
            for p in enumerate_paths(node.ctes[i], path+['ctes', i]): yield p

    else:
        raise Exception("enumerate_paths: don't know what to do with", path, node)

def reduce_step(state, path):
    """Given a parse tree and a path, try to reduce the node at that path"""

    node = getattr_path(state['parsetree'], path)
    classname = type(node).__name__

    if isinstance(node, tuple):
        # try removing the tuple entirely unless it's a CoalesceExpr which doesn't like that
        # also don't strip the inner layer of a valuesLists(tuple(tuple()))
        # TODO: move CoalesceExpr to a better place
        parent = getattr_path(state['parsetree'], path[:-1])
        if not isinstance(parent, pglast.ast.CoalesceExpr) and not isinstance(parent, tuple):
            if try_reduce(state, path, None): return True

        # try removing one tuple element
        if len(node) > 1:
            for i in range(len(node)):
                if try_reduce(state, path, node[:i] + node[i+1:]): return True

    elif classname in rules:
        rule = rules[classname]

        # try running the subquery as new top-level query
        # TODO: skip "recurse" for that case?
        if 'replace' in rule:
            for attr in rule['replace']:
                if subnode := getattr(node, attr):
                    if try_reduce(state, [], subnode): return True

        # try replacing the node with NULL
        if 'try_null' in rule:
            if try_reduce(state, path, pglast.ast.Null()): return True

        # try removing some attribute
        if 'remove' in rule:
            for attr in rule['remove']:
                if try_reduce(state, path+[attr], None): return True

        # try pulling up subexpressions
        if 'recurse' in rule:
            for attr in rule['recurse']:
                if subnode := getattr(node, attr):
                    if try_reduce(state, path, subnode): return True

        # try pulling up subexpressions from a list
        if 'recurse_list' in rule:
            for attr in rule['recurse_list']:
                if subnodelist := getattr(node, attr):
                    for subnode in subnodelist:
                        if try_reduce(state, path, subnode): return True

    # replace expression with NULL
    #elif isinstance(node, pglast.ast.A_Expr):
    #    if try_reduce(state, path, pglast.ast.Null()): return True
    #    if node.lexpr:
    #        if try_reduce(state, path, node.lexpr): return True
    #    if node.rexpr:
    #        if try_reduce(state, path, node.rexpr): return True

    elif isinstance(node, pglast.ast.CaseExpr):
        if try_reduce(state, path, pglast.ast.Null()): return True
        for arg in node.args:
            if try_reduce(state, path, arg.expr): return True
            if try_reduce(state, path, arg.result): return True
        if node.defresult:
            if try_reduce(state, path, node.defresult): return True

    elif isinstance(node, pglast.ast.RangeFunction):
        pass # TODO: node structure is weird, check later

    elif isinstance(node, pglast.ast.SortBy):
        pass

    elif isinstance(node, pglast.ast.WithClause):
        pass

    else:
        raise Exception("reduce_step: don't know what to do with", path, node)

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

def run_reduce(query, database='', verbose=False, use_sqlstate=False, timeout='100ms'):
    """Set up state object for running reduce steps"""

    # parse query
    parsed_query = pglast.parse_sql(query)
    parsetree = parsed_query
    regenerated_query = RawStream()(parsetree)

    state = {
            'called': 0,
            'database': database,
            'parsetree': parsetree,
            'seen': set(),
            'timeout': timeout,
            'use_sqlstate': use_sqlstate,
            'verbose': verbose,
            }

    state['expected_error'] = run_query(state, query)

    if verbose:
        print("Input query:", query)
        print("Regenerated:", regenerated_query)
        print("Query returns: ✔", state['expected_error'])
        print()

    regenerated_query_error = run_query(state, regenerated_query)
    assert(state['expected_error'] == regenerated_query_error)

    reduce_loop(state)

    return RawStream()(state['parsetree']), state

if __name__ == "__main__":
    reduce("", "select 1, moo, 3")
