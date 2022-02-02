from sqlreduce import run_reduce

def test_select():
    res, _ = run_reduce('', 'select 1, moo, 3')
    assert res == 'SELECT moo'

    res, _ = run_reduce('', 'select case when moo then 1 end')
    assert res == 'SELECT moo'

    res, _ = run_reduce('', 'select case when true then 1 else bar end')
    assert res == 'SELECT bar'
