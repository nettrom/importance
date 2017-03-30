#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that gathers a dataset of importance-rated articles for a given
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

import os
import logging
from datetime import date, timedelta

from time import sleep

import requests
from urllib.parse import quote

import MySQLdb

class RatedPage():
    def __init__(self, talk_page_id, talk_revision_id, talk_page_title,
                 talk_is_archive, importance_rating,
                 art_page_id = -1, art_revision_id = -1,
                 art_is_redirect = 0):
        '''
        Instantiate a page with a given importance rating.  This is
        intended for pages within a specific WikiProject, meaning an
        article only has a single importance rating.

        :param talk_page_id: page ID of the associated talk page
        :type talk_page_id: int

        :param talk_revision_id: revision ID of the most recent revision of
                                 the talk page at the time the dataset
                                 was gathered.

        :param talk_page_title: title of the talk page (without namespace)
        :type talk_page_title: str

        :param importance_rating: the importance rating of the article
                                  in the current WikiProject
        :type importance_rating: str

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
        self.importance_rating = importance_rating

        self.n_proj_inlinks = -1
        self.n_inlinks = -1
        self.n_views = -1

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
        
        self.pageview_url = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        self._headers = {
            'User-Agent': 'SuggestBot/1.0',
            'From': 'morten@cs.umn.edu',
            }

        ## Number of articles we process at a time for inlink counts
        self.slice_size = 25

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

    def grab_project(self, project_name, output_file):
        '''
        Grab articles from the given project by importance.

        :param project_name: Name of the project we're grabbing articles from
        :type project_name: str

        :param output_file: Path to where dataset TSV file should be
        :type output_file: str
        '''

        ## Category Structure:
        ## "{imp}-importance {project name} articles"
        ## Where 'imp' is the importance rating (e.g. "High")
        ## and "project name" is the uncapitalized name (e.g. "medicine")

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

        ## Given a list of article pages (by page ID)
        ## JOIN with pagelinks to find all articles that link to this article
        ## JOIN with page to find the talk pages of all these articles
        ## WHERE the talk page is in a WikiProject-related category.
        ## Q: Do we count _all_ pages then? That might be useful, if
        ##    a given article has many redirects (e.g. for spelling),
        ##    that should make it more important.
        projlink_query = '''SELECT
                            p.page_id AS page_id,
                            COUNT(*) AS num_inlinks
                            FROM page p JOIN pagelinks pl
                            ON (p.page_namespace=pl.pl_namespace
                                AND p.page_title=pl.pl_title)
                            JOIN page lp
                            ON (lp.page_id=pl.pl_from)
                            JOIN page tp
                            ON (lp.page_title=tp.page_title)
                            JOIN categorylinks cl
                            ON (tp.page_id=cl.cl_from)
                            WHERE p.page_id IN ({idlist})
                            AND pl.pl_from_namespace=0
                            AND tp.page_namespace=1
                            AND cl.cl_to = %(imp_category)s
                            GROUP BY p.page_id'''

        ## connect to database
        if not self.db_connect():
            logging.error("Unable to connect to database")
            return()

        ## This maps page page ID to RatedPage objects
        id_page_map = {}

        ## for each importance category
        for imp_rating in self.imp_classes:
            logging.info('Grabbing {}-importance articles'.format(imp_rating))
            ## grab articles, create Article objects, populate with data
            category_name = '{imp}-importance_{project}_articles'.format(
                imp=imp_rating, project=project_name.lower())
            self.db_cursor.execute(art_query,
                                   {'imp_category': category_name})

            ## Not that many articles in these categories, so fetchall()
            ## should be okay
            for row in self.db_cursor.fetchall():
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

                page_data = RatedPage(talk_page_id,
                                      talk_revision_id,
                                      talk_page_title,
                                      talk_is_archive,
                                      imp_rating,
                                      art_page_id,
                                      art_revision_id,
                                      art_is_redirect)
                id_page_map[art_page_id] = page_data
                
        ## grab inlinks for all articles in this project, update
        ##      article data

        ## Note: We'll have to figure out something more clever here,
        ## as WPMED uses the category "All WikiProject Medicine articles",
        ## while for instance WP Biology uses "WikiProject Biology articles"

        logging.info("Getting inlink counts for {} articles".format(len(id_page_map)))
        
        category_name = "All_WikiProject_{project}_articles".format(project=project_name)

        ## Set up the list of page IDs for processing
        pageids = [str(p) for p in id_page_map.keys()]
        i = 0
        while i < len(pageids):
            subset = pageids[i:i+self.slice_size]
            logging.info('processing subset starting at {}'.format(i))
            logging.info('getting project-internal link counts')
            self.db_cursor.execute(projlink_query.format(
                idlist=','.join(subset)),
                {'imp_category': category_name})
            for row in self.db_cursor.fetchall():
                page_id = row['page_id']
                numlinks = row['num_inlinks']
                
                id_page_map[page_id].n_proj_inlinks = numlinks

            logging.info('getting global link counts')
            self.db_cursor.execute(inlink_query.format(
                idlist=','.join(subset)))
            for row in self.db_cursor.fetchall():
                page_id = row['page_id']
                numlinks = row['num_inlinks']
                
                id_page_map[page_id].n_inlinks = numlinks

            ## ok, advance
            i += self.slice_size

        ## disconnect from database
        self.db_disconnect()

        logging.info("Grabbing article views and writing out data")

        ## Set up our HTTP session so keep-alive works
        httpsession = requests.Session()

        ## spit it all out as a TSV
        with open(output_file, 'w+', encoding='utf-8') as outfile:
            outfile.write('talk_page_id\ttalk_revision_id\ttalk_page_title\ttalk_is_archive\tart_page_id\tart_revision_id\tart_is_redirect\timportance_rating\tn_proj_inlinks\tn_inlinks\tn_views\n')
            for (page_id, page_data) in id_page_map.items():
                page_data.n_views = round(self._get_views_from_api(
                    page_data.talk_page_title.replace('_', ' '),
                    http_session=httpsession))
                outfile.write('{0.talk_page_id}\t{0.talk_revision_id}\t{0.talk_page_title}\t{0.talk_is_archive}\t{0.page_id}\t{0.revision_id}\t{0.is_redirect}\t{0.importance_rating}\t{0.n_proj_inlinks}\t{0.n_inlinks}\t{0.n_views}\n'.format(page_data))

                ## give the pageview API a bit of breating room
                sleep(0.05)

        return()
        
    def _get_views_from_api(self, page_title, http_session=None):
        '''
        Make a request to the Wikipedia pageview API to retrieve page views
        for the past 91 days and calculate and set `_avg_views` accordingly.

        :param page_title: The title of the page we're grabbing views for
        :type page_title: str
        
        :param http_session: Session to use for HTTP requests
        :type http_session: requests.session

        This is from
        https://github.com/nettrom/suggestbot/blob/master/suggestbot/utilities/page.py
        '''
        # make a URL request to config.pageview_url with the following
        # information appendend:
        # languageCode + '.wikipedia/all-access/all-agents/' + uriEncodedArticle + '/daily/' +
        # startDate.format(config.timestampFormat) + '/' + endDate.format(config.timestampFormat)
        # Note that we're currently not filtering out spider and bot access,
        # we might consider doing that.

        # Note: Per the below URL, daily pageviews might be late, therefore
        # we operate on a 2-week basis starting a couple of days back. We have
        # no guarantee that the API has two weeks of data, though.
        # https://wikitech.wikimedia.org/wiki/Analytics/PageviewAPI#Updates_and_backfilling

        if not http_session:
            http_session = requests.Session()
        
        today = date.today()
        start_date = today - timedelta(days=92)
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
                    sleep(1)
                    continue # try again
                except KeyError:
                    logging.warning("Key 'items' not found in pageview API response")
                    sleep(1)
            else:
                logging.warning('Pageview API did not return HTTP status 200')
                logging.warning('page: {}'.format(page_title))
                sleep(1)

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
        description="Script to grab articles by importance for a given WikiProject"
    )

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    cli_parser.add_argument("project_name",
                            help="name of the WikiProject (e.g. 'Medicine')")
    
    cli_parser.add_argument("output_file",
                            help="path to the TSV output file")
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    grab = ProjectGrabber()
    grab.grab_project(args.project_name, args.output_file)
        
    return()

if __name__ == '__main__':
    main()
    
