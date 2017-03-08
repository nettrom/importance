#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that processes a dataset of rated articles and extends
the dataset with with information on the number of inlinks and
views for those articles.

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
from datetime import date, timedelta

import requests
from urllib.parse import quote

import MySQLdb

class ArticleData:
    def __init__(self, page_id, page_title):
        self.page_id = page_id
        self.page_title = page_title
        self.num_inlinks = 0
        self.num_views = 0.0

class DataGetter:
    def __init__(self):
        self.lang = 'en'
        self.db_conf = "~/replica.my.cnf"
        self.db_server = "enwiki.labsdb"
        self.db_name = "enwiki_p"
        self.db_conn = None
        self.db_cursor = None

        self.slice_size = 50 # batch size for inlink count retrieval

        self.pageview_url = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        self._headers = {
            'User-Agent': 'SuggestBot/1.0',
            'From:': 'morten@cs.umn.edu',
            }
        
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

    def extend_dataset(self, input_filename, output_filename, num_view_days,
                       id_col, title_col):
        '''
        Read in a dataset of importance-rated articles, grab number of
        inlinks and views for those articles, and write out an extended
        dataset with those columns added.

        :param input_filename: path to the input file
        :type input_filename: str

        :param output_filename: path to the output file
        :type output_filename: str

        :param num_view_days: number of days to average views over
        :type num_view_days: int

        :param id_col: zero-based index of the page ID column
        :type id_col: int

        :param title_col: zero-based index of the page title column
        :type title_col: int
        '''

        ## SQL query to get the number of inlinks for a set of pages.
        ## This query is from
        ## https://github.com/nettrom/suggestbot/blob/master/tool-labs/link-rec/inlink-table-updater.py
        inlink_query = '''SELECT
                          p.page_id AS page_id,
                          COUNT(*) AS num_inlinks
                          FROM page p JOIN pagelinks pl
                          ON (p.page_namespace=pl.pl_namespace
                              AND p.page_title=pl.pl_title)
                          WHERE p.page_id IN ({idlist})
                          AND pl.pl_from_namespace=0
                          GROUP BY p.page_id'''

        ## Mapping page_ids to article data
        articles = {}

        with open(input_filename, 'r', encoding='utf-8') as infile:
            infile.readline() # skip the header
            for line in infile:
                cols = line.rstrip('\n').split('\t')
                page_id = cols[id_col]
                page_title = cols[title_col].replace('_', ' ')
                articles[page_id] = ArticleData(page_id, page_title)

        logging.info('read dataset, getting pageviews...')
                
        ## get view data for all pages
        api_session = requests.Session()
        
        for (page_id, page_data) in articles.items():
            page_data.num_views = self.get_views_from_api(
                page_data.page_title, num_view_days,
                http_session=api_session)

        logging.info('got pageviews, getting inlinks counts...')

        if not self.db_connect():
            logging.error('unable to connect to database')
            return()
        
        ## get inlink numbers of batches of pages
        page_ids = list(articles.keys())
        i = 0
        while i < len(page_ids):
            subset = page_ids[i:i+self.slice_size]
            self.db_cursor.execute(inlink_query.format(
                idlist = ','.join(subset)))

            for row in self.db_cursor.fetchall():
                page_id = str(row['page_id'])
                page_data = articles[page_id]
                page_data.num_inlinks = row['num_inlinks']

            # ok, move forward and iterate
            i += self.slice_size

        logging.info('got all data, writing out new dataset...')
        
        ## read in the current dataset, write out the extended one
        with open(input_filename, 'r', encoding='utf-8') as infile:
            with open(output_filename, 'w', encoding='utf-8') as outfile:
                header_line = infile.readline().rstrip('\n')
                outfile.write('{header}\tnum_inlinks\tnum_views\n'.format(
                    header=header_line))

                for line in infile:
                    line = line.rstrip('\n')
                    cols = line.split('\t')
                    page_data = articles[cols[id_col]]

                    outfile.write(
                        '{0}\t{1.num_inlinks}\t{1.num_views}\n'.format(
                            line, page_data))

        # ok, done
        return()

    def get_views_from_api(self, page_title, num_view_days,
                           http_session=None):
        '''
        Make a request to the Wikipedia pageview API to retrieve page views
        for the past `num_view_days` days and return the avg number of views.

        :param page_title: the title of the page we're grabbing views for
        :type page_title: str

        :param num_view_days: the number of days of view data to average over
        :type num_view_days: int
        
        :param http_session: session to use for HTTP requests
        :type http_session: requests.session

        This method is from
        https://github.com/nettrom/suggestbot/blob/master/suggestbot/utilities/page.py
        '''
        # make a URL request to self.pageview_url with the following
        # information appendend:
        # languageCode + '.wikipedia/all-access/all-agents/' + uriEncodedArticle + '/daily/' +
        # startDate.format(config.timestampFormat) + '/' + endDate.format(config.timestampFormat)
        # Note that we're currently not filtering out spider and bot access,
        # we might consider doing that.

        # Note: Per the below URL, daily pageviews might be late, therefore
        # we operate on an n-days basis starting a couple of days back. We have
        # no guarantee that the API has that much data, though.
        # https://wikitech.wikimedia.org/wiki/Analytics/PageviewAPI#Updates_and_backfilling

        if not http_session:
            http_session = requests.Session()
        
        today = date.today()
        start_date = today - timedelta(days=num_view_days + 1)
        end_date = today - timedelta(days=2)

        # test url for Barack Obama
        # 'https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/Barack%20Obama/daily/20160318/20160331'
        
        url = '{api_url}{lang}.wikipedia/all-access/all-agents/{title}/daily/{startdate}/{enddate}'.format(api_url=self.pageview_url, lang=self.lang, title=quote(page_title, safe=''), startdate=start_date.strftime('%Y%m%d'), enddate=end_date.strftime('%Y%m%d'))

        view_list = []
        num_attempts = 0
        max_url_attempts = 3
        while not view_list and num_attempts < max_url_attempts:
            r = http_session.get(url, headers=self._headers)
            num_attempts += 1
            if r.status_code == 200:
                try:
                    response = r.json()
                    view_list = response['items']
                except ValueError:
                    logging.warning('Unable to decode pageview API as JSON')
                    continue # try again
                except KeyError:
                    logging.warning("Key 'items' not found in pageview API response")
            else:
                logging.warning('Pageview API did not return HTTP status 200')

        avg_views = 0
        if view_list:
            # The views should be in chronological order starting with
            # the oldest date requested. Iterate and sum.
            total_views = 0
            days = 0
            for item in view_list:
                try:
                    total_views += item['views']
                    days += 1
                except KeyError:
                    # no views for this day?
                    pass
            avg_views = total_views/days
                
        return(avg_views)

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to extend a dataset with article rating data with number of inlinks and views"
    )

    cli_parser.add_argument("input_filename", type=str,
                            help="path to the input TSV dataset")
    
    cli_parser.add_argument("output_filename", type=str,
                            help="path to the output TSV extended dataset")

    cli_parser.add_argument("num_view_days", type=int,
                            help="number of days to get view data for")

    cli_parser.add_argument("id_col_idx", type=int,
                            help="zero-based index of the page ID column")
    
    cli_parser.add_argument("title_col_idx", type=int,
                            help="zero-based index of the page title column")

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    getter = DataGetter()
    getter.extend_dataset(args.input_filename, args.output_filename,
                          args.num_view_days, args.id_col_idx,
                          args.title_col_idx)
    return()

if __name__ == '__main__':
    main()
    

