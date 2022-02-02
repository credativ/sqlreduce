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
            cur.execute("set statement_timeout = '500ms'")
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

def reduce_expr(node):
    yield node
    yield pglast.ast.Null()
    if isinstance(node, pglast.ast.ResTarget):
        for res in reduce_expr(node.val): yield res
    if isinstance(node, pglast.ast.CaseExpr):
        for arg in node.args:
            for res in reduce_expr(arg.expr): yield res
            for res in reduce_expr(arg.result): yield res
        if node.defresult:
            for res in reduce_expr(node.defresult): yield res
    if isinstance(node, pglast.ast.FuncCall):
        for i in range(len(node.args)):
            for expr in reduce_expr(node.args[i]):
                node2 = copy(node)
                node2.args = node.args[:i] + (expr,) + node.args[i+1:]
                yield node2
    return

def reduce(parsetree, state, level):
    query = RawStream()(parsetree)
    if query in state['seen']:
        return
    state['seen'].add(query)
    if state['verbose']:
        print(query, end='')

    error = run_query(state['database'], query)
    # if running the reduced query yields a different result, stop recursion here
    if error != state['expected_error']:
        if state['verbose']:
            print(" --", error)
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
        if parsetree.targetList:
            # try an empty target list first
            parsetree2 = copy(parsetree)
            parsetree2.targetList = None
            e = reduce(parsetree2, state, level+1)

            # if that yields a different error, remove one target list element
            if e != state['expected_error']:
                for i in range(len(parsetree.targetList)):
                    parsetree2 = copy(parsetree)
                    parsetree2.targetList = parsetree.targetList[:i] + parsetree.targetList[i+1:]
                    if parsetree2.targetList == ():
                        parsetree2.targetList = None
                    e = reduce(parsetree2, state, level+1)

                    # if we cannot remove the element, try to reduce it
                    if e != state['expected_error']:
                        for node in reduce_expr(parsetree.targetList[i]):
                            print("Trying", node)
                            parsetree2 = copy(parsetree)
                            parsetree2.targetList = parsetree.targetList[:i] + (node,) + parsetree.targetList[i+1:]
                            reduce(parsetree2, state, level+1)

                    #if isinstance(parsetree.targetList[i].val, psqlparse.nodes.primnodes.CaseExpr):
                    #    for arg in parsetree.targetList[i].val.args:
                    #        # replace case expression by one of its conditions
                    #        parsetree2 = copy(parsetree)
                    #        parsetree2.targetList = copy(parsetree.targetList)
                    #        parsetree2.targetList[i].val = arg.expr
                    #        reduce(parsetree2, state, level+1)

                    #        # replace case expression by one of its results
                    #        parsetree2 = copy(parsetree)
                    #        parsetree2.targetList = copy(parsetree.targetList)
                    #        parsetree2.targetList[i].val = arg.result
                    #        reduce(parsetree2, state, level+1)

        #if parsetree.from_clause:
        #    for i in range(len(parsetree.from_clause)):
        #        parsetree2 = copy(parsetree)
        #        parsetree2.from_clause = parsetree.from_clause[:i] + parsetree.from_clause[i+1:]
        #        reduce(parsetree2, state, level+1)

        #if parsetree.where_clause:
        #    parsetree2 = copy(parsetree)
        #    parsetree2.where_clause = None
        #    reduce(parsetree2, state, level+1)

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
