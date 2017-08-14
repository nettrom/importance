#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Library with various functionality for executing Hadoop queries
using Hive, and importing/exporting tables between MySQL and Hadoop.

Copyright (c) 2017 Morten Wang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

import logging
import subprocess

from datetime import timedelta

def make_where_datespan(start_date, end_date, prefix=''):
    '''
    The data in Hadoop might be partitioned by year, month, and day,
    so we'll have to have all dates in the range in our where clause.

    :param start_date: first date to include in the range
    :type start_date datetime.date

    :param end_date: last date to include in the range
    :type end_date: datetime.date

    :param prefix: prefix to use in front of year/month/day variable names
    :type prefix: str
    '''

    one_day = timedelta(days=1)
    i = start_date
    dates = [] # string of dates
    while i <= end_date:
        dates.append('({p}year={y} AND {p}month={m} AND {p}day={d})'.format(
            p=prefix, y=i.year, m=i.month, d=i.day))

        i += one_day

    return(' OR '.join(dates))

def exec_beeline(query, output_file=None, priority=False):
    '''
    Execute a call to `beeline` to execute the given query, as priority
    if set.

    :param query: the HQL query to execute
    :type query: str

    :param output_file: path where the result of the query will be piped to
    :type output_file: str

    :param priority: ask to give this query priority?
    :type priority: bool
    '''

    if priority:
        query = "SET mapreduce.job.queuename=priority;{}".format(query)

    command = 'beeline -e "{}"'.format(query)
    if output_file:
        command = "{} > {}".format(command, output_file)
        
    logging.info('executing {}'.format(command))
    retcode = None
    try:
        retcode = subprocess.call(command, shell=True)
        if retcode < 0:
            logging.error("child was terminated by signal {}".format(-retcode))
        else:
            logging.info("child returned {}".format(retcode))
    except OSError as e:
        logging.error("Beeline execution failed: {}".format(e))
    return(retcode)

def exec_hql(hql_file, output_file=None):
    '''
    Execute a call to `beeline` so that the given HQL file is an input file
    with query commands.  Optionally redirecting the output to the given
    path. Note that handling the output file is left to the caller.

    :param hql_file: path to the HQL file to execute
    :type hql_file: str

    :param output_file: path to the output file
    :type output_file: str
    '''

    command = 'beeline -f {}'.format(hql_file)
    if output_file:
        command = '{} > {}'.format(command, output_file)

    logging.info('`executing {}`'.format(command))
    retcode = None
    try:
        retcode = subprocess.call(command, shell=True)
        if retcode < 0:
            logging.error("child was terminated by signal {}".format(-retcode))
        else:
            logging.info("child returned {}".format(retcode))
    except OSError as e:
        logging.error("Beeline HQL file execution failed: {}".format(e))
    return(retcode)

def sqoop_export_table(hostname, dest_db, target_table, hive_table_path,
                       username, password_file,
                       extra_opts=None):
    '''
    Use `sqoop export` to export a datable from Hadoop into a MySQL database.
    The table has to exist in the database before running the export.

    :param hostname: hostname of the MySQL database server
    :type hostname: str

    :param dest_db: destination dataabase
    :type dest_db: str

    :param target_table: table to import data into
    :type target_table: str

    :param hive_table_path: path in the Hadoop file system to the table
                            that will be exported
    :type hive_table_path: str

    :param username: username to use when authentication to the MySQL server
    :type username: str

    :param password_file: path to the password file for authentication
    :type password_file: str

    :param extra_opts: additional options to pass to `sqoop`
    :type extrap_opts: str
    '''

    scoop_command = """sqoop export \
  --connect jdbc:mysql://{hostname}/{database} \
  --username {username} \
  --password-file {pwd_file} \
  --export-dir {hive_table_path} \
  --table {target_table} \
  --input-fields-terminated-by '\001' \
  --mysql-delimiters""".format(hostname=hostname, database=dest_db,
                               username=username, pwd_file=password_file,
                               hive_table_path=hive_table_path,
                               target_table=target_table)
    if extra_opts:
        scoop_command = "{} {}".format(sqoop_command, extra_opts)

    retcode = None
    try:
        retcode = subprocess.call(scoop_command, shell=True)
        if retcode < 0:
            logging.warning("child was terminated by signal {}".format(-retcode))
        else:
            logging.info("child returned {}".format(retcode))
    except OSError as e:
        logging.error("Sqoop execution failed: {}".format(e))

    return(retcode)
    
def sqoop_import_table(hostname, src_db, query, hive_db, hive_table,
                       split_column, username, password_file, temp_directory):
    '''
    Use `sqoop import` to import a table from a database using a specific query.
    The table is imported into the given Hive database and table and split on
    the given column.

    :param hostname: hostname of the database server we're exporting from
    :type hostname: str

    :param src_db: name of the database we're exporting from
    :type src_db: str

    :param query: the SQL query to use for the export, note that per the sqoop
                   manual this query must include a "WHERE $CONDITIONS" clause
                   to allow for parallelisation of the import:
                   https://sqoop.apache.org/docs/1.4.5/SqoopUserGuide.html#_free_form_query_imports
    :type query: str

    :param hive_db: name of the Hive database to store the table in
    :type hive_db: str

    :param hive_table: name of the imported table in the Hive database
    :type hive_table: str

    :param split_column: name of the column to split the data on to allow
                         for parallelisation of the import
    :type split_column: str

    :param username: username to use when connecting to the replicated database
    :type username: str

    :param password_file: path to the password file to use when authenticating
    :type password_file: str
    '''

    scoop_command = """sqoop import \
  --connect jdbc:mysql://{hostname}/{database} \
  --target-dir {temp_dir} \
  --username {username} \
  --password-file {pwd_file} \
  --split-by {split_column} \
  --hive-import \
  --hive-database {hive_db} \
  --create-hive-table \
  --hive-table {hive_table} \
  --hive-delims-replacement ' ' \
  --query '{query}'"""

    retcode = None
    try:
        retcode = subprocess.call(scoop_command.format(
            hostname=hostname, database=src_db, temp_dir=temp_directory,
            username=username, pwd_file=password_file, split_column=split_column,
            hive_db=hive_db, hive_table=hive_table, query=query),
                                  shell=True)
        if retcode < 0:
            logging.warning("child was terminated by signal {}".format(-retcode))
        else:
            logging.info("child returned {}".format(retcode))
    except OSError as e:
        logging.error("Sqoop execution failed: {}".format(e))

    return(retcode)
