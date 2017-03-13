#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that processes a dataset of rated articles and gathers view data
for these articles.

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

from time import sleep
from datetime import datetime, date, timedelta

import requests
from urllib.parse import quote

import MySQLdb

class ArticleData:
    def __init__(self, page_id, page_title):
        self.page_id = page_id
        self.page_title = page_title

        ## dict mapping date to views
        self.views = {}

class ViewGetter:
    def __init__(self):
        self.lang = 'en'
        
        self.pageview_url = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"

        self._headers = {
            'User-Agent': 'SuggestBot/1.0',
            'From:': 'morten@cs.umn.edu',
            }

    def get_views(self, input_filename, output_filename, end_date,
                  num_days, id_col_idx, title_col_idx):
        '''
        Process the given dataset and gather view data for articles,
        then write that view data out to a new dataset.

        :param input_filename: path to the dataset TSV file
        :type input_filename: str

        :param output_filename: path to the view dataset TSV file
        :type output_filename: str

        :param end_date: last day we are gathering view data for
                         (format: YYYYMMDD)
        :type end_date: str

        :param num_days: number of days of data we're gathering
        :type num_days: int

        :param id_col_idx: zero-based column index of the page ID column
        :type id_col_idx: int

        :param title_col_id: zero-based column index of the page title column
        :type title_col_id: int
        '''

        ## Conver end_date to a date object
        end_date_obj = datetime.strptime(end_date, '%Y%m%d').date()
        
        ## All articles
        articles = []
        
        ## read in the dataset
        with open(input_filename, 'r', encoding='utf-8') as infile:
            infile.readline() # skip header
            for line in infile:
                cols = line.rstrip('\n').split('\t')
                page_id = cols[id_col_idx]
                page_title = cols[title_col_idx]
                articles.append(ArticleData(page_id, page_title))
            
        ## process all the pages
        api_session = requests.Session()
        
        for page_data in articles:
            page_data.views = self.get_views_from_api(
                page_data.page_title, end_date_obj, num_days,
                http_session=api_session)
            sleep(0.05)

        ## write out new dataset
        with open(output_filename, 'w', encoding='utf-8') as outfile:
            outfile.write('page_id\tdate\tviews\n')
            for page_data in articles:
                print('found {} views for {}'.format(len(page_data.views),
                                                     page_data.page_title))
                for (view_date, view_num) in page_data.views.items():
                    outfile.write('{}\t{}\t{}\n'.format(page_data.page_id,
                                                        view_date,
                                                        view_num))

        # ok, done
        return()
        
    def get_views_from_api(self, page_title, end_date, num_view_days,
                           http_session=None):
        '''
        Make a request to the Wikipedia pageview API to retrieve page views
        for the past `num_view_days` days before `start_date` and return
        a dictionary with these views.

        :param page_title: the title of the page we're grabbing views for
        :type page_title: str

        :param end_date: the last day we are gathering views for
        :type end_date: datetime.date

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

        ## Note: the API returns data also for end_date, so the start date
        ## is num_view_days -1 as it's an inclusive date range.
        start_date = end_date - timedelta(days=num_view_days -1)

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

        views_by_date = {}
        for item in view_list:
            try:
                views = item['views']
                date = datetime.strptime(item['timestamp'],
                                         '%Y%m%d%H').date()
                views_by_date[date] = int(views)
            except KeyError:
                # no views for this day?
                pass
                
        return(views_by_date)

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to gather additional views for a dataset of articles"
    )

    cli_parser.add_argument("input_filename", type=str,
                            help="path to the input TSV dataset")
    
    cli_parser.add_argument("output_filename", type=str,
                            help="path to the output TSV extended dataset")

    cli_parser.add_argument("end_date", type=str,
                            help="last day to gather view data for (format: YYYYMMDD)")

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

    getter = ViewGetter()
    getter.get_views(args.input_filename, args.output_filename,
                     args.end_date, args.num_view_days,
                     args.id_col_idx, args.title_col_idx)

    return()

if __name__ == '__main__':
    main()
    

