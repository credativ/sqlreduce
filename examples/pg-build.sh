#!/bin/sh

# Run this script in a postgresql.git checkout

set -eux

PGHOME=/usr/local/pgsql
PGDATA=$PGHOME/data
PGLOG=$PGDATA/log
PGBIN=$PGHOME/bin

# check we are in the correct directory before invoking git clean
grep 'PostgreSQL Database Management System' README

git clean -xdf
./configure --enable-cassert
make -j$(nproc)
make install

PATH=$PGBIN:$PATH

pg_ctl -D $PGDATA stop || :
rm -rf $PGDATA

initdb -D $PGDATA
cat >> $PGDATA/postgresql.conf <<EOF
port = 5430
unix_socket_directories = '/tmp'
fsync = off
EOF

pg_ctl -D $PGDATA -l $PGLOG start

PGHOST=/tmp PGPORT=5430 make installcheck
