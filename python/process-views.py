#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that processes view data for a set of articles and generates
various forms of statistics.

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
from datetime import datetime, date, timedelta

import numpy as np
import scipy.stats as st

class ArticleData:
    def __init__(self, page_id, view_date, num_views):
        self.page_id = page_id

        ## dict mapping date to views
        self.views = {view_date: num_views}

class ViewProcessor:
    def __init__(self):
        pass

    def process_views(self, input_filename, output_filename,
                      end_date, num_days):
        '''
        Process a dataset of view data and output a new dataset with
        various summary statistics. Assumes that the input dataset has
        three tab-separated columns: page id, date, and number of views.

        :parameter input_filename: path to the input TSV file
        :type input_filename: str

        :parameter output_filename: path to the output TSV file
        :type output_filename: str

        :parameter end_date: expected last day of data in the dataset
                             (format: YYYYMMDD)
        :type end_date: str

        :parameter num_days: number of days of data in the dataset
        :type num_days: int
        '''

        ## parse the end date
        end_date_obj = datetime.strptime(end_date, '%Y%m%d').date()
        
        ## mapping page ID to page data
        articles = {}

        ## slurp in the data
        with open(input_filename, 'r', encoding='utf-8') as infile:
            infile.readline() # skip header
            for line in infile:
                (page_id, view_date, num_views) = line.strip().split('\t')
                view_date = datetime.strptime(view_date, '%Y-%m-%d').date()

                if page_id in articles:
                    articles[page_id].views[view_date] = int(num_views)
                else:
                    articles[page_id] = ArticleData(page_id,
                                                    view_date,
                                                    int(num_views))

        logging.info('slurped in data')

        # helpful single day delta
        one_day = timedelta(days=1)
        
        ## process the data
        ## first: go through everything and add zero views where missing
        for art_data in articles.values():
            sorted_views = [] # processing is easier with a sorted list
            cur_date = end_date_obj - timedelta(days=num_days -1)
            while cur_date <= end_date_obj:
                if not cur_date in art_data.views:
                    logging.info('found {} missing data, adding zero'.format(cur_date))
                    art_data.views[cur_date] = 0

                sorted_views.append(art_data.views[cur_date])
                cur_date += one_day


            # flip it around so the most recent data is first.
            sorted_views.reverse()
            art_data.sorted_views = sorted_views
                
        ## For each article, I want to know:
        ## avg views across the whole timespan
        ## avg views for first, second, and third set of 28 days
        ## avg views for each of the last four weeks
        for art_data in articles.values():
            logging.info('processing {}'.format(art_data.page_id))

            start_date = end_date_obj - timedelta(days=num_days -1)
            end_first_28 = start_date + timedelta(days=27)
            start_second_28 = start_date + timedelta(days=28)
            end_second_28 = start_second_28 + timedelta(days=27)
            start_third_28 = start_second_28 + timedelta(days=28)

            start_week_1 = end_date_obj - timedelta(days=27)
            end_week_1 = start_week_1 + timedelta(days=6)
            start_week_2 = end_date_obj - timedelta(days=20)
            end_week_2 = start_week_2 + timedelta(days=6)
            start_week_3 = end_date_obj - timedelta(days=13)
            end_week_3 = start_week_3 + timedelta(days=6)
            start_week_4 = end_date_obj - timedelta(days=6)
           
            first_28 = []
            cur_date = start_date
            while cur_date <= end_first_28:
                first_28.append(art_data.views[cur_date])
                cur_date += one_day

            logging.info('populated first_28 with {} values'.format(len(first_28)))
            
            second_28 = []
            cur_date = start_second_28
            while cur_date <= end_second_28:
                second_28.append(art_data.views[cur_date])
                cur_date += one_day

            logging.info('populated second_28 with {} values'.format(len(second_28)))
                
            third_28 = []
            cur_date = start_third_28
            while cur_date <= end_date_obj:
                third_28.append(art_data.views[cur_date])
                cur_date += one_day

            logging.info('populated third_28 with {} values'.format(len(third_28)))
            
            week_1 = []
            cur_date = start_week_1
            while cur_date <= end_week_1:
                week_1.append(art_data.views[cur_date])
                cur_date += one_day
            
            week_2 = []
            cur_date = start_week_2
            while cur_date <= end_week_2:
                week_2.append(art_data.views[cur_date])
                cur_date += one_day
            
            week_3 = []
            cur_date = start_week_3
            while cur_date <= end_week_3:
                week_3.append(art_data.views[cur_date])
                cur_date += one_day
            
            week_4 = []
            cur_date = start_week_4
            while cur_date <= end_date_obj:
                week_4.append(art_data.views[cur_date])
                cur_date += one_day

            art_data.tot_avg = np.mean(list(art_data.views.values()))
            art_data.tot_sdev = np.std(list(art_data.views.values()))
            
            art_data.first28_avg = np.mean(first_28)
            art_data.first28_sdev = np.std(first_28)
            
            art_data.second28_avg = np.mean(second_28)
            art_data.second28_sdev = np.std(second_28)
            
            art_data.third28_avg = np.mean(third_28)
            art_data.third28_sdev = np.std(third_28)
            
            art_data.week1_avg = np.mean(week_1)
            art_data.week1_sdev = np.std(week_1)
            
            art_data.week2_avg = np.mean(week_2)
            art_data.week2_sdev = np.std(week_2)
            
            art_data.week3_avg = np.mean(week_3)
            art_data.week3_sdev = np.std(week_3)
            
            art_data.week4_avg = np.mean(week_4)
            art_data.week4_sdev = np.std(week_4)

            ## New approach:
            ## Calculate a 99% confidence interval based on the second
            ## 28-day interval. Then use that to label each of the four
            ## weeks succeeding it.
            (low_bound, high_bound) = st.t.interval(0.99,
                                                    len(second_28)-1,
                                                    loc=np.mean(second_28),
                                                    scale=st.sem(second_28))
            art_data.week1_label = "0"
            if art_data.week1_avg < low_bound:
                art_data.week1_label = "-"
            elif art_data.week1_avg > high_bound:
                art_data.week1_label = "+"

            art_data.week2_label = "0"
            if art_data.week2_avg < low_bound:
                art_data.week2_label = "-"
            elif art_data.week2_avg > high_bound:
                art_data.week2_label = "+"

            art_data.week3_label = "0"
            if art_data.week3_avg < low_bound:
                art_data.week3_label = "-"
            elif art_data.week3_avg > high_bound:
                art_data.week3_label = "+"

            art_data.week4_label = "0"
            if art_data.week4_avg < low_bound:
                art_data.week4_label = "-"
            elif art_data.week4_avg > high_bound:
                art_data.week4_label = "+"

            ## Newer approach:
            ## Calculate the mean of the most recent week,
            ## then calculate the mean of the four & eight weeks preceeding.
            ## Calculate a 99% CI for the second mean and check if the first
            ## is outside of it. If it's positive, label it "+", negative
            ## label it "-", otherwise label it "0"
            ## I also want std.dev of the last week as a ratio of the mean
            ## of the four/eight weeks preceeding it, but I can just calculate
            ## that in R.
            sorted_views = art_data.sorted_views

            art_data.last_1_avg = np.mean(sorted_views[:7])
            art_data.last_1_sdev = np.std(sorted_views[:7])

            last_4 = sorted_views[7:35]
            art_data.last_4_avg = np.mean(last_4)
            art_data.last_4_sdev = np.std(last_4)
            (low_bound, high_bound) = st.t.interval(0.99,
                                                    len(last_4)-1,
                                                    loc=np.mean(last_4),
                                                    scale=st.sem(last_4))
            art_data.last_4_label = "0"
            if art_data.last_1_avg < low_bound:
                art_data.last_4_label = "-"
            elif art_data.last_1_avg > high_bound:
                art_data.last_4_label = "+"

            last_8 = sorted_views[7:63]
            art_data.last_8_avg = np.mean(last_8)
            art_data.last_8_sdev = np.std(last_8)
            (low_bound, high_bound) = st.t.interval(0.99,
                                                    len(last_8)-1,
                                                    loc=np.mean(last_8),
                                                    scale=st.sem(last_8))
            art_data.last_8_label = "0"
            if art_data.last_1_avg < low_bound:
                art_data.last_8_label = "-"
            elif art_data.last_1_avg > high_bound:
                art_data.last_8_label = "+"
                            
        ## write out new data
        with open(output_filename, 'w', encoding='utf-8') as outfile:
            outfile.write('page_id\ttot_avg\ttot_sdev\tfirst28_avg\tfirst28_sdev\tsecond28_avg\tsecond28_sdev\tthird28_avg\tthird28_sdev\tweek1_avg\tweek1_sdev\tweek1_label\tweek2_avg\tweek2_sdev\tweek2_label\tweek3_avg\tweek3_sdev\tweek3_label\tweek4_avg\tweek4_sdev\tweek4_label\tlast_1_avg\tlast_1_sdev\tlast_4_avg\tlast_4_sdev\tlast_4_label\tlast_8_avg\tlast_8_sdev\tlast_8_label\n') # write header
            for art_data in articles.values():
                outfile.write('{0.page_id}\t{0.tot_avg}\t{0.tot_sdev}\t{0.first28_avg}\t{0.first28_sdev}\t{0.second28_avg}\t{0.second28_sdev}\t{0.third28_avg}\t{0.third28_sdev}\t{0.week1_avg}\t{0.week1_sdev}\t{0.week1_label}\t{0.week2_avg}\t{0.week2_sdev}\t{0.week2_label}\t{0.week3_avg}\t{0.week3_sdev}\t{0.week3_label}\t{0.week4_avg}\t{0.week4_sdev}\t{0.week4_label}\t{0.last_1_avg}\t{0.last_1_sdev}\t{0.last_4_avg}\t{0.last_4_sdev}\t{0.last_4_label}\t{0.last_8_avg}\t{0.last_8_sdev}\t{0.last_8_label}\n'.format(art_data))

        # ok, done!
        return()

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to process view data"
    )

    cli_parser.add_argument("input_filename", type=str,
                            help="path to the input TSV dataset")
    
    cli_parser.add_argument("output_filename", type=str,
                            help="path to the output TSV extended dataset")

    cli_parser.add_argument("end_date", type=str,
                            help="last day we have view data for (format: YYYYMMDD)")

    cli_parser.add_argument("num_days", type=int,
                            help="number of days of view data we should have for each article")

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    processor = ViewProcessor()
    processor.process_views(args.input_filename, args.output_filename,
                            args.end_date, args.num_days)
    
    return()

if __name__ == '__main__':
    main()
