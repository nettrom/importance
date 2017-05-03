#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that identifies any articles that are disambiguation pages
in the snapshot dataset from a WikiProject.

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

class DisambiguationChecker():
    def __init__(self):
        '''
        Instantiate the grabber.
        '''

        self.lang = 'en'
        self.disambig_cat = 'All_disambiguation_pages'
        self.db_conf = "~/replica.my.cnf"
        self.db_server = "enwiki.labsdb"
        self.db_name = "enwiki_p"
        self.db_conn = None
        self.db_cursor = None

        ## How many pages do we process at a time?
        self.slice_size = 50

    def check_disambiguations(self, config_file):
        '''
        Read in the configuration file, grab the associated snapshot dataset,
        and identify any article in the dataset that is a disambiguation page.
        
        :param config_file: path to the YAML configuration file
        :type config_file: str
        '''

        ## Note that we do not do a check against Wikidata, because we're going
        ## to grab that information later anyway, and can then check if we found
        ## additional disambiguation pages.
        
        disambig_query = '''SELECT page_id, page_title
                            FROM page
                            JOIN categorylinks
                            ON page_id=cl_from
                            WHERE page_id IN ({idlist})
                            AND cl_to=%(disambig_cat)s'''
        
        # read in the configuration file
        with open(config_file, 'r') as infile:
            proj_conf = load(infile)
            
        ## page IDs of all pages in the dataset
        all_pages = list()

        ## Read in the snapshot dataset
        with open(proj_conf['snapshot file'], 'r', encoding='utf-8') as infile:
            infile.readline() # skip header

            for line in infile:
                cols = line.strip().split('\t')

                ## cols[6] is the "article is a redirect" column, if it's
                ## 1 we want to ignore this page:
                if cols[6] == "1":
                    continue

                ## cols[4] is the page_id of the article in question
                all_pages.append(cols[4])

        db_conn = db.connect(self.db_server, self.db_name, self.db_conf)
        if db_conn is None:
            logging.error("Unable to connect to database")
            return()
                
        ## Pages we've identified are disambiguation pages, stored as
        ## dictionaries with keys for "page_id" and "page_title"
        disambigs = list()

        i = 0
        while i < len(all_pages):
            subset = all_pages[i:i+self.slice_size]

            with db.cursor(db_conn, 'dict') as db_cursor:
                ## Use .format() to add the page IDs, but send the
                ## category name as a standard parameter through a dict.
                db_cursor.execute(
                    disambig_query.format(idlist=",".join(subset)),
                    {'disambig_cat': self.disambig_cat})
        
                for row in db_cursor.fetchall():
                    disambigs.append(
                        {'page_id': row['page_id'],
                         'page_title': row['page_title'].decode('utf-8')})

            ## done with this slice, add and iterate
            i += self.slice_size

        ## ok, done, write out
        with open(proj_conf['disambiguation file'],
                  'w', encoding='utf-8') as outfile:
            outfile.write('page_id\tpage_title\n') # write header
            for page_dict in disambigs:
                outfile.write('{}\t{}\n'.format(page_dict['page_id'],
                                                page_dict['page_title']))

        ## ok, done
        return()
    
def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to process a snapshot for a WikiProject and identify articles that are disambiguation pages"
    )

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    cli_parser.add_argument("config_file",
                            help="path to the YAML configuration file for the WikiProject")
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    checker = DisambiguationChecker()
    checker.check_disambiguations(args.config_file)
        
    return()

if __name__ == '__main__':
    main()
    

