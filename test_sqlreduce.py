#!/usr/bin/python3

from sqlreduce import run_reduce

def test_select():
    # targetList
    res, _ = run_reduce('', 'select 1, moo as foo, 3')
    assert res == 'SELECT moo'

    res, _ = run_reduce('', 'select case when moo then 1 end')
    assert res == 'SELECT moo'

    res, _ = run_reduce('', 'select case when true then 1 else bar end')
    assert res == 'SELECT bar'

    res, _ = run_reduce('', 'select true and (false or bar)')
    assert res == 'SELECT bar'

    # fromClause
    res, _ = run_reduce('', 'select from pg_class, moo')
    assert res == 'SELECT FROM moo'

    res, _ = run_reduce('', 'select from a, (select 1 from bar) b')
    assert res == 'SELECT FROM bar'

if __name__ == '__main__':
    test_select()
