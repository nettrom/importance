#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script to read in the dataset from a WikiProject and grab ORES quality
predictions for the article revisions listed in the dataset.

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
import requests

from yaml import load
from time import sleep

import pandas as pd

ORES_URL = "https://ores.wikimedia.org/v3/scores/"
HTTP_USER_AGENT = 'SuggestBot/1.0'
HTTP_FROM = 'morten@cs.umn.edu'
MAX_URL_ATTEMPTS = 3

class WikiProjectQualityPredictor:
    def __init__(self):
        self.config = None

    def load_dataset(self):
        '''
        Read in the snapshot for this WikiProject.
        '''

        # read in snapshot
        self.dataset = pd.read_table(self.config['snapshot file'])

        return()

    def get_ores_predictions(self, revision_ids, step=50):
        '''
        Iterate through a list of revision IDs in groups of size `step`,
        and get article quality predictions for those revisions from ORES.

        :param revision_ids: List of revision IDs we are predicting for
        :type revision_ids: list 

        :param step: Number of revisions to get predictions for at a time,
                     maximum is 50.
        :type step: int
        '''

        # looks like the best way to do this is to first make one
        # API request to update the pages with the current revision ID,
        # then make one ORES request to get the predictions.
        
        if step > 50:
            step = 50

        langcode = '{lang}wiki'.format(lang=self.config['lang'])
        
        # example ORES URL predicting ratings for multiple revisions:
        # https://ores.wmflabs.org/v3/scores/enwiki?models=wp10&revids=703654757%7C714153013%7C713916222%7C691301429%7C704638887%7C619467163
        # sub "%7C" with "|"

        results = []
        
        i = 0
        while i < len(revision_ids):
            logging.info('processing subset [{}:{}]'.format(i, i+step))
            subset = [str(r) for r in revision_ids[i: i + step]]
            
            # rev id (str) -> predictions
            revid_score_map = {k:{} for k in subset}

            # make a request to score the revisions
            url = '{ores_url}{langcode}?models=wp10&revids={revids}'.format(
                ores_url=ORES_URL,
                langcode=langcode,
                revids='|'.join(subset))

            logging.debug('Requesting predictions for {n} pages from ORES'.format(n=len(revid_score_map)))

            num_attempts = 0
            while num_attempts < MAX_URL_ATTEMPTS:
                r = requests.get(url,
                                 headers={'User-Agent': HTTP_USER_AGENT,
                                          'From': HTTP_FROM})
                num_attempts += 1
                if r.status_code == 200:
                    try:
                        response = r.json()
                        revid_pred_map = response[langcode]['scores']
                        break
                    except ValueError:
                        logging.warning("Unable to decode ORES response as JSON")
                    except KeyError:
                        logging.warning("ORES response keys not as expected")

                # something didn't go right, let's wait and try again
                sleep(5)

            # iterate over returned predictions and update
            for revid, score_data in revid_pred_map.items():
                try:
                    revid_score_map[revid] = score_data['wp10']['score']
                except KeyError:
                    # skip this revid
                    continue
                
            for rev_id in subset:
                try:
                    score_data = revid_score_map[str(rev_id)]
                    score_data['revid'] = rev_id
                    results.append(score_data)
                except KeyError:
                    # no predictions for this revision
                    pass
                    
            i += step

        return(results)
    
    def predict_quality(self):
        '''
        Grab the article revision ID column from the dataset and get
        quality predictions and probabilities for all the revisions,
        in batches of 50 at a time since ORES supports that.
        '''

        qual_pres = self.get_ores_predictions(
            self.dataset.loc[:, 'art_revision_id'].tolist())

        ## Unpack the quality predictions by creating a data frame
        ## of revision IDs, predicted classes, and probability by class
        rev_ids = []
        pred_ratings = []
        pred_prob_fa = []
        pred_prob_ga = []
        pred_prob_b = []
        pred_prob_c = []
        pred_prob_start = []
        pred_prob_stub = []
        
        for pred_data in qual_pres:
            rev_ids.append(pred_data['revid'])
            try:
                pred_ratings.append(pred_data['prediction'])
                pred_prob_fa.append(pred_data['probability']['FA'])
                pred_prob_ga.append(pred_data['probability']['GA'])
                pred_prob_b.append(pred_data['probability']['B'])
                pred_prob_c.append(pred_data['probability']['C'])
                pred_prob_start.append(pred_data['probability']['Start'])
                pred_prob_stub.append(pred_data['probability']['Stub'])
            except KeyError:
                pred_ratings.append('')
                pred_prob_fa.append(0.0)
                pred_prob_ga.append(0.0)
                pred_prob_b.append(0.0)
                pred_prob_c.append(0.0)
                pred_prob_start.append(0.0)
                pred_prob_stub.append(0.0)
                
        self.results = pd.DataFrame({'art_rev_id': pd.Series(rev_ids),
                                     'wp10_pred': pd.Series(pred_ratings),
                                     'prob_fa': pd.Series(pred_prob_fa),
                                     'prob_ga': pd.Series(pred_prob_ga),
                                     'prob_b': pd.Series(pred_prob_b),
                                     'prob_c': pd.Series(pred_prob_c),
                                     'prob_start': pd.Series(pred_prob_start),
                                     'prob_stub': pd.Series(pred_prob_stub)})

        return()
    
    def make_predictions(self, config_file):
        '''
        Load in the datasets and models defined in the given configuration file,
        then predict the importance of all articles in the datasets.

        :param config_file: path to the WikiProject YAML configuration file
        :type config_file: str
        '''

        logging.info('loading the configuration')
        with open(config_file, 'r') as infile:
            self.config = load(infile)
        
        logging.info('reading in the dataset')
        # read in the datasets
        self.load_dataset()

        # make predictions for all pages and print out a confusion matrix
        logging.info('making predictions')
        self.predict_quality()

        ## Write out the dataset
        self.results.to_csv(self.config['wp10 prediction dataset'],
                            sep='\t', index=False)

        return()

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to make article quality predictions for all articles in a WikiProject")

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    ## YAML configuration file for the global model
    cli_parser.add_argument('config_file',
                            help='path to the global model YAML configuration file')
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    predictor = WikiProjectQualityPredictor()
    predictor.make_predictions(args.config_file)
    
    return()

if __name__ == '__main__':
    main()


