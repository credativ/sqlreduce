#!/usr/bin/python3

import argparse
import sys
import time

from pglast.stream import IndentedStream
import sqlreduce

#from loguru import logger
#@logger.catch
def sqlreduce_main():
    argparser = argparse.ArgumentParser(description="Reduce a SQL query to the minimal query throwing the same error")
    argparser.add_argument("-d", "--database", type=str, default="", help="Database or connection string to use")
    argparser.add_argument("-f", "--file", type=argparse.FileType('r'), default=sys.stdin, help="Read query from file [Default: stdin]")
    argparser.add_argument("--sqlstate", action='store_true', help="Reduce query to same SQL state instead of error message")
    argparser.add_argument("-t", "--timeout", default='500ms', help="Statement timeout [Default: 500ms]")
    argparser.add_argument("--debug", action='store_true')
    argparser.add_argument("query", nargs='*', help="Query to reduce to minimum")
    args = argparser.parse_args()

    if (args.file != sys.stdin and args.query):
        raise Exception("Cannot use both -f and query arguments")

    if args.query:
        query = ' '.join(args.query)
    else:
        query = args.file.read().rstrip()

    # check database connection
    if not '=' in args.database and not "postgres://" in args.database:
        args.database = f"dbname={args.database}"
    sqlreduce.check_connection(args.database)

    # reduce query
    start = time.time()
    min_query, state = sqlreduce.run_reduce(query,
            database=args.database,
            verbose=True,
            use_sqlstate=args.sqlstate,
            timeout=args.timeout,
            debug=args.debug,
            )
    duration = time.time() - start
    qps = len(state['seen']) / duration

    print()
    print("Minimal query yielding the same error:")
    if state['terminal']:
        print("\033[1m", end="")
    print(min_query)
    if state['terminal']:
        print("\033[0m", end="")
    print()
    print("Pretty-printed minimal query:")
    print(IndentedStream(comma_at_eoln=True)(state['parsetree']))
    print()
    print("Seen:", len(state['seen']), "items,", sum([len(v) for v in state['seen']]), "Bytes")
    print("Iterations:", state['called'])
    print(f"Runtime: {duration:.3f} s, {qps:.1f} q/s")
    #print(state)

if __name__ == "__main__":
    sqlreduce_main()
