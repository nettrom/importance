#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script to read in datasets for a WikiProject and run analysis of how
article quality and importance correlates.

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

import yaml
import logging

import pandas as pd
import numpy as np

IMP_RATINGS = ['Low', 'Mid', 'High', 'Top']
QUAL_RATINGS = ['Stub', 'Start', 'C', 'B', 'GA', 'FA']

def calc_qual_score(row):
    '''
    Calculate the quality completeness score for a given article.

    :param row: a row in the dataset
    :type row: `pandas.Series`
    '''
    return(0*row['prob_stub'] + 1*row['prob_start'] + 2*row['prob_c'] +
           3*row['prob_b'] + 4*row['prob_ga'] + 5*row['prob_fa'])

def calc_imp_score(row):
    '''
    Calculate the total importance score for a given article.

    :param row: a row in the dataset
    :type row: `pandas.Series`
    '''
    return(0*row['proba_Low'] + 1*row['proba_Mid'] +
           2*row['proba_High'] + 3*row['proba_Top'])

def make_wikitable(dataset, column_titles, row_titles,
                   column_column, row_column):
    '''
    Take the given set of column and row titles and build a wikitable
    confusion matrix based on the given dataset.

    :param dataset: The dataset we're building a confusion matrix from
    :type dataset: pandas.DataFrame

    :param column_titles: titles for the columns, which match categories
                          in the dataset
    :type column_titles: str

    :param row_titles: titles for the rows, which match categories in the dataset
    :type row_titles: str

    :param column_column: name of the column in the dataset that contains the
                          matching column title values
    :type column_column: str

    :param row_column: name of the column in the dataset that contains the
                       matching row title values
    :type row_column: str
    '''

    # header
    wikitable = '''{| class="wikitable sortable"
|-
| 
'''
    for col_title in column_titles:
        wikitable = "{}! {}\n".format(wikitable, col_title)

    # content
    for (i, row_title) in enumerate(row_titles):
        wikitable = "{}|-\n! {}\n".format(wikitable, row_title)
        for (j, col_title) in enumerate(column_titles):
            n = dataset.loc[(dataset[row_column] == row_title) &
                            (dataset[column_column] == col_title), :].shape[0]
            wikitable = "{}| style='text-align:right;' | {{{{formatnum:{n}}}}}\n".format(wikitable, n=n)

    # footer
    return(wikitable + "|}")

def quality_importance_analysis(config_file, write_wikitable=False):
    # read in the config file
    with open(config_file) as infile:
        config = yaml.load(infile)
    
    # read in the datasets and join them
    snapshot = pd.read_table(config['snapshot file'])
    disambiguations = pd.read_table(config['disambiguation file'])
    importance_predictions = pd.read_table(config['prediction dataset'])
    quality_predictions = pd.read_table(config['wp10 prediction dataset'])
    sidechain = pd.read_table(config['sidechain file'])

    logging.info('snapshot size before merging: {}'.format(
        len(snapshot['talk_page_id'])))
    
    df = pd.merge(pd.merge(snapshot,
                           importance_predictions, on='art_page_id',
                           how='left'),
                  quality_predictions, how='left',
                  left_on='art_revision_id', right_on='art_rev_id')

    logging.info('data size after merging: {}'.format(
        len(df['talk_page_id'])))
    
    ## take out articles where the article is a redirect, a disambiguation page,
    ## or the talk page is an archive
    df = df[df.art_is_redirect == 0]
    df = df[df.art_page_id.isin(disambiguations.page_id) == False]
    df = df[df.talk_is_archive == 0]

    ## if an article is sidechained, set its predicted rating to the sidechain
    ## rating
    logging.info('updating ratings of {} sidechained articles'.format(
        len(sidechain.page_id)))
    for row in sidechain.itertuples(index=False):
        ratings = set(row.ratings.split(','))
        if len(ratings) > 1:
            # pick the highest if we have multiple ratings
            rating = IMP_RATINGS[max([IMP_RATINGS.index(r) for r in ratings])]
        else:
            rating = ratings.pop()
            
        df.loc[(df.art_page_id == row.page_id), 'pred_rating_name'] = rating
        for imp_rating in IMP_RATINGS:
            col_name = 'proba_{}'.format(imp_rating)
            prob = 0.0
            if imp_rating == rating:
                prob = 1.0
            df.loc[(df.art_page_id == row.page_id), col_name] = prob

    # take out articles for which we do not have an importance prediction
    # nor a quality prediction
    df = df.loc[(df['pred_rating_name'].isin(IMP_RATINGS) == True) &
                (df['wp10_pred'].isin(QUAL_RATINGS) == True)]

    df.importance_rating = df.importance_rating.astype(
        'category', categories=IMP_RATINGS, ordered=True)
    df.pred_rating_name = df.pred_rating_name.astype(
        'category', categories=IMP_RATINGS, ordered=True)
    df.wp10_pred = df.wp10_pred.astype(
        'category', categories=QUAL_RATINGS, ordered=True)
    
    logging.info('data size after filtering: {}'.format(
        len(df['talk_page_id'])))
    
    # write out a confusion matrix of quality vs importance
    if write_wikitable:
        print('Confusion matrix for predicted quality vs current importance:')
        print(make_wikitable(df, IMP_RATINGS, QUAL_RATINGS,
                             'importance_rating', 'wp10_pred'))
        print('\nConfusion matrix for predicted quality vs predicted importance:')
        print(make_wikitable(df, IMP_RATINGS, QUAL_RATINGS,
                             'pred_rating_name', 'wp10_pred'))
    else:
        print('Confusion matrix for predicted quality vs current importance:')
        print(pd.crosstab(df.wp10_pred,
                          df.importance_rating,
                          colnames=['Importance'],
                          rownames=['Quality'],
                          margins=True))

        print('\nConfusion matrix for predicted quality vs predicted importance:')
        print(pd.crosstab(df.wp10_pred,
                          df.pred_rating_name,
                          colnames=['Importance'],
                          rownames=['Quality'],
                          margins=True))

    # calculate quality completion scores
    df['qual_comp'] = df.apply(calc_qual_score, axis=1, reduce=True)
    
    # calculate importance scores
    df['imp_comp'] = df.apply(calc_imp_score, axis=1, reduce=True)

    # calculate the correlation between these
    print('quality / importance correlation:')
    print(np.corrcoef(df.qual_comp, df.imp_comp))

    return()

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to analyse correlation between quality and importance in a WikiProject"
    )

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    cli_parser.add_argument('-w', '--wikitable', action='store_true',
                            help='print the confusion matrix as a wikitable')
    
    cli_parser.add_argument("config_file",
                            help="path to the WikiProject YAML configuration file")
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    quality_importance_analysis(args.config_file, args.wikitable)
        
    return()

if __name__ == '__main__':
    main()
