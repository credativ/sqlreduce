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

    elif isinstance(node, pglast.ast.CommonTableExpr):
        for p in enumerate_paths(node.ctequery, path+['ctequery']): yield p

    elif isinstance(node, pglast.ast.CreateStmt):
        pass

    elif isinstance(node, pglast.ast.CreateTableAsStmt):
        for p in enumerate_paths(node.query, path+['query']): yield p

    elif isinstance(node, pglast.ast.DeleteStmt):
        if node.whereClause:
            for p in enumerate_paths(node.whereClause, path+['whereClause']): yield p
        if node.usingClause:
            for p in enumerate_paths(node.usingClause, path+['usingClause']): yield p
        if node.returningList:
            for p in enumerate_paths(node.returningList, path+['returningList']): yield p

    elif isinstance(node, pglast.ast.DropStmt):
        pass

    elif isinstance(node, pglast.ast.FuncCall):
        if node.args:
            # recurse into individual arguments (do not recurse into "args" since we don't want to shorten the tuple)
            for i in range(len(node.args)):
                for p in enumerate_paths(node.args[i], path+['args', i]): yield p
        if node.over:
            for p in enumerate_paths(node.over, path+['over']): yield p

    elif isinstance(node, pglast.ast.InsertStmt):
        if node.selectStmt:
            for p in enumerate_paths(node.selectStmt, path+['selectStmt']): yield p

    elif isinstance(node, pglast.ast.JoinExpr):
        for p in enumerate_paths(node.larg, path+['larg']): yield p
        for p in enumerate_paths(node.rarg, path+['rarg']): yield p
        for p in enumerate_paths(node.quals, path+['quals']): yield p

    elif isinstance(node, pglast.ast.Null):
        pass

    elif isinstance(node, pglast.ast.NullTest):
        for p in enumerate_paths(node.arg, path+['arg']): yield p

    elif isinstance(node, pglast.ast.RangeFunction):
        pass # TODO: node structure is weird, check later

    elif isinstance(node, pglast.ast.RangeSubselect):
        for p in enumerate_paths(node.subquery, path+['subquery']): yield p

    elif isinstance(node, pglast.ast.RangeTableSample):
        for p in enumerate_paths(node.relation, path+['relation']): yield p

    elif isinstance(node, pglast.ast.RangeVar):
        pass

    elif isinstance(node, pglast.ast.RawStmt):
        for p in enumerate_paths(node.stmt, path+['stmt']): yield p

    elif isinstance(node, pglast.ast.ResTarget):
        for p in enumerate_paths(node.val, path+['val']): yield p

    elif isinstance(node, pglast.ast.SelectStmt):
        if node.limitCount:
            for p in enumerate_paths(node.limitCount, path+['limitCount']): yield p
        if node.targetList:
            for p in enumerate_paths(node.targetList, path+['targetList']): yield p
        if node.valuesLists:
            for p in enumerate_paths(node.valuesLists, path+['valuesLists']): yield p
        if node.fromClause:
            for p in enumerate_paths(node.fromClause, path+['fromClause']): yield p
        if node.whereClause:
            for p in enumerate_paths(node.whereClause, path+['whereClause']): yield p
        if node.withClause:
            for p in enumerate_paths(node.withClause, path+['withClause']): yield p
        if node.larg:
            for p in enumerate_paths(node.larg, path+['larg']): yield p
        if node.rarg:
            for p in enumerate_paths(node.rarg, path+['rarg']): yield p

    elif isinstance(node, pglast.ast.SortBy):
        for p in enumerate_paths(node.node, path+['node']): yield p

    elif isinstance(node, pglast.ast.SubLink):
        for p in enumerate_paths(node.subselect, path+['subselect']): yield p

    elif isinstance(node, pglast.ast.TypeCast):
        for p in enumerate_paths(node.arg, path+['arg']): yield p

    elif isinstance(node, pglast.ast.VariableSetStmt):
        pass

    elif isinstance(node, pglast.ast.WindowDef):
        if node.partitionClause:
            for p in enumerate_paths(node.partitionClause, path+['partitionClause']): yield p
        if node.orderClause:
            for p in enumerate_paths(node.orderClause, path+['orderClause']): yield p

    elif isinstance(node, pglast.ast.WithClause):
        for i in range(len(node.ctes)):
            for p in enumerate_paths(node.ctes[i], path+['ctes', i]): yield p

    else:
        raise Exception("enumerate_paths: don't know what to do with", path, node)

