#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that retrieves a dataset of Wikipedia articles based on their
importance ratings.

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
import re
import logging

import MySQLdb

class ImportanceRating:
    def __init__(self, talk_page_id, talk_revision_id, talk_page_title,
                 talk_is_archive,
                 art_page_id = -1, art_revision_id = -1,
                 art_is_redirect = 0):
        '''
        Instantiate a set of importance ratings. Note that ratings might
        be applied to talk pages that do not have an associated article
        (e.g. "Talk:Tribes_of_Montenegro/Archive 1" contains ratings,
         but there is no associated article). In that case the article page ID
        and revision ID should both be -1.

        :param talk_page_id: page ID of the associated talk page
        :type talk_page_id: int

        :param talk_revision_id: revision ID of the most recent revision of
                                 the talk page at the time the dataset
                                 was gathered.

        :param talk_page_title: title of the talk page (without namespace)
        :type talk_page_title: str

        :param talk_is_archive: is the talk page an archive page?
        :type talk_is_archive: int

        :param art_page_id: page ID of the rated article
        :type art_page_id: int

        :param art_revision_id: revision ID of the most recent revision of
                                the rated article at the time the dataset
                                was gathered.
        :type art_revision_id: int

        :param art_is_redirect: is the article a redirect
        :type art_is_redirect: int
        '''

        self.page_id = art_page_id
        self.revision_id = art_revision_id
        self.is_redirect = art_is_redirect
        self.talk_page_id = talk_page_id
        self.talk_page_title = talk_page_title
        self.talk_revision_id = talk_revision_id
        self.talk_is_archive = talk_is_archive

        self.imp_ratings = []
        self.wikiprojects = []

    def add_importance_rating(self, imp_rating):
        self.imp_ratings.append(imp_rating)

