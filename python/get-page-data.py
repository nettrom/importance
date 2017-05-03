#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that processes a snapshot of pages from a WikiProject and
gathers count of inlinks, both from across a Wikipedia edition as
well as from within the WikiProject, number of page views, and the
Wikidata item associated with each page.

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

import pywikibot
from pywikibot.data.api import Request

from yaml import load
from time import sleep
from datetime import date, timedelta

from mwviews.api import PageviewsClient

class DataGetter:
    def __init__(self):
        self.lang = 'en'
        self.db_conf = "~/replica.my.cnf"
        self.db_server = "enwiki.labsdb"
        self.db_name = "enwiki_p"

        self.slice_size = 50 # batch size for inlink count retrieval

        # number of days of pageviews our view rate is based on:
        self.num_view_days = 28

    def get_data(self, config_file):
        '''
        Read in the snapshot TSV defined in the configuration file,
        and gather data for the articles defined in it.

        :param config_file: path to the YAML configuration file
                            for this WikiProject
        :type config_file: str
        '''

        ## SQL query to get the number of inlinks for a set of pages,
        ## accounting for inlinks coming in through single redirects.
        inlink_query = '''SELECT page_id,
                                 links.numlinks 
                                 + IFNULL(redirlinks.numlinks, 0)
                                 - IFNULL(redirs.numredirs, 0) AS num_inlinks
                          FROM
                          (SELECT p.page_id AS page_id,
                                  count(*) AS numlinks
                           FROM page p
                           JOIN pagelinks pl
                           ON (p.page_namespace=pl.pl_namespace
                               AND p.page_title=pl.pl_title)
                           WHERE p.page_id IN ({idlist})
                           AND pl.pl_from_namespace=0
                           GROUP BY p.page_id
                          ) AS links
                          LEFT JOIN
                          (SELECT p1.page_id,
                                  count(*) AS numredirs
                           FROM page p1
                           JOIN redirect 
                           ON (p1.page_namespace=rd_namespace
                               AND page_title=rd_title)
                           JOIN page p2
                           ON rd_from=p2.page_id
                           WHERE p2.page_namespace=0
                           AND p1.page_id IN ({idlist})
                           GROUP BY page_id
                          ) AS redirs
                          USING (page_id)
                          LEFT JOIN
                          (SELECT p1.page_id,
                                  count(*) AS numlinks
                           FROM page p1
                           JOIN redirect 
                           ON (p1.page_namespace=rd_namespace
                               AND page_title=rd_title)
                           JOIN page p2
                           ON rd_from=p2.page_id
                           JOIN pagelinks pl
                           ON (p2.page_namespace=pl.pl_namespace
                               AND p2.page_title=pl.pl_title)
                           WHERE p2.page_namespace=0
                           AND pl.pl_from_namespace=0
                           AND p1.page_id IN ({idlist})
                           GROUP BY page_id
                          ) AS redirlinks
                          USING (page_id)'''

        ## Query to get the number of inlinks coming in from pages within
        ## a set of categories.
        projlink_query = '''
            SELECT page_id,
                   links.numlinks
                   + IFNULL(redirlinks.numlinks, 0) AS num_inlinks
                   FROM
                   (SELECT p.page_id AS page_id,
                           count(*) AS numlinks
                    FROM page p
                    JOIN pagelinks pl
                    ON (p.page_namespace=pl.pl_namespace
                        AND p.page_title=pl.pl_title)
                    JOIN page lp
                    ON (lp.page_id=pl.pl_from)
                    LEFT JOIN redirect
                    ON lp.page_id=rd_from
                    LEFT JOIN page tp
                    ON (lp.page_title=tp.page_title
                        AND 1=tp.page_namespace)
                    LEFT JOIN categorylinks cl
                    ON (tp.page_id=cl.cl_from)
                    WHERE p.page_id IN ({idlist})
                    AND rd_from IS NULL
                    AND pl.pl_from_namespace=0
                    AND cl.cl_to IN ({cat_list})
                    GROUP BY p.page_id
                   ) AS links
                   LEFT JOIN
                   (SELECT p1.page_id,
                           count(*) AS numlinks
                    FROM page p1
                    JOIN redirect 
                    ON (p1.page_namespace=rd_namespace
                        AND page_title=rd_title)
                    JOIN page p2
                    ON rd_from=p2.page_id
                    JOIN pagelinks pl
                    ON (p2.page_namespace=pl.pl_namespace
                        AND p2.page_title=pl.pl_title)
                    JOIN page tp
                    ON (p2.page_title=tp.page_title
                        AND 1=tp.page_namespace)
                    JOIN categorylinks cl
                    ON (tp.page_id=cl.cl_from)
                    WHERE p2.page_namespace=0
                    AND pl.pl_from_namespace=0
                    AND p1.page_id IN ({idlist})
                    AND cl.cl_to IN ({cat_list})
                    GROUP BY page_id
                   ) AS redirlinks
                   USING (page_id)'''

        # read in the configuration file
        with open(config_file, 'r') as infile:
            proj_conf = load(infile)
        
        # read in the snapshot
        # store pages in a map from page_id to PageData object
        all_pages = dict()
        
        with open(proj_conf['snapshot file'], 'r', encoding='utf-8') as infile:
            infile.readline() # skip header

            for line in infile:
                cols = line.strip().split('\t')

                ## If the page ID is -1, the talk page doesn't have
                ## a matching article, so skip those
                if cols[4] == '-1':
                    continue

                ## The importance rating is last, but needs to be the
                ## fifth element for the list to work as a single parameter,
                ## so we splice it in:
                cols = cols[:4] + cols[-1:] + cols[4:-1]

                page = wp.RatedPage(*cols)
                all_pages[page.page_id] = page

        logging.info('read in dataset of {} pages'.format(len(all_pages)))
                
        # open the database connection
        db_conn = db.connect(self.db_server, self.db_name, self.db_conf)
        if db_conn is None:
            logging.error("Unable to connect to database")
            return()

        # create the Pywikibot site object
        site = pywikibot.Site(self.lang)

        ## instantiate the PageviewsClient (note that it's going to
        ## parallelize to self.slice_size)
        page_client = PageviewsClient(
            "User:SuggestBot/1.0; email: morten@cs.umn.edu")
        
        # Prepare the list of categories for the project-specific query
        imp_cats = [cat_name.replace(" ", "_") for cat_name in
                    proj_conf['importance categories'].values()]
        for supp_cat in proj_conf['support categories']:
            imp_cats.append(supp_cat.replace(" ", "_"))

        ## Prepare the list of category parameters to be added to the
        ## project-specific query
        cat_params = ','.join(["%s" for i in imp_cats])

        ## Prepare the dates used for pageview requests. Note that the pageview
        ## API also returns data for the end date, so the start date is
        ## num_view_days -1, because it's an inclusive date range.
        today = date.today()
        end_date = today - timedelta(days=2)
        start_date = end_date - timedelta(days=self.num_view_days -1)
        
        # open the output file and write a header
        outfile = open(proj_conf['dataset'], 'w', encoding='utf-8')
        outfile.write('page_id\twikidata_id\tnum_inlinks\tnum_proj_inlinks\tnum_views\n')

        # Make a list of all the pages for subsetting
        all_pages_list = list(all_pages.values())
        
        i = 0
        while i < len(all_pages_list):
            logging.info('processing subset starting from {}'.format(i))
            subset = all_pages_list[i:i+self.slice_size]
            
            # get global inlinks
            with db.cursor(db_conn, 'dict') as db_cursor:
                db_cursor.execute(inlink_query.format(
                    idlist=",".join([p.page_id for p in subset])))
                for row in db_cursor.fetchall():
                    page_id = str(row['page_id'])
                    num_inlinks = row['num_inlinks']
                    all_pages[page_id].num_inlinks = num_inlinks
            
            ## Get project-specific inlinks. Note that we use format() for
            ## the page IDs (since they're all numbers) and the category
            ## parameters, but pass in the importance categories as a list
            ## so that the library can translate the strings into SQL for us.
            with db.cursor(db_conn, 'dict') as db_cursor:
                db_cursor.execute(projlink_query.format(
                    idlist=",".join([p.page_id for p in subset]),
                    cat_list=cat_params),
                                  ## We use the params twice, so send two
                                  imp_cats*2)
                for row in db_cursor.fetchall():
                    page_id = str(row['page_id'])
                    num_inlinks = row['num_inlinks']
                    all_pages[page_id].num_proj_inlinks = num_inlinks
            
            # make query to the Wikipedia API to get the Wikidata items
            wikidata = self.get_wikidata([p.page_id for p in subset])
            for page in wikidata:
                all_pages[page['page_id']].q = page['wikibase_item']
            
            ## Make a set of requests to the pageview API to get views.
            ## First, map titles to objects in our subset:
            title_map = {p.talk_page_title:p for p in subset}
            
            pageviews = page_client.article_views(
                '{}.wikipedia'.format(self.lang),
                [p.talk_page_title for p in subset],
                start=start_date, end=end_date)
            ## Pageviews are dictionaries with date as keys, and then
            ## article as key and number of views as the value.
            for a_date in pageviews.keys():
                for (article, views) in pageviews[a_date].items():
                    if views is not None:
                        title_map[article].num_views += views

            for page in subset:
                outfile.write('{0.page_id}\t{0.q}\t{0.num_inlinks}\t{0.num_proj_inlinks}\t{0.num_views}\n'.format(page))
                    
            # iterate
            i += self.slice_size
        
        # close the output file
        outfile.close()

        # close the database connection
        db_conn.close()

        # ok, done
        return()
        
    def get_wikidata(self, page_ids):
        '''
        Make a request to the Wikipedia API to retrieve the Wikidata items
        associated with the given page IDs. Note that query continuation
        is not done, so `page_ids` should not contain more than 50 items
        (500 if you're a bot).

        Returns a list of dicts for every page returned.

        :param page_ids: list of page IDs to get Wikidata items for
        :type page_ids: list of str
        '''

        pageid_set = set(page_ids)
        wd_pages = list()

        r = Request(pywikibot.Site(self.lang), action='query')
        r['prop'] = 'pageprops'
        r['ppprop'] = 'wikibase_item'
        r['pageids'] = '|'.join(page_ids)

        res = r.submit()
        pages = res['query']['pages']
        for pagedata in pages.values():
            if not str(pagedata['pageid']) in pageid_set:
                logging.warning('found {} in pages, but not in our dataset'.format(pagedata['pageid']))
                continue

            try:
                props = pagedata['pageprops']
            except KeyError:
                logging.warning('no page properties for {}'.format(pagedata['pageid']))
                continue
                
            if 'wikibase_item' in props:
                wd_pages.append(
                    {'page_id': str(pagedata['pageid']),
                     'wikibase_item': props['wikibase_item'].upper()}
                )
                
        return(wd_pages)
    
def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to process a snapshot for a WikiProject and grab inlink counts, page views, and Wikidata identifiers"
    )

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    cli_parser.add_argument("config_file",
                            help="path to the YAML configuration file for the WikiProject")
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    getter = DataGetter()
    getter.get_data(args.config_file)
        
    return()

if __name__ == '__main__':
    main()

