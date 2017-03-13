#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that processes a dataset of rated articles and checks each article's
talk page in order to verify how many templates with importance ratings are
on their talk pages.

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

import pywikibot
from pywikibot.pagegenerators import PreloadingGenerator, PagesFromTitlesGenerator

import mwparserfromhell as mwp

class TalkPage:
    def __init__(self, page_id):
        self.page_id = page_id
        self.page_title = ''
        self.num_ratings = 0

class TalkpageProcessor:
    def __init__(self):
        ## Language code of the Wikipedia edition we're processing for
        self.lang = 'en'

        ## Do 10 at a time in case the talk page is huge
        self.slice_size = 10

        self.db_conf = "~/replica.my.cnf"
        self.db_server = "enwiki.labsdb"
        self.db_name = "enwiki_p"
        self.db_conn = None
        self.db_cursor = None

        ## Names of templates with a "priority" parameter.
        self.priority_templates = []

    def db_connect(self):
        '''
        Connect to the database. Returns True if successful.
        '''
        self.db_conn = None
        self.db_cursor = None
        try:
            self.db_conn = MySQLdb.connect(db=self.db_name,
                                           host=self.db_server,
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

    def process_template(self, template):
        '''
        Process the template and return a list of any valid ratings
        found in it.
        '''
        
        ## Valid importance ratings
        VALID_RATINGS = set(['top','high','mid','low'])

        ## There are several cases where an importance rating might be found:
        ##
        ## 1: parameter named importance
        ## 2: sub-project importance parameters (e.g. WikiProject Africa
        ##    uses a "Djibouti-importance" parameter)
        ## 3: sub-project priority parameters (e.g. WikiProject Biography
        ##    uses a "filmbio-priority" parameter)
        ##
        ## Note that some WikiProjects use a "priority" parameter. We will
        ## ignore that parameter as we have yet to see an example where it
        ## results in a subsequent categorization of the article. As we're
        ## interested in knowing about them, we'll store the template names
        ## and write them out at the end.

        ratings = []

        if template.has('priority'):
            self.priority_templates.append(str(template.name.strip_code()))
        elif template.has('importance'):
            rating = str(template.get('importance').value.strip_code()).strip().lower()
            if rating in VALID_RATINGS:
                ratings.append(rating)

        for param in template.params:
            p_name = str(param.name.strip_code()).strip().lower()
            
            ## This regex is deliberately liberal because some projects
            ## use things like "&" in the parameter name.
            if re.search('.+-(priority|importance)$', p_name):
                rating = str(param.value.strip_code()).strip().lower()

                if rating in VALID_RATINGS:
                    ratings.append(rating)

        return(ratings)
        
    def check_talkpages(self, input_filename, output_filename,
                        id_col_idx):
        '''
        Go through all the pages in the given dataset of unanimously rated
        articles and check their talk pages in order to establish the number
        of actual importance ratings they have.

        :param input_filename: path to the TSV dataset
        :type input_filename: str

        :param output_filename: path to output TSV dataset
        :type output_filename: str

        :param id_col_idx: zero-based index of the page ID column
        :type id_col_idx: int
        '''

        ## SQL query to get page titles based on page IDs
        title_query = '''SELECT page_id, page_title
                         FROM page
                         WHERE page_id IN ({idlist})'''
        
        
        site = pywikibot.Site(self.lang)

        ## Mapping page IDs and titles to talk page data
        id_page_map = {}
        title_page_map = {}

        ## read in the dataset
        with open(input_filename, 'r', encoding='utf-8') as infile:
            infile.readline() # skip header
            for line in infile:
                cols = line.rstrip('\n').split('\t')
                page_id = cols[id_col_idx]
                id_page_map[page_id] = TalkPage(page_id)

        ## find the current page title of all the pages
        ## (ideally none of them should have incorrect page IDs)
        if not self.db_connect():
            logging.error('unable to connect to database')
            return()

        pageids = list(id_page_map.keys())
        i = 0
        while i < len(pageids):
            subset = pageids[i:i+self.slice_size]
            
            self.db_cursor.execute(title_query.format(
                idlist=','.join(subset)))

            for row in self.db_cursor.fetchall():
                page_id = str(row['page_id'])
                page_title = row['page_title'].decode('utf-8').replace('_', ' ')

                id_page_map[page_id].page_title = page_title
                title_page_map[page_title] = id_page_map[page_id]

            # ok, iterate
            i += self.slice_size

        self.db_disconnect()

        talkpage_titles = ["Talk:{}".format(title)
                           for title in title_page_map.keys()]
        for talkpage in PreloadingGenerator(
                PagesFromTitlesGenerator(talkpage_titles),
                                         step=self.slice_size):
            logging.info('processing {}'.format(talkpage.title()))

            ## The templates are at the top of the page, so if it's a long
            ## page, truncate to speed up parsing.
            try:
                content = talkpage.get()
            except pywikibot.exceptions.IsRedirectPage as e:
                logging.warning('{} is a redirect'.format(talkpage.title()))
                continue
                
            if len(content) > 8*1024:
                content = content[:8*1024]
                
            parsed_page = mwp.parse(content)
            for template in parsed_page.filter_templates(recursive=True):
                ratings = self.process_template(template)

                ## Sanity check
                if len({k:1 for k in ratings}) > 1:
                    logging.warning('{} has non-unanimous importance ratings'.format(talkpage.title()))
                else:
                    title_page_map[talkpage.title(withNamespace=False)].num_ratings += len(ratings)


        ## Write out all pages with priority templates, if any
        if self.priority_templates:
            print('We found the following templates with a "priority" parameter')
            for template in self.priority_templates:
                print('* {}'.format(template))
            print('')
                
        ## Write out a dataset of page ID and num ratings
        with open(output_filename, 'w', encoding='utf-8') as outfile:
            outfile.write('talk_page_id\ttalk_page_title\tnum_wpratings\n')
            for (page_id, page_data) in id_page_map.items():
                outfile.write('{0.page_id}\t{0.page_title}\t{0.num_ratings}\n'.format(page_data))

        ## ok, done
        return()

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to check talk pages for importance ratings"
    )

    cli_parser.add_argument("input_filename", type=str,
                            help="path to the input TSV dataset")
    
    cli_parser.add_argument("output_filename", type=str,
                            help="path to the output TSV extended dataset")

    cli_parser.add_argument("id_col_idx", type=int,
                            help="zero-based index of the page ID column")
    
    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)
        
    processor = TalkpageProcessor()
    processor.check_talkpages(args.input_filename, args.output_filename,
                              args.id_col_idx)
    return()

if __name__ == '__main__':
    main()
        
