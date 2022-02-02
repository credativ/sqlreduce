#!/usr/bin/python3

import pglast
from pglast.stream import RawStream
import psycopg2
from copy import copy
import time

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

def reduce_expr(node, state, level):
    yield node
    yield pglast.ast.Null()

    if isinstance(node, pglast.ast.BoolExpr):
        for arg in node.args:
            for res in reduce_expr(arg, state, level): yield res

    if isinstance(node, pglast.ast.CaseExpr):
        for arg in node.args:
            for res in reduce_expr(arg.expr, state, level): yield res
            for res in reduce_expr(arg.result, state, level): yield res
        if node.defresult:
            for res in reduce_expr(node.defresult, state, level): yield res

    if isinstance(node, pglast.ast.FuncCall) and node.args:
        for i in range(len(node.args)):
            for expr in reduce_expr(node.args[i], state, level):
                node2 = copy(node)
                node2.args = node.args[:i] + (expr,) + node.args[i+1:]
                yield node2

    if isinstance(node, pglast.ast.ResTarget):
        for res in reduce_expr(node.val, state, level): yield res

    # if it's a subselect, try that alone
    if isinstance(node, pglast.ast.SubLink):
        e = reduce(node.subselect, state, level+1)
        #if e == state['expected_error']: break
        # TODO: dig into subselect

    return

def reduce_from_expr(node, state, level):
    yield node
    # TODO: yield 'SELECT NULL' ?

    if isinstance(node, pglast.ast.JoinExpr):
        for res in reduce_from_expr(node.larg, state, level): yield res
        for res in reduce_from_expr(node.rarg, state, level): yield res

    # if it's a subselect, try that alone
    if isinstance(node, pglast.ast.RangeSubselect):
        e = reduce(node.subquery, state, level+1)
        #if e == state['expected_error']: break
        # TODO: dig into subselect

    return

def reduce_target_list(parsetree, state, level):
    # try an empty target list first
    parsetree2 = copy(parsetree)
    parsetree2.targetList = None
    e = reduce(parsetree2, state, level+1)

    # if that yields the same error, stop recursion
    if e == state['expected_error']: return

    # else take the target list apart
    for i in range(len(parsetree.targetList)):
        # try without an element
        parsetree2 = copy(parsetree)
        parsetree2.targetList = parsetree.targetList[:i] + parsetree.targetList[i+1:]
        if parsetree2.targetList == ():
            parsetree2.targetList = None
        e = reduce(parsetree2, state, level+1)

        # if we can remove the element, no need to dig further
        if e == state['expected_error']: break

        # else reduce the expression
        for node in reduce_expr(parsetree.targetList[i], state, level):
            parsetree2 = copy(parsetree)
            parsetree2.targetList = parsetree.targetList[:i] + (node,) + parsetree.targetList[i+1:]
            reduce(parsetree2, state, level+1)

def reduce_from_clause(parsetree, state, level):
    # try an empty from clause first
    parsetree2 = copy(parsetree)
    parsetree2.fromClause = None
    e = reduce(parsetree2, state, level+1)

    # if that yields the same error, stop recursion
    if e == state['expected_error']: return

    # else take the from clause apart
    for i in range(len(parsetree.fromClause)):

        # try without an element
        parsetree2 = copy(parsetree)
        parsetree2.fromClause = parsetree.fromClause[:i] + parsetree.fromClause[i+1:]
        if parsetree2.fromClause == ():
            parsetree2.fromClause = None
        e = reduce(parsetree2, state, level+1)

        # if we can remove the element, stop
        if e == state['expected_error']: break

        # else reduce the expression
        for node in reduce_from_expr(parsetree.fromClause[i], state, level):
            parsetree2 = copy(parsetree)
            parsetree2.fromClause = parsetree.fromClause[:i] + (node,) + parsetree.fromClause[i+1:]
            reduce(parsetree2, state, level+1)

            #for node in reduce_select(parsetree.fromClause[i]):
            #    parsetree2 = copy(parsetree)
            #    parsetree2.fromClause = parsetree.fromClause[:i] + (node,) + parsetree.fromClause[i+1:]
            #    reduce(parsetree2, state, level+1)

def reduce(parsetree, state, level):
    query = RawStream()(parsetree)
    state['called'] += 1
    if query in state['seen']:
        return
    state['seen'].add(query)
    if state['verbose']:
        print(query, end='')

    error = run_query(state['database'], query)
    # if running the reduced query yields a different result, stop recursion here
    if error != state['expected_error']:
        if state['verbose']:
            print(" ✘", error)
        return error
    else:
        # found expected result
        if state['verbose']:
            print(" ✔")

    if len(query) < state['min_query_len']:
        state['min_query'] = query
        state['min_query_len'] = len(query)
        state['min_query_level'] = level

    # SELECT
    if isinstance(parsetree, pglast.ast.SelectStmt):

        if parsetree.limitCount or parsetree.limitOffset:
            parsetree2 = copy(parsetree)
            parsetree2.limitCount = None
            parsetree2.limitOffset = None
            e = reduce(parsetree2, state, level+1)
            if e == state['expected_error']: return error

        if parsetree.targetList:
            reduce_target_list(parsetree, state, level)

        if parsetree.fromClause:
            reduce_from_clause(parsetree, state, level)

        if parsetree.whereClause:
            parsetree2 = copy(parsetree)
            parsetree2.whereClause = None
            e = reduce(parsetree2, state, level+1)
            if e != state['expected_error']:
                for expr in reduce_expr(parsetree.whereClause, state, level):
                    parsetree2 = copy(parsetree)
                    parsetree2.whereClause = expr
                    e = reduce(parsetree2, state, level+1)

        #if parsetree.group_clause:
        #    for i in range(len(parsetree.group_clause)):
        #        parsetree2 = copy(parsetree)
        #        parsetree2.group_clause = parsetree.group_clause[:i] + parsetree.group_clause[i+1:]
        #        reduce(parsetree2, state, level+1)

        #if parsetree.having_clause:
        #    parsetree2 = copy(parsetree)
        #    parsetree2.having_clause = None
        #    reduce(parsetree2, state, level+1)

        #if parsetree.limit_count:
        #    parsetree2 = copy(parsetree)
        #    parsetree2.limit_count = None
        #    reduce(parsetree2, state, level+1)

        #if parsetree.limit_offset:
        #    parsetree2 = copy(parsetree)
        #    parsetree2.limit_offset = None
        #    reduce(parsetree2, state, level+1)

    # INSERT
    #elif isinstance(parsetree, psqlparse.nodes.parsenodes.InsertStmt):
    #    # try the query part only
    #    reduce(parsetree.select_stmt, state, level+1)

    #    # try INSERT with dummy query
    #    parsetree2 = copy(parsetree)
    #    parsetree2.select_stmt = psqlparse.nodes.parsenodes.SelectStmt(dict())
    #    reduce(parsetree2, state, level+1)

    return error

def run_reduce(database, query, verbose=False):
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
            'min_query_level': 0,
            'seen': set(),
            'verbose': verbose,
            }

    reduce(parsetree.stmt, state, 0)

    return state['min_query'], state

if __name__ == "__main__":
    reduce("", "select 1, moo, 3")
