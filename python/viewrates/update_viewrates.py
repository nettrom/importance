#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script to create or update viewrate data for all articles in English Wikipedia.

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

import sys
import logging
import datetime as dt

import db
import hive

from yaml import load
from tempfile import TemporaryDirectory

import MySQLdb

class MAWindow:
    '''
    A Moving Average (MA) window represented as start and end dates.
    Accepts start & end parameters as either `datetime.date` or
    `datetime.datetime` objects, and converts the latter case.

    :param start: oldest date in the window
    :type start: datetime.date

    :param end: most recent date in the window
    :type end: datetime.date
    '''
    def __init__(self, start, end):
        self.start = start
        self.end = end

        if isinstance(self.start, dt.datetime):
            self.start = self.start.date()

        if isinstance(self.end, dt.datetime):
            self.end = self.end.date()

class SnapshotError(Exception):
    '''
    Exception raised if we fail to create snapshots
    of the `page` and `redirect` tables
    '''
    pass

class SqoopError(Exception):
    '''
    Exception raised if import/export of data from MySQL
    to Hadoop using `sqoop` failed.
    '''
    pass
            
class Viewrates:
    def __init__(self, config_file):

        with open(config_file) as infile:
            self.config = load(infile)
        
        self.db_conn = None
        
    def make_snapshots(self):
        '''
        Create a snapshot of the `page` and 'redirect'tables from the given
        language Wikipedia so we can use them to compare and update our local
        `vr_page` table.
        '''

        page_snapshot_query = '''CREATE TABLE {page_snapshot_table}
                                 SELECT page_id, page_title
                                 FROM {lang}wiki.page
                                 WHERE page_namespace=0'''

        redirect_snapshot_query = '''CREATE TABLE {redirect_snapshot_table}
                                     SELECT rd_from, page_id AS rd_to
                                     FROM {lang}wiki.redirect
                                     JOIN {lang}wiki.page
                                     ON (rd_namespace=page_namespace
                                     AND rd_title=page_title)
                                     WHERE rd_namespace=0'''

        add_page_index_query = '''ALTER TABLE {page_snapshot_table}
                                  ADD INDEX (page_id)'''

        add_rdid_index_query = '''ALTER TABLE {redirect_snapshot_table}
                                  ADD INDEX rd_from_to (rd_from, rd_to)'''
        add_rdrev_index_query = '''ALTER TABLE {redirect_snapshot_table}
                                   ADD INDEX rd_to_from (rd_to, rd_from)'''

        try:
            with db.cursor(self.db_conn, 'dict') as db_cursor:
                db_cursor.execute(
                    page_snapshot_query.format_map(self.config))
                db_cursor.execute(
                    redirect_snapshot_query.format_map(self.config))
                db_cursor.execute(
                    add_page_index_query.format_map(self.config))
                db_cursor.execute(
                    add_rdid_index_query.format_map(self.config))
                db_cursor.execute(
                    add_rdrev_index_query.format_map(self.config))
            self.db_conn.commit()
        except:
            print("Unexpected error: {}".format(sys.exc_info()[0]))
            raise(SnapshotError)

        return()

    def delete_pages_and_redirects(self):
        '''
        Compare the page snapshot to the page table to find pages that
        no longer exists, and compare the redirect table to the page table
        to remove redirects that originate from outside the main namespace.
        '''

        ## Query to compare our list of pages against the snapshot
        ## to identify pages that should be deleted.
        find_query = '''SELECT p.page_id
                        FROM {page_table} p
                        LEFT JOIN {page_snapshot_table} ps
                        USING (page_id)
                        WHERE ps.page_id IS NULL'''

        ## Query to compare the redirect and page snapshots to identify
        ## redirects that originate outside the main namespace
        redirect_query = '''SELECT rd_from
                            FROM {redirect_snapshot_table}
                            LEFT JOIN {page_snapshot_table}
                            ON rd_from=page_id
                            WHERE page_id IS NULL'''

        ## Query to delete a page from a table
        delete_query = '''DELETE FROM {table}
                          WHERE {column} IN ({idlist})'''
        
        ## Query to get all page IDs from a table
        get_all_newpages_query = '''SELECT page_id
                                    FROM {newpage_table}'''
        
        pages_to_delete = list()
        with db.cursor(self.db_conn, 'dict') as db_cursor:
            db_cursor.execute(find_query.format_map(self.config))
            for row in db_cursor.fetchall():
                pages_to_delete.append(row['page_id'])

            if pages_to_delete:
                logging.info('deleting {} pages'.format(
                    len(pages_to_delete)))
                i = 0
                while i < len(pages_to_delete):
                    subset = pages_to_delete[i: i + self.config['slice_size']]
                    db_cursor.execute(delete_query.format(
                        table=self.config['page_table'],
                        column='page_id',
                        idlist=','.join([str(p) for p in subset])))

                    i += self.config['slice_size']

                # Identify any new pages that also have to be deleted
                pages_to_delete = set(pages_to_delete)
                newpages = set()
                db_cursor.execute(
                    get_all_newpages_query.format_map(self.config))
                for row in db_cursor.fetchall():
                    newpages.add(row['page_id'])

                # Delete the data for any new page that's deleted
                for new_page_id in (pages_to_delete & newpages):
                    self.delete_newpage(new_page_id)
                
            ## Identify redirects that don't originate from namespace 0
            ## and delete those.
            pages_to_delete = list()
            db_cursor.execute(redirect_query.format_map(self.config))
            for row in db_cursor.fetchall():
                pages_to_delete.append(row['rd_from'])

            i = 0
            while i < len(pages_to_delete):
                subset = pages_to_delete[i : i + self.config['slice_size']]
                db_cursor.execute(delete_query.format(
                    table=self.config['redirect_snapshot_table'],
                    column='rd_from',
                    idlist=','.join([str(p) for p in subset])))

                i += self.config['slice_size']

        # ok, done
        self.db_conn.commit()
        return()

    def add_pages(self):
        '''
        Compare our page table with the page snapshot to identify new
        pages that should be added.
        '''

        # Query to compare our list of pages against the snapshot
        # to identify pages that should be added. We left join with
        # redirects so we can prevent adding any of them.
        find_query = '''SELECT page_id
                        FROM {page_snapshot_table} s
                        LEFT JOIN {redirect_snapshot_table} r
                        ON (s.page_id=r.rd_from)
                        LEFT JOIN {page_table} p
                        USING (page_id)
                        WHERE r.rd_from IS NULL
                        AND p.page_id IS NULL'''

        ## Query to insert a set of pages into the page table
        insert_query = '''INSERT INTO {page_table} (page_id, page_title)
                          SELECT page_id, page_title
                          FROM {page_snapshot_table}
                          WHERE page_id IN ({idlist})'''
        
        pages_to_add = list()
        with db.cursor(self.db_conn, 'dict') as db_cursor:
            db_cursor.execute(find_query.format_map(self.config))

            for row in db_cursor.fetchall():
                pages_to_add.append(row['page_id'])

            logging.info('adding {} pages'.format(
                len(pages_to_add)))
                
            i = 0
            while i < len(pages_to_add):
                subset = pages_to_add[i : i + self.config['slice_size']]
                db_cursor.execute(insert_query.format(
                    page_table=self.config['page_table'],
                    page_snapshot_table=self.config['page_snapshot_table'],
                    idlist=','.join([str(p) for p in subset])))

                i += self.config['slice_size']

            self.db_conn.commit()

        ## Return the list of added pages because it will be used later
        return(pages_to_add)

    def update_titles(self):
        '''
        Update all page titles in our local page table to match the snapshot.
        This is run after adds and deletes, at which point the two tables
        should match each other so a straight JOIN works.
        '''

        update_title_query = '''UPDATE {page_table} p
                                JOIN {page_snapshot_table} s
                                USING (page_id)
                                SET p.page_title=s.page_title'''

        with db.cursor(self.db_conn, 'dict') as db_cursor:
            db_cursor.execute(update_title_query.format_map(self.config))

            logging.info('updated titles of {} pages'.format(
                db_cursor.rowcount))
            self.db_conn.commit()
            
        return()
    
    def add_newpages(self, pages):
        '''
        Add all `pages` to the `newpage` table. Expects `pages` to be a list
        of tuples where the first element is the page ID and the second element
        is the first edit (as a `datetime.datetime` object)

        :param pages: page IDs and first edits of the new pages to add
        :type pages: list
        '''

        insert_query = '''INSERT INTO {newpage_table}
                          (page_id, first_edit) VALUES (%s, %s)'''
        
        with db.cursor(self.db_conn, 'dict') as db_cursor:
            i = 0
            while i < len(pages):
                subset = pages[i : i + self.config['slice_size']]
                db_cursor.executemany(insert_query.format(
                    newpage_table=self.config['newpage_table']),
                                      subset)

                i += self.config['slice_size']

            self.db_conn.commit()

        # ok, done
        return()
        
    def initialize_newpage(self, cutoff_time):
        '''
        The initial run is slightly different from an update because
        we need to get first edits for all pages and populate the
        `newpage` table accordingly.

        :param cutoff_time: articles have to be created before this time
                            to not be considered "new"
        :type cutoff_time: datetime.datetime
        '''

        allpages_query = '''SELECT page_id
                            FROM {page_table}'''

        ## Turn cutoff time into a datetime object at midnight on the given day.
        if isinstance(cutoff_time, dt.date):
            cutoff_time = dt.datetime.combine(cutoff_time, dt.time())

        logging.info('cutoff time is {}'.format(cutoff_time))
        
        # go through all pages, find their first edit, if it's
        # recent enough, add them to the newpage table
        with db.cursor(self.db_conn, 'dict') as db_cursor:
            all_pages = list()
            db_cursor.execute(allpages_query.format_map(self.config))
            done = False
            while not done:
                rows = db_cursor.fetchmany(self.config['slice_size'])
                if not rows:
                    done = True
                    continue

                for row in rows:
                    all_pages.append(row['page_id'])

            logging.info('checking {} pages for the first edit'.format(
                len(all_pages)))

            pages_to_add = list()
            for (page_id, first_edit) in self.find_first_edits(all_pages):
                if first_edit >= cutoff_time:
                    # Add it as a tuple we can pass to executemany()
                    pages_to_add.append(
                        (page_id, first_edit)
                    )

        ## Add all those pages
        self.add_newpages(pages_to_add)
        return()

    def find_first_edits(self, pages):
        '''
        Identify the first edits of all the given pages. Returns an unordered
        list of tuples of the form (page_id, first_edit), where the first edit
        has been converted to a datetime.datetime object.

        :param pages: list of page IDs of pages to find first edits for
        :type pages: list
        '''

        recent_edit_query = '''SELECT rev_page,
                               MIN(rev_timestamp) AS first_edit
                               FROM {lang}wiki.revision
                               WHERE rev_page IN ({idlist})
                               GROUP BY rev_page'''

        pages_with_edits = list()

        with db.cursor(self.db_conn, 'dict') as db_cursor:
            i = 0
            while i < len(pages):
                subset = pages[i : i + self.config['slice_size']]
                db_cursor.execute(recent_edit_query.format(
                    lang=self.config['lang'],
                    idlist=','.join([str(p) for p in subset])))
                for row in db_cursor.fetchall():
                    page_id = row['rev_page']
                    first_edit = dt.datetime.strptime(
                        row['first_edit'].decode('utf-8'), '%Y%m%d%H%M%S')
                    pages_with_edits.append(
                        (page_id, first_edit)
                        )
                i += self.config['slice_size']

        return(pages_with_edits)

    def create_export_tables(self, cutoff_time):
        '''
        Create the two tables that will be exported to Hadoop. One contains
        all "new" pages and the redirects that point to them, the other contains
        all "old" pages and the redirects that point to them.

        :param cutoff_time: a new article has to have been first edited
                            before this time to be exported (typically
                            before midnight the current day)
        :type cutoff_time: datetime.datetime
        '''

        ## Query to drop the temporary "old" and "new" page tables
        drop_tables_query = '''DROP TABLE IF EXISTS {temp_oldpage_table},
                                                    {temp_newpage_table}'''
        
        ## Query to create a table contain all "old" pages.
        create_oldpage_query = '''CREATE TABLE {temp_oldpage_table}
           (SELECT p.page_id, p.page_title
            FROM {page_table} p
            LEFT JOIN {newpage_table} n
            USING (page_id)
            WHERE n.page_id IS NULL)
        UNION ALL
           (SELECT p2.page_id, p2.page_title
            FROM {page_table} p1
            LEFT JOIN {newpage_table} n
            USING (page_id)
            LEFT JOIN {redirect_snapshot_table} r
            ON p1.page_id=r.rd_to
            LEFT JOIN {page_snapshot_table} p2
            ON r.rd_from=p2.page_id)'''

        ## Add the page_id index to the temp oldpage table
        add_oldpage_index_query = '''ALTER TABLE {temp_oldpage_table}
        ADD INDEX pageid_idx (page_id)'''

        ## Query to insert into the "old" page table all redirects that point
        ## to all the old pages
        insert_oldpage_query = '''
        INSERT INTO {temp_oldpage_table}
        SELECT p.page_id, p.page_title
        FROM {temp_oldpage_table} t
        JOIN {redirect_snapshot_table} r
        ON t.page_id=r.rd_to
        JOIN {page_table} p
        ON r.rd_from=p.page_id
        '''

        ## Query to create the "new" temp page table as the union of
        ## all new pages and the redirects that point to them.
        create_newpage_query = '''
        CREATE TABLE {temp_newpage_table}
           (SELECT p.page_id, p.page_title
            FROM {newpage_table} n
            JOIN {page_table} p
            USING (page_id)
            WHERE first_edit <= %(cutoff)s)
        UNION ALL
           (SELECT p.page_id, p.page_title
            FROM {newpage_table} n
            JOIN {redirect_snapshot_table} r
            ON n.page_id=r.rd_to
            JOIN {page_table} p
            ON r.rd_from=p.page_id
            WHERE first_edit <= %(cutoff)s)'''

        with db.cursor(self.db_conn, 'dict') as db_cursor:
            # Drop the tables if they exist
            db_cursor.execute(drop_tables_query.format_map(self.config))
            
            ## Create the export table for "old" pages
            db_cursor.execute(create_oldpage_query.format_map(self.config))
            db_cursor.execute(add_oldpage_index_query.format_map(self.config))
            db_cursor.execute(insert_oldpage_query.format_map(self.config))

            logging.info('created table for export of pages and added {} redirects'.format(db_cursor.rowcount))

            ## Create the export table for "new" pages
            db_cursor.execute(create_newpage_query.format_map(self.config),
                              {'cutoff': cutoff_time})

            logging.info('created table for export of new pages')

        self.db_conn.commit()
            
        return()
    
    def mysql_to_hadoop(self):
        '''
        Use the `sqoop` command line utility to export two tables from
        our MySQL database to Hadoop.
        '''
        
        ## SQL query used with `sqoop` to export the list of "old" pages
        ## and all redirects pointing to them, that was created earlier.
        oldpage_query = '''SELECT o.page_id, \
CAST(o.page_title AS CHAR(255) CHARSET utf8) AS page_title \
FROM {temp_oldpage_table} o
WHERE $CONDITIONS'''.format_map(self.config)

        ## SQL query used with `sqoop` to export the list of new pages
        ## Grabs all new pages that were created before midnight today
        ## minus `delay_days`
        newpage_query = '''SELECT n.page_id, \
CAST(n.page_title AS CHAR(255) CHARSET utf8) AS page_title \
FROM {temp_newpage_table} n
WHERE $CONDITIONS'''.format_map(self.config)
        
        # call the creation of the database and deletion of the target table
        if hive.exec_hql(self.config['create_hive_file']) is None:
            logging.error('unable to create/update Hive target tables')
            return()

        # create the temporary directory
        with TemporaryDirectory(prefix=self.config['tempdir_prefix']) \
             as temp_dir:
            logging.info('sqoop is using temporary directory {}'.format(temp_dir))
            # call the import
            # first, export vr_page - vr_newpage (aka `vr_oldpage`), which
            # are all the existing pages for which we'll normal just do
            # incremental updates
            sqoop = hive.sqoop_import_table(self.config['db_server'],
                                            self.config['db_name'],
                                            oldpage_query,
                                            self.config['hive_database'],
                                            self.config['hive_oldpage_table'],
                                            'page_id',
                                            self.config['db_username'],
                                            self.config['sqoop_password_file'],
                                            temp_dir)
            if sqoop is None:
                logging.error('sqoop import of oldpage table failed')
                raise(ScoopException)
            
            # second, export `vr_newpage` so we can get recent view data for
            # those
            sqoop = hive.sqoop_import_table(self.config['db_server'],
                                            self.config['db_name'],
                                            newpage_query,
                                            self.config['hive_database'],
                                            self.config['hive_newpage_table'],
                                            'page_id',
                                            self.config['db_username'],
                                            self.config['sqoop_password_file'],
                                            temp_dir)
            if sqoop is None:
                logging.error('sqoop import of newpage table failed')
                raise(ScoopException)

        # ok, done
        return()

    def get_newpage_views(self, sliding_window):
        '''
        Use Hive to get views for all pages in the `vr_newpage` table that
        we just uploaded into Hadoop, spanning the most recent side of our
        `sliding_window`

        :param sliding_window: the sliding window used to calculate the
                               moving average view rates
        :type sliding_window: dict
        '''

        newpage_query = '''CREATE TABLE \
{hive_database}.{newpage_data_table} AS \
SELECT a.page_id, year, month, day, sum(view_count) AS num_views \
FROM {hive_database}.{newpage_table} AS a \
JOIN wmf.pageview_hourly AS b \
ON (a.page_title=b.page_title) \
WHERE ({date_range}) \
AND project='{lang}.wikipedia' \
GROUP BY a.page_id, year, month, day'''
        
        # for all the new pages:
        # get views per day from the end day in the old side of the sliding
        # window to the end day in the new side of the sliding window
        # (this is the shift in the most recent side of the window)
        hive.exec_beeline(newpage_query.format(
            hive_database=self.config['hive_database'],
            newpage_data_table=self.config['hive_newpage_data_table'],
            newpage_table=self.config['hive_newpage_table'],
            date_range=hive.make_where_datespan(
                sliding_window['old'].end,
                sliding_window['new'].end),
            lang=self.config['lang']))

        # ok, done
        return()

    def get_oldpage_views(self, sliding_window):
        '''
        Use Hive to get views for all pages in the `vr_oldpage` table
        that we just uploaded into Hadoop. The query will either accumulate
        views for an entire period of `k` days (if we have never done this
        before), or accumulate views for the two ends of the sliding window
        to allow us to update our SQL tables.

        :param sliding_window: the sliding window used to calculate the
                               moving average view rates
        :type sliding_window: dict
        '''

        if not sliding_window['old'].start:
            ## We're initializing the data, get one aggregate set of views.
            oldpage_query = '''CREATE TABLE \
{hive_database}.{oldpage_data_table} AS \
SELECT a.page_id, SUM(view_count) AS old_views, 0 as new_views \
FROM {hive_database}.{oldpage_table} AS a \
JOIN wmf.pageview_hourly AS b \
ON (a.page_title=b.page_title) \
WHERE ({date_range}) \
AND project='{lang}.wikipedia' \
GROUP BY a.page_id'''.format(
    hive_database=self.config['hive_database'],
    oldpage_data_table=self.config['hive_oldpage_data_table'],
    oldpage_table=self.config['hive_oldpage_table'],
    date_range=hive.make_where_datespan(
        sliding_window['old'].end,
        sliding_window['new'].end),
    lang=self.config['lang'])
        else:
            ## Query to update both ends of the sliding window
            oldpage_query = '''
CREATE TABLE \
{hive_database}.{oldpage_data_table} AS \
SELECT a.page_id, SUM(b.view_count) AS old_views, SUM(c.view_count) AS new_views
FROM {hive_database}.{oldpage_table} AS a \
JOIN wmf.pageview_hourly AS b \
ON (a.page_title=b.page_title) \
JOIN wmf.pageview_hourly AS c \
ON (a.page_title=c.page_title) \
WHERE ({date_range_b}) \
AND ({date_range_c}) \
AND b.project='{lang}.wikipedia' \
AND c.project='{lang}.wikipedia' \
GROUP BY a.page_id'''.format(
    hive_database=self.config['hive_database'],
    oldpage_data_table=self.config['hive_oldpage_data_table'],
    oldpage_table=self.config['hive_oldpage_table'],
    date_range_b=hive.make_where_datespan(
        sliding_window['old'].start,
        sliding_window['new'].start, prefix='b.'),
    date_range_c=hive.make_where_datespan(
        sliding_window['old'].end,
        sliding_window['old'].start, prefix='c.'),
    lang=self.config['lang'])

        # Execute the Hive query
        hive.exec_beeline(oldpage_query)

        # ok, done
        return()

    def hadoop_to_mysql(self):
        '''
        Use `sqoop` to export the data tables from Hadoop back into MySQL.
        '''

        # Execute a SQL file to drop and recreate the target tables
        db.execute_sql(self.config['create_mysql_file'],
                       self.config['db_server'], self.config['db_name'],
                       self.config['db_config_file'])
        
        # Path to the table is `hive_path`/`database_name`.db/`table_name`
        sqoop = hive.sqoop_export_table(
            self.config['db_server'],
            self.config['db_name'],
            self.config['temp_oldpage_table'],
            '{path}/{database}.db/{table}'.format(
                path=self.config['hive_path'],
                database=self.config['hive_database'],
                table=self.config['hive_oldpage_data_table']),
            self.config['db_username'],
            self.config['sqoop_password_file'])

        if sqoop is None:
            logging.error('sqoop export of oldpage table failed')
            raise(ScoopException)
        
        sqoop = hive.sqoop_export_table(
            self.config['db_server'],
            self.config['db_name'],
            self.config['temp_newpage_table'],
            '{path}/{database}.db/{table}'.format(
                path=self.config['hive_path'],
                database=self.config['hive_database'],
                table=self.config['hive_newpage_data_table']),
            self.config['db_username'],
            self.config['sqoop_password_file'])

        if sqoop is None:
            logging.error('sqoop export of oldpage table failed')
            raise(ScoopException)

       # ok, done
        return()

    def update_stats(self, sliding_window):
        '''
        Update the data in our MySQL database. The sliding window is used
        to determine how we're updating  "old" pages.
        '''

        ## Query to add an index on the `page_id` column to a table
        add_index_query = '''ALTER TABLE {}
                             ADD INDEX pid_idx (page_id)'''
        
        ## Query used to update old pages if it's the first calculation.
        ## Two left joins because a page might have 0 direct views, but
        ## non-0 redirect views.
        oldpage_set_query = '''UPDATE {page_table} p
                               LEFT JOIN (SELECT page_id, old_views AS page_views
                                     FROM {page_table} p1
                                     JOIN {temp_oldpage_table} data1
                                     USING (page_id)) AS pviews
                               USING (page_id)
                               LEFT JOIN (SELECT rd_to AS page_id,
                                            SUM(old_views) AS redirect_views
                                     FROM {redirect_snapshot_table} r
                                     JOIN {temp_oldpage_table} data2
                                     ON r.rd_from=data2.page_id
                                     GROUP BY rd_to) AS rviews
                               USING (page_id)
                               SET p.num_views = (IFNULL(pviews.page_views, 0) +
                                            IFNULL(rviews.redirect_views, 0))'''

        ## Query used to update old pages on each side of the window,
        ## similar to the one above but updates the value instead of setting it.
        oldpage_update_query = '''
            UPDATE {page_table} p
            LEFT JOIN (SELECT page_id, old_views, new_views
                  FROM {page_table} p1
                  JOIN {temp_oldpage_table} data1
                  USING (page_id)) AS pviews
            USING (page_id)
            LEFT JOIN (SELECT rd_to AS page_id,
                              SUM(old_views) AS old_views,
                              SUM(new_views) AS new_views
                       FROM {redirect_snapshot_table} r
                       JOIN {temp_oldpage_table} data2
                       ON r.rd_from=data2.page_id
                       GROUP BY rd_to) AS rviews
            USING (page_id)
            SET p.num_views=p.num_views - IFNULL(pviews.old_views, 0) -
                            IFNULL(rviews.old_views, 0) +
                            IFNULL(pviews.new_views, 0 +
                            IFNULL(rviews.new_views, 0)'''
        
        ## Query used to insert data on new pages
        newpage_insert_query = '''INSERT INTO {newpage_data_table}
                                  SELECT page_id,
                                         STR_TO_DATE(CONCAT(view_year, '-',
                                         view_month, '-', view_day), '%Y-%m-%d')
                                         AS view_date,
                                         num_views
                                  FROM {data_table}'''.format(
                        newpage_data_table=self.config['newpage_data_table'],
                        data_table=self.config['temp_newpage_table'])

        ## Query to add up all direct and redirect views for new pages
        ## and insert them into the new page data table
        newpage_insert_query = '''INSERT INTO {newpage_data_table}
            SELECT page_id, STR_TO_DATE(CONCAT(view_year, '-', view_month, '-',
                            view_day), '%Y-%m-%d') AS view_date,
                            SUM(num_views) AS num_views
            FROM (
                  (SELECT n.page_id, view_year, view_month, view_day, num_views
                   FROM nettrom_vr_newpage n
                   JOIN nettrom_vr_temp_newpage t
                   USING (page_id))
                 UNION ALL
                  (SELECT n.page_id, view_year, view_month, view_day,
                          SUM(num_views) AS num_views
                   FROM nettrom_vr_newpage n
                   JOIN nettrom_vr_redirect_snapshot r
                   ON n.page_id=rd_to
                   JOIN nettrom_vr_temp_newpage t
                   ON rd_from=t.page_id
                   GROUP BY n.page_id, view_year, view_month, view_day)
                 ) AS views
             GROUP BY page_id, view_year, view_month, view_day'''

        with db.cursor(self.db_conn, 'dict') as db_cursor:
            # Execute SQL commands to add indexes to the two new tables.
            db_cursor.execute(add_index_query.format(
                self.config['temp_oldpage_table']))
            db_cursor.execute(add_index_query.format(
                self.config['temp_newpage_table']))

            ## Update the "old" page table, either one side if first run,
            ## or both sides of the sliding window if updating.
            if not sliding_window['old'].start:
                db_cursor.execute(oldpage_set_query.format_map(self.config))
            else:
                db_cursor.execute(oldpage_update_query.format_map(self.config))
            logging.info('set/updated {} rows in the "old" page table'.format(
                db_cursor.rowcount))

            ## Insert the data on new pages
            db_cursor.execute(newpage_insert_query.format_map(self.config))
            logging.info('inserted {} rows of new page data'.format(
                db_cursor.rowcount))

            ## Commit the data
            self.db_conn.commit()
            
        # ok, done
        return()

    def check_new_pages(self, sliding_window):
        '''
        Get data on all new pages, if they were created before
        the beginning of the sliding window, update the page table
        and delete them from the new page tables.

        :param sliding_window: the moving average sliding window
        :type sliding_window: dict
        '''

        ## Query to get the page IDs of all new pages created before
        ## the beginning of the sliding window
        get_pages_query = '''SELECT page_id
                             FROM {newpage_table}
                             WHERE first_edit < %(beginning)s'''
        
        ## Query to update data for a page in the page table based on the
        ## number of views for the appropriate days
        update_page_query = '''UPDATE {page_table}
                               SET num_views=(
                                   SELECT SUM(num_views) AS num_views
                                   FROM {newpage_data_table}
                                   WHERE page_id=%(page_id)s
                                   AND view_date BETWEEN %(beginning)s
                                                 AND %(end)s
                               ) WHERE page_id=%(page_id)s'''

        ## Midnight at the earliest date of the current side of the window
        beginning = dt.datetime.combine(sliding_window['old'].end, dt.time())
        
        ## Get all pages created earlier than the beginning of the window
        with db.cursor(self.db_conn, 'dict') as db_cursor:
            db_cursor.execute(get_pages_query.format_map(self.config),
                              {'beginning': beginning})

            ## For each page...
            for row in db_cursor.fetchall():
                page_id = row['page_id']

                ## Update the data in the page table
                db_cursor.execute(update_page_query.format_map(self.config),
                                  {'page_id': page_id,
                                   'beginning': sliding_window['old'].end,
                                   'end': sliding_window['new'].end})

                ## delete the data from both new page tables
                self.delete_newpage(page_id)

            self.db_conn.commit()
        ## ok, done
        return()

    def delete_newpage(self, page_id):
        '''
        Delete the given page from the "newpage" and "newpage_data" tables.

        :param page_id: page ID of the page we're deleting
        :type page_id: int
        '''

        ## Query to delete data about a page from the newpage data table
        delete_data_query = '''DELETE FROM {newpage_data}
                               WHERE page_id={page_id}'''

        ## Query to delete a page from the newpage table
        delete_newpage_query = '''DELETE FROM {newpage}
                                  WHERE page_id={page_id}'''

        with db.cursor(self.db_conn, 'dict') as db_cursor:
            db_cursor.execute(delete_data_query.format(
                newpage_data=self.config['newpage_data_table'],
                page_id=page_id))
            db_cursor.execute(delete_newpage_query.format(
                newpage=self.config['newpage_table'],
                page_id=page_id))

        return()

    def drop_temp_tables(self):
        '''
        Drop the four temporary tables we have:
        1: page snapshot table
        2: redirect snapshot table
        3: page views import table
        4: new page views import table
        '''

        ## Drop table query
        drop_query = "DROP TABLE IF EXISTS {}"

        with db.cursor(self.db_conn, 'dict') as db_cursor:
            db_cursor.execute(drop_query.format(
                self.config['page_snapshot_table']))
            db_cursor.execute(drop_query.format(
                self.config['redirect_snapshot_table']))
            db_cursor.execute(drop_query.format(
                self.config['temp_oldpage_table']))
            db_cursor.execute(drop_query.format(
                self.config['temp_newpage_table']))

        # ok, done
        return()

    
    def update(self):
        '''
        Update our view rate data using a current snapshot of the `page` table,
        processing data from whenever our last update was.
        '''

        ## Check and update status
        get_status_query = '''SELECT latest_update
                              FROM {status_table}'''

        update_status_query = '''UPDATE {status_table}
                                 SET latest_update=%(new_timestamp)s'''
        
        # connect to database server
        self.db_conn = db.connect(self.config['db_server'],
                                  self.config['db_name'],
                                  self.config['db_config_file'])

        ## Record the time we start updating, as that will be used both for
        ## calculating deltas and stored in the database upon completion
        update_timestamp = dt.datetime.now(dt.timezone.utc)
        
        # take a snapshot of non-redirecting articles
        logging.info('taking a snapshot of the page and redirect tables')
        try:
            self.make_snapshots()
        except SnapshotError:
            logging.error('failed to snapshot the page table, unable to continue')
            return()
        
        # Compare vr_page to page to identify pages that should be deleted,
        # and delete those pages.
        logging.info('finding pages to delete...')
        self.delete_pages_and_redirects()

        # compare vr_page to page to identify new pages
        logging.info('finding pages to add...')
        added_pages = self.add_pages()

        # figure out the timespan since the last update and calculate the
        # two sides of the sliding window
        last_update = None
        with db.cursor(self.db_conn, 'dict') as db_cursor:
            db_cursor.execute(get_status_query.format(
                status_table=self.config['status_table']))
            row = db_cursor.fetchone()
            last_update = row['latest_update']

        # If we never updated before, identify "new" pages
        if last_update is None:
            ## We fake the sliding window so we update our data across
            ## the past k days.
            sliding_window = {'old': MAWindow(
                None,
                update_timestamp - dt.timedelta(days=self.config['delay_days']
                                                     + self.config['k'] -1)),
                              'new': MAWindow(
                None,
                update_timestamp - dt.timedelta(self.config['delay_days']))}

            logging.info('never updated before, identifying new pages')
            self.initialize_newpage(sliding_window['old'].end)
        else:
            ## Update titles of the `page` table to match the snapshot
            self.update_titles()

            # Create the sliding windows that allows us to easily calculate
            # the time spans we are updating on either side.
            # The oldest side is from last_update - delay_days - k + 1 day
            # to today - delay_days - k + 1 day
            # We have to add a day because the date range is _inclusive_.
            sliding_window  = {'old': MAWindow(
                last_update - dt.timedelta(days=self.config['delay_days']
                                                + self.config['k'] -1),
                last_update - dt.timedelta(days=self.config['delay_days'])),
                               # The most recent side is from
                               # last_update - delay_days
                               # to today - delay_days
                               'new': MAWindow(
                update_timestamp - dt.timedelta(days=self.config['delay_days']
                                                     + self.config['k'] -1),
                update_timestamp - dt.timedelta(self.config['delay_days']))}
            
            # find the first edit of all the new pages, then add them
            logging.info('last update was {}, adding new pages')
            self.add_newpages(self.find_first_edits(added_pages))

        ## Added pages is no longer useful and can be GCed if necessary
        del(added_pages)
            
        ## Create the `page` and `newpage` tables that will be exported
        ## to Hadoop to be used for queries.
        logging.info('creating tables for export to Hadoop')
        self.create_export_tables(sliding_window['new'].end)

        ## The import/export process can take a while, so we disconnect
        ## the database connection now and reconnect aftewards.
        db.disconnect(self.db_conn)
            
        logging.info('exporting page data from MySQL to Hadoop')
        try:
            self.mysql_to_hadoop()
        except ScoopException as e:
            return()

        # Use `beeline` to calculate views at either end of our
        # view rate window for old pages
        logging.info('calculating views for old pages with Hive')
        self.get_oldpage_views(sliding_window)

        # Use `beeline` to calculate views at the most recent end
        # of our view rate window for new pages
        logging.info('calculating views for news pages with Hive')
        self.get_newpage_views(sliding_window)

        # export the data we just generated from Hadoop to MySQL
        logging.info('exporting data from Hadoop to MySQL')
        try:
            self.hadoop_to_mysql()
        except ScoopException as e:
            return()

        # grab the data we just generated and update our database
        logging.info('updating database based on new data')
        self.db_conn = db.connect(self.config['db_server'],
                                  self.config['db_name'],
                                  self.config['db_config_file'])
        self.update_stats(sliding_window)

        # identify all new pages for which we have all data, update their
        # values and delete their data from vr_newpage and vr_newpage_data
        logging.info('checking new pages for complete data')
        self.check_new_pages(sliding_window)

        ## Delete the four temporary tables we have been using
        self.drop_temp_tables()
        
        # update the last_update timestamp
        logging.info('updating last update timestamp')
        with db.cursor(self.db_conn, 'dict') as db_cursor:
            db_cursor.execute(update_status_query.format(
                status_table=self.config['status_table']),
                              {'new_timestamp': update_timestamp})

        logging.info('all done!')
        db.disconnect(self.db_conn)
        # ok, done
        return()

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to update our global view rate dataset"
    )

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    # YAML configuration file
    cli_parser.add_argument('config_file',
                            help='path to the YAML configuration file')
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    rates = Viewrates(args.config_file)
    rates.update()
        
    return()

if __name__ == '__main__':
    main()
