#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script to load a global dataset of articles and generate predictions.
Articles will be split into two groups depending on whether we have
all available view data or not. For articles that do not, we will calculate
the lower end of a confidence interval to use as a view estimate.

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

import re
import logging
import pickle

from yaml import load

import pandas as pd
import numpy as np
import scipy.stats as st

from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import GradientBoostingClassifier as gbm
from sklearn.externals.joblib import Parallel, delayed

class GlobalPredictor:
    def __init__(self):
        self.config = None
        self.model = None
        self.le = None

    def calc_views(self, pg):
        '''
        Calculate views for a "new" page based on the given group of page data.
        
        :param pg: group of page data (page_id, number of views, etc)
        :type pg: `pandas.GroupBy`
        '''

        ## Index the page group by date, then reindex it by our full
        ## date range to add NaN-rows, then turn all NaNs into 0.
        pg.set_index(pd.to_datetime(pg.view_date), inplace=True)
        pg = pg.reindex(self.date_range).fillna(0)

        ## From https://stackoverflow.com/questions/39352554/pandas-dataframe-delete-row-with-certain-value-until-that-value-changes
        ## Remove all rows until the first non-zero row is encountered.
        ## This works because at some point in the date range, the page was
        ## created and therefore _must_ have non-zero views at that point.
        pg = pg.loc[pg[(pg != 0).all(axis=1)].first_valid_index():]
        
        ## If we only have two data points, the average views is 0,
        ## otherwise, it's the lower end of the confidence interval.
        if len(pg.num_views) <= 2:
            return(0.0)
        else:
            return(st.t.interval(self.config['confidence interval']/100,
                                 len(pg.num_views)-1,
                                 loc=np.mean(pg.num_views),
                                 scale=st.sem(pg.num_views))[0])

    def load_datasets(self):
        '''
        Load in the datasets defined in the configuration file, split them
        into "new" and "old" pages. Make any necessary calculations. Return
        both datasets.
        
        :param config: the global model configuration
        :type config: dict
        '''
        
        # read in snapshot
        snapshot = pd.read_table(self.config['snapshot file'])
        # read in dataset
        dataset = pd.read_table(self.config['dataset'])
        # read in clickstream
        clickstream = pd.read_table(self.config['clickstream file'])
        # read in disambiguations
        disambiguations = pd.read_table(self.config['disambiguation file'])
        # read in the "new" page views
        newpage_views = pd.read_table(self.config['new page views'])

        logging.info('loaded all datasets, processing and merging')
        
        # Log-transform number of inlinks, views, and calculate prop_proj_inlinks
        dataset['log_inlinks'] = np.log10(1 + dataset['num_inlinks'])
        
        ## Because this is the global dataset, we don't have WikiProjects,
        ## so "prop_proj_inlinks" is always (1 + num_inlinks/(1 + num_inlinks))
        dataset['prop_proj_inlinks'] = 1 + (dataset['num_inlinks']/ \
                                            (1 + dataset['num_inlinks']))
        
        # Calculate the proportion of clicks from articles
        clickstream['prop_from_art'] = np.minimum(
            1.0, clickstream['n_from_art']/(1 + clickstream['n_clicks']))
        
        # Join the datasets
        # snapshot[dataset[clickstream]]
        res = pd.merge(snapshot,
                       pd.merge(dataset, clickstream,
                                on='page_id'),
                       left_on='art_page_id', right_on='page_id')
        
        # filter out pages where the talk page is an archive
        res = res[res.talk_is_archive == 0]
        
        # filter out pages where the article is a redirect
        res = res[res.art_is_redirect == 0]
        
        # filter out pages where there is no corresponding article
        res = res[res.art_page_id > 0]
        
        # filter out disambiguations
        res = res[res.art_page_id.isin(disambiguations.page_id) == False]

        # Split out the new pages, calculate views for them, then copy those
        # views back in.
        logging.info('processing new page views')

        ## We need to extend data for "new" pages so that all of them have
        ## data for all days after their first day in the dataset.
        self.date_range = pd.date_range(start=min(newpage_views.view_date),
                                        end=max(newpage_views.view_date))

        ## Calculate confidence intervals for all new page views. Set it to
        ## 0 of it's below 0.
        newpage_views = newpage_views.groupby('page_id').apply(self.calc_views)
        newpage_views = newpage_views.to_frame()
        newpage_views.columns = ['num_views']
        newpage_views.num_views = newpage_views.num_views.apply(
            lambda n: np.max(n, 0))

        ## Set all with negative views to NaN, create the index,
        ## update, then set all rows with NaN to 0 views.
        ## Consider: df.num_views[df.num_views < 0] = np.nan
        res.loc[('num_views' < 0), 'num_views'] = np.nan
        res.set_index('art_page_id', inplace=True)
        res.update(newpage_views, overwrite=True)
        res.loc[(pd.isnull(res.num_views) | ('num_views' < 0)), 'num_views'] = 0

        # calculate log views
        res['log_views'] = np.log10(1 + res['num_views'])
        
        # calculate proportion of active inlinks
        res['prop_act_inlinks'] = np.minimum(
            1.0, res['n_act_links']/(1 + res['num_inlinks']))
        
        # add rank variables for views and inlinks, and make them percentiles
        res['rank_links'] = res.num_inlinks.rank(method='min')
        res['rank_links_perc'] = res.num_inlinks.rank(method='min', pct=True)
        res['rank_views'] = res.num_views.rank(method='min')
        res['rank_views_perc'] = res.num_views.rank(method='min', pct=True)

        # ok, done
        return(res)

    def predict_ratings(self, dataset):
        '''
        Trim the given dataset down to the right columns, make predictions
        of the importance rating, and also probabilities for each rating.

        :param dataset: the dataset to make predictions on
        :type dataset: `pandas.DataFrame`
        '''
        
        X = dataset[self.config['predictors']].as_matrix()

        logging.info('predicting importance ratings')
        classes = self.model.predict(X)
        logging.info('predicting rating probabilities')
        probabilities = self.model.predict_proba(X)

        dataset['pred_rating'] = pd.Series(classes, index=dataset.index)
        for i in range(probabilities.shape[1]):
            col_name = 'proba_{}'.format(self.le.inverse_transform(i))
            dataset[col_name] = probabilities[:,i]
        
        ## Return the dataset with predictions and probabilities added
        return(dataset)
    
    def make_predictions(self, config_file):
        '''
        Load in the datasets and models defined in the given configuration file,
        then predict the importance of all articles in the datasets.
        '''

        logging.info('loading the configuration file')
        # load in the configuration
        with open(config_file) as infile:
            self.config = load(infile)
            
        logging.info('loading the model')
        # load in the model
        with open(self.config['model file'], 'rb') as infile:
            self.model = pickle.load(infile)

        logging.info('loading the label encoder')
        # load in the label encoder
        with open(self.config['label encoder file'], 'rb') as infile:
            self.le = pickle.load(infile)

        logging.info('reading in the datasets')
        # read in the datasets
        self.dataset = self.load_datasets()

        # make predictions for all the old pages and write out a dataset
        logging.info('making predictions')
        self.dataset = self.predict_ratings(self.dataset)

        # reset the index so the page id column exists before writing it out
        self.dataset.reset_index(inplace=True)
        self.dataset[self.config['prediction dataset columns']].to_csv(
            self.config['prediction dataset'], sep='\t', index=False,
            compression='bz2')

        return()

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to make predictions for all articles in a Wikipedia edition using the global model"
    )

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    ## YAML configuration file for the global model
    cli_parser.add_argument('config_file',
                            help='path to the global model YAML configuration file')
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    predictor = GlobalPredictor()
    predictor.make_predictions(args.config_file)
    
    return()

if __name__ == '__main__':
    main()
