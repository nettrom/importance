#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Library to connect to a given shared replicated Wikipedia database server.

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

import os
import logging

import MySQLdb
import MySQLdb.cursors

ctypes = {'dict': MySQLdb.cursors.DictCursor,
          'ss': MySQLdb.cursors.SSCursor,
          'ssdict': MySQLdb.cursors.SSDictCursor,
          'default': MySQLdb.cursors.Cursor
          }

def connect(server, database, config_file):
    '''
    Connect to a database server.

    :param server: the hostname of the server
    :type server: str

    :param database: the name of the database to use
    :type database: str

    :param config_file: path to the MySQL configuration file to use
                       (os.path.expanduser() is called on this path)
    :type config_file: str
    '''
    db_conn = None
    try:
        db_conn = MySQLdb.connect(db=database,
                                  host=server,
                                  read_default_file=os.path.expanduser(
                                      config_file))
    except MySQLdb.Error as e:
        logging.error('unable to connect to database')
        logging.error('{} : {}'.format(e[0], e[1]))

    return(db_conn)

def cursor(connection, cursor_type=None):
    '''
    Get a cursor connected to the given database connection.

    :param connection: an open database connection
    :type MySQLdb.Connection

    :param cursor_type: type of cursor we want back, one of either:
                        'dict': MySQLdb.cursor.DictCursor
                        'ss': MySQLdb.cursor.SSCursor
                        'ssdict': MySQLdb.cursor.SSDictCursor
                        if no type is specified, the default
                        (MySQLdb.cursors.Cursor) is returned
    :type cursor_type: str
    '''

    if cursor_type is None:
        cursor_type = 'default'
    return(connection.cursor(ctypes[cursor_type]))

def disconnect(connection):
    '''Close our database connections.'''
    try:
        connection.close()
    except:
        pass
    return()