class Retriever:
    def __init__(self):

        self.imp_ratings = ['Top', 'High', 'Mid', 'Low']

        self.lang = 'en'
        self.db_conf = "~/replica.my.cnf"
        self.db_server = "enwiki.labsdb"
        self.db_name = "enwiki_p"
        self.db_conn = None
        self.db_cursor = None

        ## Number of talk pages we process at a time when grabbing
        ## all importance rating categories.
        self.slice_size = 500

    def db_connect(self):
        '''
        Connect to the database. Returns True if successful.
        '''
        self.db_conn = None
        self.db_cursor = None
        try:
            self.db_conn = MySQLdb.connect(db=self.db_name,
                                           host=self.db_server,
                                           charset='utf8',
                                           use_unicode=True,
                                           read_default_file=os.path.expanduser(self.db_conf))
            self.db_cursor = self.db_conn.cursor(MySQLdb.cursors.SSDictCursor)
        except MySQLdb.Error as e:
            logging.error('Unable to connect to database')
            logging.error('{} : {}'.format(e[0], e[1]))

        if self.db_conn:
            return(True)

        return(False)

    def db_disconnect(self):
        '''Close our database connections.'''
        try:
            self.db_cursor.close()
            self.db_conn.close()
        except:
            pass

        return()
        
        
    def get_dataset(self, output_filename):
        '''
        Fetch a dataset of all importance-rated articles for a given Wikipedia
        edition and write information out to the given file as a TSV.

        :param output_filename: Path to the output TSV file
        :type output_filename: str
        '''

        ## Note: We're doing this in two stages. First we get all articles
        ##       and talk pages with a given importance rating. Then we'll
        ##       grab all importance categories for all those articles.
        
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

        ## Query to get all the importance-related categories that a given
        ## article belongs to.
        imp_query = '''SELECT cl_from, cl_to
                       FROM categorylinks
                       WHERE cl_to LIKE "%-importance\\_%\\_articles"
                       AND cl_from IN ({talk_pages})'''

        ## Regular expression to extract WikiProject name from
        ## the name of an importance category
        wp_name_re = re.compile('(Top|High|Mid|Low|Unknown|NA)-importance_(.+)_articles')
        
        ## Maps talk page ID to related ImportanceRating objects
        talk_pages = {}

        if not self.db_connect():
            logging.error('Unable to connect to database')
            return()
        
        ## Open the output file and write out the header
        ## (we'll then later append to this file)
        with open(output_filename, 'w+', encoding='utf-8') as outfile:
            outfile.write('talk_page_id\ttalk_revision_id\ttalk_page_title\ttalk_is_archive\tpage_id\trevision_id\tis_redirect\timportance_ratings\twikiprojects\n')
        
        ## for each of the importance categories
        for imp_cat in self.imp_ratings:
            ## List of pages in this rating category we need to grab
            ## all data for
            seen_pages = []
            
            imp_cat_match = '{imp}-importance%articles'.format(imp=imp_cat)
            
            self.db_cursor.execute(art_query,
                                   {'imp_category': imp_cat_match})
            done = False
            while not done:
                row = self.db_cursor.fetchone()
                if not row:
                    done = True
                    continue

                ## Did we already process this page previously?
                ## (e.g. because it also has a higher rating)
                if row['talk_page_id'] in talk_pages:
                    continue
                
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

                talk_pages[talk_page_id] = ImportanceRating(talk_page_id,
                                                            talk_revision_id,
                                                            talk_page_title,
                                                            talk_is_archive,
                                                            art_page_id,
                                                            art_revision_id,
                                                            art_is_redirect)
                seen_pages.append(talk_page_id)

            logging.info('Fetching all importance rating categories for {} pages'.format(len(seen_pages)))
                
            ## For all unseen articles in this category, grab all their
            ## importance ratings and associated WikiProject names
            i = 0
            while i < len(seen_pages):
                logging.info('Grabbing subset starting from {}'.format(i))

                talkpage_ids = seen_pages[i : i + self.slice_size]
                self.db_cursor.execute(imp_query.format(
                    talk_pages=",".join([str(page_id) for page_id
                                         in talkpage_ids])))
                done = False
                while not done:
                    row = self.db_cursor.fetchone()
                    if not row:
                        done = True
                        continue

                    talk_page_id = row['cl_from']
                    imp_category = row['cl_to'].decode('utf-8')
                
                    ## Extract the importance rating and WikiProject name
                    wikiproj_match = wp_name_re.match(imp_category)

                    if not wikiproj_match:
                        logging.warning('unable to match category name: {}'.format(imp_category))
                        continue

                    ## The importance rating should now be in group(1)
                    ## and the WikiProject name be in group(2)
                    imp_rating = wikiproj_match.group(1).lower()
                    wp_name = wikiproj_match.group(2).lower().replace('_', ' ')

                    rating_obj = talk_pages[talk_page_id]
                    rating_obj.imp_ratings.append(imp_rating)
                    rating_obj.wikiprojects.append(wp_name)

                ## Step forward and iterate
                i += self.slice_size

            ## We can now write out info about all these pages
            ## to the output file
            with open(output_filename, 'a', encoding='utf-8') as outfile:
                for talk_page_id in seen_pages:
                    rating_obj = talk_pages[talk_page_id]
                    outfile.write('{0.talk_page_id}\t{0.talk_revision_id}\t{0.talk_page_title}\t{0.talk_is_archive}\t{0.page_id}\t{0.revision_id}\t{0.is_redirect}\t{importance_ratings}\t{wikiprojects}\n'.format(rating_obj, importance_ratings=",".join(rating_obj.imp_ratings), wikiprojects="::".join(rating_obj.wikiprojects)))

        ## OK, all done!
        self.db_disconnect()
        return()
        
def main():
    # Parse CLI options
    import argparse;

    cli_parser = argparse.ArgumentParser(
        description="Program to generate a dataset of articles across all importance categories"
        )

    ## Path to the output file
    cli_parser.add_argument('output_filename', type=str,
                            help="path to the output TSV file")

    cli_parser.add_argument("-v", "--verbose", action="store_true",
                            help="write informational output");

    args = cli_parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)


    retriever = Retriever()
    retriever.get_dataset(args.output_filename)
        
    return()

if __name__ == '__main__':
    main()
