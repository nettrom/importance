#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that gathers a snapshot of importance-rated articles for a given
WikiProject.

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
import wikiproject as wp

from yaml import load

class ProjectGrabber():
    def __init__(self):
        '''
        Instantiate the grabber.
        '''

        self.lang = 'en'
        self.db_conf = "~/replica.my.cnf"
        self.db_server = "enwiki.labsdb"
        self.db_name = "enwiki_p"
        self.db_conn = None
        self.db_cursor = None

        ## The importance classes we are interested in. Note that we
        ## discard "Unknown" and "NA" classes as they are either not
        ## a rating, or describing something that's not an article.
        self.imp_classes = ['Top',
                            'High',
                            'Mid',
                            'Low']

        
    def grab_project(self, config_file):
        '''
        Read in the given YAML configuration file describing a WikiProject,
        grab a dataset of importance-rated articles from this project,
        and write out a TSV of that data to the snapshot file path
        defined in the configuration.

        :param config_file: path to the YAML configuration file
        :type config_file: str
        '''

        ## Query to get information about articles and talk pages based on
        ## their importance rating. This assumes regularity in the importance
        ## rating category structure.
        art_query = '''SELECT DISTINCT art.page_id AS art_page_id,
                              art.page_latest AS art_revision_id,
                              art.page_is_redirect AS art_is_redirect,
                              talk.page_id AS talk_page_id,
                              talk.page_title AS talk_page_title,
                              talk.page_latest AS talk_revision_id
                       FROM page talk
                       JOIN categorylinks
                       ON page_id=cl_from
                       LEFT JOIN page art
                       ON (art.page_title=talk.page_title
                           AND art.page_namespace=0)
                       WHERE cl_to LIKE %(imp_category)s
                       AND talk.page_namespace=1'''
        
        # read in the configuration file
        with open(config_file, 'r') as infile:
            proj_conf = load(infile)

        db_conn = db.connect(self.db_server, self.db_name, self.db_conf)
        if db_conn is None:
            logging.error("Unable to connect to database")
            return()

        ## List of all pages rated by the WikiProject
        all_pages = list()
        
        # for each of the importance classes:
        for imp_class in self.imp_classes:
            logging.info('grabbing {}-importance articles'.format(imp_class))

            with db.cursor(db_conn, 'dict') as db_cursor:
                db_cursor.execute(art_query,
                    {'imp_category': proj_conf['importance categories'][imp_class].replace(' ', '_')})
                ## Not too many articles in these categories, so fetchall()
                ## should be okay.
                for row in db_cursor.fetchall():
                    talk_page_id = row['talk_page_id']
                    talk_revision_id = row['talk_revision_id']
                    talk_page_title = row['talk_page_title'].decode('utf-8')

                    art_page_id = row['art_page_id']
                    art_revision_id = row['art_revision_id']
                    art_is_redirect = row['art_is_redirect']
                    
                    talk_is_archive = 0
                    if '/archive' in talk_page_title.lower():
                        talk_is_archive = 1

                    if not art_page_id:
                        art_page_id = -1
                    if not art_revision_id:
                        art_revision_id = -1
                    if art_is_redirect is None:
                        art_is_redirect = 0

                    all_pages.append(wp.RatedPage(talk_page_id,
                                                  talk_revision_id,
                                                  talk_page_title,
                                                  talk_is_archive,
                                                  imp_class,
                                                  art_page_id,
                                                  art_revision_id,
                                                  art_is_redirect))

        # write out the snapshot to the file defined in the configuration
        with open(proj_conf['snapshot file'], 'w', encoding='utf-8') as outfile:
            outfile.write('talk_page_id\ttalk_revision_id\ttalk_page_title\ttalk_is_archive\tart_page_id\tart_revision_id\tart_is_redirect\timportance_rating\n') # write header

            for page in all_pages:
                outfile.write('{0.talk_page_id}\t{0.talk_revision_id}\t{0.talk_page_title}\t{0.talk_is_archive}\t{0.page_id}\t{0.revision_id}\t{0.is_redirect}\t{0.importance_rating}\n'.format(page))

        # ok, done
        return()

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to grab a snapshot of a given WikiProject's importance-rated articles"
    )

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    cli_parser.add_argument("config_file",
                            help="path to the YAML configuration file for the WikiProject")
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    grab = ProjectGrabber()
    grab.grab_project(args.config_file)
        
    return()

if __name__ == '__main__':
    main()
    

