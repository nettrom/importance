#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script to predict articles for an entire WikiProject using its trained
model and the entire snapshot dataset.

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
from sklearn.metrics import confusion_matrix

class WikiProjectPredictor:
    def __init__(self):
        self.config = None
        self.model = None
        self.le = None

    def load_datasets(self):
        '''
        Read in the datasets for this WikiProject, join them into a combined
        dataset and add the necessary columns.
        '''

        # read in snapshot
        snapshot = pd.read_table(self.config['snapshot file'])
        # read in dataset
        dataset = pd.read_table(self.config['dataset'])
        # read in clickstream
        clickstream = pd.read_table(self.config['clickstream file'])
        # read in disambiguations
        disambiguations = pd.read_table(self.config['disambiguation file'])
        # read in the list of side-chained articles
        sidechained = pd.read_table(self.config['sidechain file'])
        
        # Log-transform number of inlinks, views, and calculate prop_proj_inlinks
        dataset['log_inlinks'] = np.log10(1 + dataset['num_inlinks'])
        dataset['log_views'] = np.log10(1 + dataset['num_views'])
        dataset['prop_proj_inlinks'] = 1 + dataset['num_proj_inlinks']/(1 + dataset['num_inlinks'])

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

        # filter out all side-chained articles
        if not sidechained.empty:
            res = res[res.art_page_id.isin(sidechained.page_id) == False]
        
        # calculate proportion of active inlinks
        res['prop_act_inlinks'] = np.minimum(
            1.0, res['n_act_links']/(1 + res['num_inlinks']))

        # add rank variables for views and inlinks, and make them percentiles
        res['rank_links'] = res.num_inlinks.rank(method='min')
        res['rank_links_perc'] = res.num_inlinks.rank(method='min', pct=True)
        res['rank_views'] = res.num_views.rank(method='min')
        res['rank_views_perc'] = res.num_views.rank(method='min', pct=True)

        # make sure importance ratings are an ordered categorical variable
        res['importance_rating'] = res.importance_rating.astype(
            'category', categories=['Low', 'Mid', 'High', 'Top'], ordered=True)

        self.dataset = res

        return()

    def predict_ratings(self):
        '''
        Trim the given dataset down to the right columns, make predictions
        of the importance rating, and also probabilities for each rating.

        :param dataset: the dataset to make predictions on
        :type dataset: `pandas.DataFrame`
        '''
        
        X = self.dataset.loc[:, self.config['predictors']].as_matrix()

        logging.info('predicting importance ratings')
        classes = self.model.predict(X)
        logging.info('predicting rating probabilities')
        probabilities = self.model.predict_proba(X)

        self.dataset['pred_rating'] = pd.Series(classes,
                                                index=self.dataset.index)
        for i in range(probabilities.shape[1]):
            col_name = 'proba_{}'.format(self.le.inverse_transform(i))
            self.dataset[col_name] = probabilities[:,i]
        
        ## Return the dataset with predictions and probabilities added
        return()
    
    def make_confusion_matrix(self, config_file, print_wikitable=False):
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
        self.load_datasets()

        # make predictions for all pages and print out a confusion matrix
        logging.info('making predictions')
        self.predict_ratings()

        ## Add a column with the name of the predicted rating
        self.dataset['pred_rating_name'] = self.le.inverse_transform(
            self.dataset['pred_rating'])

        ratings = ['Top', 'High', 'Mid', 'Low'] # ratings in descending order

        if print_wikitable:
            conf_matrix = confusion_matrix(self.dataset['importance_rating'],
                                           self.dataset['pred_rating_name'],
                                           labels=ratings)
            # print header
            wikitable = '''{| class="wikitable sortable"
|-
| 
'''
            for rating in ratings:
                wikitable = "{}! {}\n".format(wikitable, rating)

            # print content
            for (i, rating) in enumerate(ratings):
                wikitable = "{}|-\n| {}\n".format(wikitable, rating)
                for (j, rating) in enumerate(ratings):
                    wikitable = "{}| style='text-align:right;' | {{{{formatnum:{n}}}}}\n".format(wikitable, n=conf_matrix[i, j])

            # print footer
            print(wikitable + "|}")
        else:
            print(pd.crosstab(self.dataset['importance_rating'],
                              self.dataset['pred_rating_name'],
                              rownames=['True'],
                              colnames=['Predicted'],
                              margins=True))
        return()

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to make predictions for all articles in a WikiProject")

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    cli_parser.add_argument('-w', '--wikitable', action='store_true',
                            help='print the confusion matrix as a wikitable')

    ## YAML configuration file for the global model
    cli_parser.add_argument('config_file',
                            help='path to the global model YAML configuration file')
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    predictor = WikiProjectPredictor()
    predictor.make_confusion_matrix(args.config_file, args.wikitable)
    
    return()

if __name__ == '__main__':
    main()


