#!/usr/bin/python3

import pglast
from sqlreduce import enumerate_paths, run_reduce, rules

def test_enumerate():
    p = pglast.parse_sql('select 1')[0].stmt
    assert [x for x in enumerate_paths(p)] == [[], ['targetList'], ['targetList', 0], ['targetList', 0, 'val']]

    p = pglast.parse_sql('select 1, 2')[0].stmt
    assert [x for x in enumerate_paths(p)] == [[], ['targetList'], ['targetList', 0], ['targetList', 0, 'val'], ['targetList', 1], ['targetList', 1, 'val']]

    p = pglast.parse_sql('select 1, moo')[0].stmt
    assert [x for x in enumerate_paths(p)] == [[], ['targetList'], ['targetList', 0], ['targetList', 0, 'val'], ['targetList', 1], ['targetList', 1, 'val']]

    p = pglast.parse_sql('select 1 limit 1')[0].stmt
    assert [x for x in enumerate_paths(p)] == [[], ['limitCount'], ['targetList'], ['targetList', 0], ['targetList', 0, 'val']]

    p = pglast.parse_sql('select from (select 1) sub')[0].stmt
    assert [x for x in enumerate_paths(p)] == [[], ['fromClause'],
            ['fromClause', 0], ['fromClause', 0, 'subquery'], ['fromClause', 0, 'subquery', 'targetList'], ['fromClause', 0, 'subquery', 'targetList', 0], ['fromClause', 0, 'subquery', 'targetList', 0, 'val']]

def test_select():
    # targetList
    res, _ = run_reduce('select 1, moo as foo, 3')
    assert res == 'SELECT moo'

    res, _ = run_reduce('select case when moo then 1 end')
    assert res == 'SELECT moo'

    res, _ = run_reduce('select case when true then 1 else bar end')
    assert res == 'SELECT bar'

    res, _ = run_reduce('select true and (false or bar)')
    assert res == 'SELECT bar'

    # fromClause
    res, _ = run_reduce('select from pg_class, moo')
    assert res == 'SELECT FROM moo'

    res, _ = run_reduce('select from pg_class, (select 1 from bar) b')
    assert res == 'SELECT FROM bar'

    res, _ = run_reduce("select foo('bla', 'bla')")
    assert res == 'SELECT foo(NULL, NULL)'

def test_rules():
    for classname, rule in rules.items():
        print(f"{classname}:")
        tests = rule['tests']
        if tests is None:
            raise Exception(f"{classname} is missing tests")
        for test, expected in zip(tests[0::2], tests[1::2]):
            print("  test:", test)
            res, _ = run_reduce(test)
            print("   got:", res)
            if res != expected:
                print("expect:", expected)
                raise Exception(f"{classname} test: {test}: expected {expected}, got {res}")

if __name__ == '__main__':
    test_enumerate()
    test_select()
    test_rules()
