#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script to create a dataset of all articles in a Wikipedia edition,
in such a way that it mimics our WikiProject-specific datasets and
allows us to make importance predictions.

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

import bz2
import yaml
import logging

import db
import wikiproject as wp

class DatasetBuilder:
    def __init__(self, config_file):
        with open(config_file, 'r') as infile:
            self.config = yaml.load(infile)

    def get_articles(self, inlink_file, get_partial=True):
        '''
        Grab the view rate data from the database and the inlink count data
        from the given dataset and return the union of those two.

        :param inlink_file: path to the inlink count bz2 file
        :type inlink_file: str

        :param get_partial: Do we also consider articles for which we do not
                            have a full dataset of view rates?
        :type get_partial: bool
        '''

        # Query to get all articles from the page table
        get_article_query = '''SELECT page_id
                               FROM {table}'''

        get_title_query = '''SELECT page_id, page_title
                             FROM {page_table}
                             WHERE page_id IN ({id_list})'''

        article_set = set()

        db_conn =  db.connect(self.config['db_server'],
                              self.config['db_name'],
                              self.config['db_config_file'])
        if not db_conn:
            logging.error('cannot connect to database server')
            return(article_set)
        
        # read the inlink dataset
        inlink_set = set()
        with bz2.open(inlink_file, 'rt') as infile:
            infile.readline() # skip header

            for line in infile:
                (page_id, num_inlinks) = line.strip().split('\t')

                inlink_set.add(int(page_id))

        logging.info('found {} articles with inlink counts'.format(
            len(inlink_set)))

        # grab articles from the database
        viewrate_set = set()
        with db.cursor(db_conn, 'ssdict') as db_cursor:
            db_cursor.execute(get_article_query.format(
                table=self.config['page_table']))
            done = False
            while not done:
                row = db_cursor.fetchone()
                if not row:
                    done = True
                    continue

                viewrate_set.add(row['page_id'])

        logging.info('found {} articles with view data'.format(
            len(viewrate_set)))
                
        # intersect the two sets
        article_set = inlink_set & viewrate_set

        logging.info('intersection has {} articles'.format(len(article_set)))
        
        # if not get_partial:
        # grab "new" articles and remove them.
        partial_set = set()
        if not get_partial:
            with db.cursor(db_conn, 'dict') as db_cursor:
                db_cursor.execute(get_article_query.format(
                    table=self.config['newpage_table']))
                for row in db_cursor.fetchall():
                    partial_set.add(row['page_id'])

            article_set = article_set - partial_set

        # get the page titles for all the pages and turn the
        # set into a set of `wp.RatedPage` objects
        logging.info('getting article titles')
        i = 0
        article_list = list(article_set)
        articles = list()
        while i < len(article_list):
            with db.cursor(db_conn, 'dict') as db_cursor:
                logging.info('processing subset [{}:{}]'.format(
                    i, i + self.config['slice_size']))
                subset = article_list[i : i + self.config['slice_size']]

                db_cursor.execute(get_title_query.format(
                    page_table=self.config['page_table'],
                    id_list=','.join([str(a) for a in subset])))

                for row in db_cursor.fetchall():
                    page_id = row['page_id']
                    page_title = row['page_title'].decode('utf-8')
                    articles.append(wp.RatedPage(page_id, 0, page_title, 0,
                                                 'None', page_id, 0, 0))

            i += self.config['slice_size']
            
        db.disconnect(db_conn)
            
        return(articles)
            
    def write_snapshot(self, articles, snapshot_file):
        '''
        Build a dataset similar to that created by `snapshot-wikiproject.py`
        that can be fed to the `process-clickstream.py` for processing of the
        full clickstream dataset.

        :param articles: the articles to write out (iterable of `wp.RatedPage`)
        :type articles: iterable

        :param snapshot_file: path to write the output TSV snapshot file
        :type snapshot_file: str
        '''

        wp.write_snapshot(articles, snapshot_file)
        
        # ok, done
        return()
    
    def get_views_inlinks(self, articles, inlink_file,
                          view_link_file, newpage_view_file):
        '''
        Grab data from the MySQL database with article views, and from
        SuggestBot's dataset of number of inlinks. Write out to a TSV
        for further processing in R.

        :param articles: the articles (typically a `list` of `wp.RatedPage`,
                         must be an iterable of `wp.RatedPage` objects) we want
                         views and inlinks for
        :type articles: list

        :param inlink_file: path to the bz2 inlink count dump
        :type inlink_file: str

        :param view_link_file: path to the output TSV file with views and inlinks
        :type view_link_file: str

        :param newpage_view_file: path to the output TSV file with view data
                                  for "new" pages
        :type newpage_view_file: str
        '''

        ## Query to get views for all pages for which we have `k` days of data
        page_view_query = '''SELECT page_id, num_views
                             FROM {page_table} p
                             LEFT JOIN {newpage_table} n
                             USING (page_id)
                             WHERE n.page_id IS NULL
                             AND page_id IN ({id_list})'''

        ## Query to get views for all "new" pages, to be written out to
        ## a separate file for separate processing
        new_view_query = '''SELECT page_id, view_date, num_views
                            FROM {newpage_data_table}'''
        
        # mapping of page ID to RatedPage object
        id_page_map = {a.page_id:a for a in articles}
        
        db_conn =  db.connect(self.config['db_server'],
                              self.config['db_name'],
                              self.config['db_config_file'])
        if not db_conn:
            logging.error('cannot connect to database server')
            return(False)

        logging.info('getting inlink counts')
        with bz2.open(inlink_file, 'rt') as infile:
            infile.readline() # skip header

            for line in infile:
                (page_id, num_inlinks) = line.strip().split('\t')

                page_id = int(page_id)

                try:
                    id_page_map[page_id].num_inlinks = num_inlinks
                except KeyError:
                    continue

        logging.info('getting views for "old" pages')
        page_ids = list(id_page_map.keys())
        i = 0
        while i < len(page_ids):
            logging.info('processing subset [{}:{}]'.format(
                i, i + self.config['slice_size']))
            
            subset = page_ids[i : i + self.config['slice_size']]
            with db.cursor(db_conn, 'dict') as db_cursor:
                db_cursor.execute(page_view_query.format(
                    page_table=self.config['page_table'],
                    newpage_table=self.config['newpage_table'],
                    id_list=','.join([str(p) for p in subset])))
                for row in db_cursor.fetchall():
                    page_id = row['page_id']
                    num_views = row['num_views']

                    id_page_map[page_id].num_views = num_views

            i += self.config['slice_size']

        ## Get views for new pages, populate num_views with a list
        logging.info('getting views for "new" pages')
        with db.cursor(db_conn, 'dict') as db_cursor:
            db_cursor.execute(new_view_query.format(
                newpage_data_table=self.config['newpage_data_table']))
            for row in db_cursor.fetchall():
                page_id = row['page_id']
                view_date = row['view_date']
                num_views = row['num_views']

                try:
                    a = id_page_map[page_id]
                except KeyError:
                    continue

                if not hasattr(a, 'view_data'):
                    ## Add `view_data` as an attribute, this lets us
                    ## distinguish between articles for which we have `k`
                    ## days of view data, that allows us to get an avg view rate
                    a.view_data = [(view_date, num_views)]
                else:
                    ## Add another date/view tuple
                    a.view_data.append(
                        (view_date, num_views)
                    )

                    
        ## Write out num views and inlinks to the output file
        ## and views to a separate file for "new" pages
        outfile = open(view_link_file, 'w')
        outfile.write('page_id\twikidata_id\tnum_inlinks\tnum_proj_inlinks\tnum_views\n')

        new_outfile = open(newpage_view_file, 'w')
        new_outfile.write('page_id\tview_date\tnum_views\n')

        for a in articles:
            ## Is it a "new" page?
            if hasattr(a, 'view_data'):
                a.num_views = -1 ## Allows us to easily identify them
                for (view_date, num_views) in a.view_data:
                    new_outfile.write('{}\t{}\t{}\n'.format(a.page_id,
                                                            view_date,
                                                            num_views))
                    
            outfile.write('{0.page_id}\t{0.q}\t{0.num_inlinks}\t{0.num_proj_inlinks}\t{0.num_views}\n'.format(a))

        new_outfile.close()
        outfile.close()
        
        # ok, done
        return(True)

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to build a global snapshot and dataset of views and inlinks"
    )

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    cli_parser.add_argument("config_file",
                            help="path to the YAML configuration file for accessing view data")

    cli_parser.add_argument("inlink_count_file",
                            help="path to the inlink count bz2 dump")

    cli_parser.add_argument("snapshot_file",
                            help="path to the output snapshot TSV file")

    cli_parser.add_argument("view_link_file",
                            help="path to the output TSV file with number of views and inlinks")

    cli_parser.add_argument("newpage_view_file",
                            help="path to the output TSV file with data on views for new page")
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    builder = DatasetBuilder(args.config_file)
    articles = builder.get_articles(args.inlink_count_file)
    logging.info('found {} articles to build a global dataset on'.format(
        len(articles)))
    builder.write_snapshot(articles, args.snapshot_file)
    logging.info('snapshot written, getting views and inlinks')
    builder.get_views_inlinks(articles, args.inlink_count_file,
                              args.view_link_file, args.newpage_view_file)
    logging.info('all done')
        
    return()

if __name__ == '__main__':
    main()