def reduce_step(state, path):
    """Given a parse tree and a path, try to reduce the node at that path"""

    node = getattr_path(state['parsetree'], path)

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

    elif isinstance(node, pglast.ast.BoolExpr):
        for arg in node.args:
            if try_reduce(state, path, arg): return True

    elif isinstance(node, pglast.ast.CoalesceExpr):
        if try_reduce(state, path, pglast.ast.Null()): return True
        for arg in node.args:
            if try_reduce(state, path, arg): return True

    # replace constant with NULL
    elif isinstance(node, pglast.ast.ColumnRef):
        if try_reduce(state, path, pglast.ast.Null()): return True

    elif isinstance(node, pglast.ast.CommonTableExpr):
        if try_reduce(state, [], node.ctequery): return True

    elif isinstance(node, pglast.ast.CreateTableAsStmt):
        if try_reduce(state, [], node.query): return True

    elif isinstance(node, pglast.ast.CaseExpr):
        if try_reduce(state, path, pglast.ast.Null()): return True
        for arg in node.args:
            if try_reduce(state, path, arg.expr): return True
            if try_reduce(state, path, arg.result): return True
        if node.defresult:
            if try_reduce(state, path, node.defresult): return True

    elif isinstance(node, pglast.ast.CreateStmt):
        pass

    elif isinstance(node, pglast.ast.DeleteStmt):
        if node.whereClause:
            if try_reduce(state, path+['whereClause'], None): return True
        if node.usingClause:
            if try_reduce(state, path+['usingClause'], None): return True
        if node.returningList:
            if try_reduce(state, path+['returningList'], None): return True

    elif isinstance(node, pglast.ast.DropStmt):
        pass

    elif isinstance(node, pglast.ast.FuncCall):
        if try_reduce(state, path, pglast.ast.Null()): return True
        if node.args:
            for arg in node.args:
                if try_reduce(state, path, arg): return True

    # insert select -> select
    elif isinstance(node, pglast.ast.InsertStmt):
        if node.selectStmt:
            if try_reduce(state, [], node.selectStmt): return True

    # pull up join expression
    elif isinstance(node, pglast.ast.JoinExpr):
        if try_reduce(state, path, node.larg): return True
        if try_reduce(state, path, node.rarg): return True
        # TODO: pull up quals?

    elif isinstance(node, pglast.ast.Null):
        pass

    elif isinstance(node, pglast.ast.NullTest):
        if try_reduce(state, path, node.arg): return True

    elif isinstance(node, pglast.ast.RangeFunction):
        pass # TODO: node structure is weird, check later

    # run subselect isolated
    elif isinstance(node, pglast.ast.RangeSubselect):
        if try_reduce(state, [], node.subquery): return True

    elif isinstance(node, pglast.ast.RangeTableSample):
        if try_reduce(state, path, node.relation): return True

    elif isinstance(node, pglast.ast.RangeVar):
        pass # no need to simplify table, we try removing altogether it elsewhere

    elif isinstance(node, pglast.ast.RawStmt):
        pass

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
        if node.whereClause:
            #if try_reduce(state, path+['whereClause'], pglast.ast.A_Const(pglast.ast.String('true'))): return True
            if try_reduce(state, path+['whereClause'], None): return True
        if node.valuesLists:
            if try_reduce(state, path+['valuesLists'], None): return True
        if node.withClause:
            if try_reduce(state, path+['withClause'], None): return True
        # union/except have larg/rarg, pull up
        if node.larg:
            if try_reduce(state, [], node.larg): return True
        if node.rarg:
            if try_reduce(state, [], node.rarg): return True

    elif isinstance(node, pglast.ast.SortBy):
        pass

    # try (subquery) and exists(select) standalone
    elif isinstance(node, pglast.ast.SubLink):
        if try_reduce(state, [], node.subselect): return True

    # case(foo as bar) -> foo
    elif isinstance(node, pglast.ast.TypeCast):
        if try_reduce(state, path, node.arg): return True

    elif isinstance(node, pglast.ast.WindowDef):
        pass

    elif isinstance(node, pglast.ast.WithClause):
        pass

    elif isinstance(node, pglast.ast.VariableSetStmt):
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
