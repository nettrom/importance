#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script to read in a WikiProject dataset and populate it with
views using data from our table on the staging server.

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

import db

from yaml import load

def populate_views(project_config_file, dbstore_config_file):
    '''
    Read in the dataset defined in the configuration files and grab view
    data from the dbstore server for all page IDs in the dataset, replacing
    the view data column.

    :param project_config_file: path to the WikiProject's YAML config file
    :type project_config_file: str

    :param dbstore_config_file: path to the YAML config file with configuration
                                parameters for connecting to the dbstore server
    :type dbstore_config_file: str
    '''

    get_views_query = '''SELECT p.page_id, n.page_id, num_views
                         FROM {page_table} p
                         LEFT JOIN {newpage_table} n
                         USING (page_id)
                         WHERE page_id=%(page_id)s'''

    get_newpage_views_query = '''SELECT num_views
                                 FROM {newpage_data_table}
                                 WHERE page_id=%(page_id)s'''
    
    with open(project_config_file) as infile:
        project_config = load(infile)

    with open(dbstore_config_file) as infile:
        dbstore_config = load(infile)

    # connect to the database
    db_conn = db.connect(dbstore_config['db_server'],
                         dbstore_config['db_name'],
                         dbstore_config['db_config_file'])
    
    # read in the dataset...
    lines = []
    with open(project_config['dataset']) as infile, db.cursor(
                db_conn, 'dict') as db_cursor:
        lines.append(infile.readline().strip())
        
        for line in infile:
            cols = line.strip().split('\t')

            page_id = cols[0]
            num_views = cols[4]
            
            db_cursor.execute(get_views_query.format_map(dbstore_config),
                              {'page_id': page_id})
            for row in db_cursor.fetchall():
                is_new = row['n.page_id']
                num_views = row['num_views']

            if is_new:
                db_cursor.execute(
                    get_newpage_views_query.format_map(dbstore_config),
                    {'page_id': page_id})

                views = []
                for row in db_cursor.fetchall():
                    views.append(row['num_views'])

                # For now, we'll just use mean number of views
                if views:
                    num_views = round(sum(views)/len(views))
                else:
                    num_views = 0

            # and replace the number of views with those from the database
            cols[4] = str(num_views)
            lines.append('\t'.join(cols))
            

    with open(project_config['dataset'], 'w') as outfile:
        outfile.write('\n'.join(lines))

    # ok, done
    return()

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to replace views in a WikiProject dataset with views from the dbstore table"
    )

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    cli_parser.add_argument("project_config_file",
                            help="path to the YAML configuration file for the WikiProject")

    cli_parser.add_argument("dbstore_config_file",
                            help="path to the YAML configuration file for the dbstore database and tables")
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    populate_views(args.project_config_file, args.dbstore_config_file)
        
    return()

if __name__ == '__main__':
    main()
    
