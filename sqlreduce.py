#!/usr/bin/python3

import pglast
from pglast.stream import RawStream
import psycopg2
from copy import copy, deepcopy
import time

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

def run_query(database, query):
    while True:
        try:
            conn = psycopg2.connect(database)
            cur = conn.cursor()
            cur.execute("set statement_timeout = '100ms'")
            cur.execute('select');
            break
        except Exception as e:
            print("Waiting for connection startup:", e)
            time.sleep(1)

    error = 'no error'
    try:
        cur.execute(query)
    except psycopg2.Error as e:
        error = e.pgerror.partition('\n')[0]
        #print(e.pgcode)
        #error = e.pgcode
    except Exception as e:
        print(e)
        error = e
    try:
        #conn.rollback()
        conn.close()
    except:
        pass
    return error

def check_connection(database):
    conn = psycopg2.connect(database)
    cur = conn.cursor()
    cur.execute("set lock_timeout = '500ms'")
    conn.commit()
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

    error = run_query(state['database'], query)
    # if running the reduced query yields a different result, stop recursion here
    if error != state['expected_error']:
        if state['verbose']:
            print(" ✘", error)
        return False

    # found expected result
    if state['verbose']:
        print(" ✔")

    #if len(query) < state['min_query_len']:
    state['parsetree'] = parsetree2
    state['min_query'] = query
    state['min_query_len'] = len(query)

    return True

def enumerate_paths(node, path=[]):
    """For a node, recursively enumerate all paths that are reduction targets"""

    assert node != None
    yield path

    if isinstance(node, tuple):
        for i in range(len(node)):
            for p in enumerate_paths(node[i], path+[i]): yield p

    elif isinstance(node, pglast.ast.A_Const):
        pass

    elif isinstance(node, pglast.ast.A_Expr):
        if node.lexpr:
            for p in enumerate_paths(node.lexpr, path+['lexpr']): yield p
        if node.rexpr:
            for p in enumerate_paths(node.rexpr, path+['rexpr']): yield p

    elif isinstance(node, pglast.ast.CaseExpr):
        if node.args:
            for p in enumerate_paths(node.args, path+['args']): yield p
        if node.defresult:
            for p in enumerate_paths(node.defresult, path+['defresult']): yield p

    elif isinstance(node, pglast.ast.CoalesceExpr):
        for p in enumerate_paths(node.args, path+['args']): yield p

    elif isinstance(node, pglast.ast.ColumnRef):
        pass

    elif isinstance(node, pglast.ast.FuncCall) and node.args:
        # recurse into individual arguments (do not recurse into "args" since we don't want to shorten the tuple)
        for i in range(len(node.args)):
            for p in enumerate_paths(node.args[i], path+['args', i]): yield p

    elif isinstance(node, pglast.ast.Null):
        pass

    elif isinstance(node, pglast.ast.RangeSubselect):
        for p in enumerate_paths(node.subquery, path+['subquery']): yield p

    elif isinstance(node, pglast.ast.RangeVar):
        pass

    elif isinstance(node, pglast.ast.ResTarget):
        for p in enumerate_paths(node.val, path+['val']): yield p

    elif isinstance(node, pglast.ast.SelectStmt):
        if node.limitCount:
            for p in enumerate_paths(node.limitCount, path+['limitCount']): yield p
        if node.targetList:
            #yield path+['targetList']
            for p in enumerate_paths(node.targetList, path+['targetList']): yield p
        if node.fromClause:
            #yield path+['fromClause']
            for p in enumerate_paths(node.fromClause, path+['fromClause']): yield p
        if node.whereClause:
            #yield path+['whereClause']
            for p in enumerate_paths(node.whereClause, path+['whereClause']): yield p

    elif isinstance(node, pglast.ast.SubLink):
        for p in enumerate_paths(node.subselect, path+['subselect']): yield p

    elif isinstance(node, pglast.ast.TypeCast):
        for p in enumerate_paths(node.arg, path+['arg']): yield p

    else:
        raise Exception("enumerate_paths: don't know what to do with", path, node)

def reduce_step(state, path):
    """Given a parse tree and a path, try to reduce the node at that path"""

    node = getattr_path(state['parsetree'], path)
    if False:
        pass

    if isinstance(node, tuple):
        # try removing the tuple entirely unless it's a CoalesceExpr which doesn't like that
        # TODO: move CoalesceExpr to a better place
        if not isinstance(getattr_path(state['parsetree'], path[:-1]), pglast.ast.CoalesceExpr):
            if try_reduce(state, path, None): return True

        # try removing one tuple element
        if len(node) > 1:
            for i in range(len(node)):
                if try_reduce(state, path, node[:i] + node[i+1:]): return True

    # replace constant with NULL
    elif isinstance(node, pglast.ast.A_Const):
        if try_reduce(state, path, pglast.ast.Null()): return True

    # replace expression with NULL
    elif isinstance(node, pglast.ast.A_Expr):
        if try_reduce(state, path, pglast.ast.Null()): return True
        if node.lexpr:
            if try_reduce(state, path, node.lexpr): return True
        if node.rexpr:
            if try_reduce(state, path, node.rexpr): return True

    elif isinstance(node, pglast.ast.CoalesceExpr):
        if try_reduce(state, path, pglast.ast.Null()): return True

    # replace constant with NULL
    elif isinstance(node, pglast.ast.ColumnRef):
        if try_reduce(state, path, pglast.ast.Null()): return True

    elif isinstance(node, pglast.ast.BoolExpr):
        for arg in node.args:
            if try_reduce(state, path, arg): return True

    elif isinstance(node, pglast.ast.CaseExpr):
        if try_reduce(state, path, pglast.ast.Null()): return True
        for arg in node.args:
            if try_reduce(state, path, arg.expr): return True
            if try_reduce(state, path, arg.result): return True
        if node.defresult:
            if try_reduce(state, path, node.defresult): return True

    elif isinstance(node, pglast.ast.FuncCall):
        if try_reduce(state, path, pglast.ast.Null()): return True
        # TODO: more?

    # pull up join expression
    elif isinstance(node, pglast.ast.JoinExpr):
        if try_reduce(state, path, node.larg): return True
        if try_reduce(state, path, node.rarg): return True

    elif isinstance(node, pglast.ast.Null):
        pass

    # run subselect isolated
    elif isinstance(node, pglast.ast.RangeSubselect):
        if try_reduce(state, [], node.subquery): return True

    elif isinstance(node, pglast.ast.RangeVar):
        pass # no need to simplify table, we try removing altogether it elsewhere

    # select foo as bar -> select foo
    elif isinstance(node, pglast.ast.ResTarget):
        if node.name:
            if try_reduce(state, path, node.val): return True

    # select limit foo -> select
    elif isinstance(node, pglast.ast.SelectStmt):
        if node.limitCount:
            if try_reduce(state, path+['limitCount'], None): return True
        if node.limitOffset:
            if try_reduce(state, path+['limitOffset'], None): return True

    elif isinstance(node, pglast.ast.SubLink):
        pass

    # case(foo as bar) -> foo
    elif isinstance(node, pglast.ast.TypeCast):
        if try_reduce(state, path, node.arg): return True

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

def run_reduce(database, query, verbose=False):
    """Set up state object for running reduce steps"""

    # parse query
    parsed_query = pglast.parse_sql(query)
    assert len(parsed_query) == 1
    parsetree = parsed_query[0]
    regenerated_query = RawStream()(parsetree)

    # check database connection
    check_connection(database)
    expected_error = run_query(database, query)

    if verbose:
        print("Input query:", query)
        print("Regenerated:", regenerated_query)
        print("Query returns:", expected_error)
        print()

    regenerated_query_error = run_query(database, regenerated_query)
    assert(expected_error == regenerated_query_error)

    state = {
            'called': 0,
            'database': database,
            'expected_error': expected_error,
            'min_query': regenerated_query,
            'min_query_len': len(regenerated_query),
            'parsetree': parsetree.stmt,
            'seen': set(),
            'verbose': verbose,
            }

    reduce_loop(state)

    return state['min_query'], state

if __name__ == "__main__":
    reduce("", "select 1, moo, 3")
