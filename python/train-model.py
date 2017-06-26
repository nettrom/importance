#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script to read in a dataset of articles with importance ratings from a
WikiProject and train a Gradient Boost Model to predict article importance.

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
import pickle

import numpy as np
import pandas as pd

from random import choice
from operator import itemgetter

from yaml import load

from scipy import interp

from sklearn import preprocessing
from sklearn.metrics import auc, roc_curve, classification_report, f1_score
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.ensemble import GradientBoostingClassifier as gbm

from imblearn.over_sampling import SMOTE


class Dataset:
    def __init__(self, training_data, training_labels,
                 test_data, test_labels):
        self.training_data = training_data
        self.training_labels = training_labels
        self.test_data = test_data
        self.test_labels = test_labels

class ModelTrainer:
    def __init__(self, config_file):
        with open(config_file) as infile:
            self.config = load(infile)

        self.dataset = None
        self.model = None
        self.le = None

    def read_dataset(self):
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

    def fit_labels(self):
        '''
        Create a LabelEncoder that encodes the importance labels.
        '''
        
        self.le = preprocessing.LabelEncoder()
        self.le.fit(self.dataset[self.config['labels']])

        return()
        
    def train_model(self, dataset):
        '''
        Train a GBM on the given dataset using the configuration's parameters.

        :param dataset: the dataset we're training on
        :type dataset: Dataset
        '''

        self.model = gbm(**self.config['model parameters'])
        self.model.fit(dataset.training_data, dataset.training_labels)

        return()

    def test_model(self, dataset):
        '''
        Test the given model on the given dataset's test data.
        '''

        if not self.le:
            self.fit_labels()
        
        # test the model
        mean_accuracy = self.model.score(dataset.test_data, dataset.test_labels)
        print("Accuracy: {}".format(mean_accuracy))

        label_preds = self.model.predict(dataset.test_data)
        label_probs = self.model.predict_proba(dataset.test_data)

        # per-class ROC AUC
        print("\nPer-class ROC AUC:")
        for label in np.unique(dataset.test_labels):
            label_name = self.le.inverse_transform([label])[0]
            fpr, tpr, thresholds = roc_curve(
                dataset.test_labels,
                label_probs[:, label],
                pos_label=label)
            roc_auc = auc(fpr, tpr)
            print(" * {}: {:.2f}".format(label_name, roc_auc))

        # output useful statistics
        print("\nPer-class F1-scores:")
        for (label, f1) in enumerate(f1_score(
                dataset.test_labels, label_preds, average=None)):
            label_name = self.le.inverse_transform([label])[0]
            print(" * {}: {:.2f}".format(label_name, f1))
            
        print(classification_report(label_preds, dataset.test_labels))

        print("Feature importances:")
        for (f_name, f_imp) in sorted(zip(self.config['predictors'],
                                          self.model.feature_importances_),
                                      key=itemgetter(1),
                                      reverse=True):
            print(" * {}: {:.2f}".format(f_name, f_imp))
        
        return()

    def make_final(self):
        '''
        Sample the full dataset according to the final training size,
        using SMOTE if necessary.
        '''

        if not self.le:
            self.fit_labels()
        
        samples_by_rating = self.dataset.groupby(self.config['labels']).apply(
            lambda s: s.sample(self.config['final training size']))

        if self.config['SMOTE final']:
            # build a binary dataset of all the SMOTE-class labels from
            # the training data, and a random sample of the right size
            # from the dataset, with test-articles held out
            training_sclass = samples_by_rating[samples_by_rating[
                self.config['labels']] == self.config['SMOTE class']]
            dataset_sample = self.dataset[
                self.dataset[self.config['labels']] !=
                self.config['SMOTE class']]
            dataset_sample = dataset_sample.sample(
                self.config['final training size'] * self.config['SMOTE factor'])

            ## Set the label of the sample to a random label that isn't
            ## the SMOTE class
            random_label = choice([l for l in
                                   self.config['importance categories'].keys()
                                   if l != self.config['SMOTE class']])
            dataset_sample[self.config['labels']] = random_label

            synth_base = pd.concat([
                training_sclass,
                dataset_sample
            ], ignore_index=True)

            ## Keep only the relevant columns, split into X & Y, then resample
            X = synth_base[self.config['predictors']]
            Y = self.le.transform(synth_base[self.config['labels']])

            sm = SMOTE(kind='regular')
            X_resampled, Y_resampled = sm.fit_sample(X, Y)

            smote_class_idx = self.le.transform([self.config['SMOTE class']])[0]

            ## Keep the new training data
            data_training = X_resampled[Y_resampled == smote_class_idx]
            labels_training = Y_resampled[Y_resampled == smote_class_idx]

            ## Combine the new training data with random training data
            ## from the other classes

            ## give me everything that is not in the SMOTE class and
            ## that is not in the test set
            dataset_sample = self.dataset[
                self.dataset[self.config['labels']] != self.config['SMOTE class']
            ]

            data_training = pd.DataFrame(data_training)
            data_training.columns = X.columns
            
            ## Sample the same number of articles from each of those
            new_samples = [data_training]
            new_labels = [np.asarray(labels_training)]
            for imp_cat in dataset_sample[self.config['labels']].unique():
                if imp_cat == self.config['SMOTE class']:
                    continue
                
                cur_sample = dataset_sample[
                    dataset_sample[
                        self.config['labels']] == imp_cat].sample(
                            self.config['final training size'] *
                            self.config['SMOTE factor'])

                new_samples.append(cur_sample[self.config['predictors']])
                new_labels.append(self.le.transform(
                    cur_sample[self.config['labels']]))
            
            data_training = pd.concat(new_samples)
            labels_training = np.concatenate(new_labels)
        else:
            ## Keep only the relevant columns
            data_training = samples_by_rating[self.config['predictors']]
            labels_training = self.le.transform(
                samples_by_rating[self.config['labels']])

        # test set is the full dataset
        data_test = self.dataset[self.config['predictors']]
        labels_test = self.le.transform(self.dataset[self.config['labels']])
            
        return(Dataset(data_training, labels_training,
                       data_test, labels_test))
        
    def split_train_test(self):
        '''
        Split the trainer's loaded dataset into a training and test set
        according to the configuration.
        '''

        if not self.le:
            self.fit_labels()
        
        # split out the data in training/test sample
        # looks like the approach to use is to first sample across all
        # groups, then do the train/test split
        samples_by_rating = self.dataset.groupby(self.config['labels']).apply(
            lambda s: s.sample(self.config['test set size'] +
                               self.config['training set size']))
        
        ## Split the dataset into data and labels, then split it into train/test
        data = samples_by_rating.drop(self.config['labels'], axis=1)
        labels = samples_by_rating[self.config['labels']]

        splitter = StratifiedShuffleSplit(
            n_splits=1,
            test_size=self.config['test set size'] * len(self.config['importance categories'].keys()),
            random_state=self.config['model parameters']['random_state'])

        train_idx, test_idx = next(splitter.split(data, labels))
        data_training = data.iloc[train_idx]
        data_test = data.iloc[test_idx]
        labels_training = labels.iloc[train_idx]
        labels_test = labels.iloc[test_idx]

        ## if we're doing SMOTE, create a SMOTE-dataset using the data
        ## from the training set and random samples from the other classes
        if self.config['SMOTE evaluation']:
            # build a binary dataset of all the SMOTE-class labels from
            # the training data, and a random sample of the right size
            # from the dataset, with test-articles held out
            training_sclass = data_training[
                labels_training == self.config['SMOTE class']]
            training_sclass[self.config['labels']] = self.config['SMOTE class']
            dataset_sample = self.dataset[
                (self.dataset[self.config['labels']] != self.config['SMOTE class'])
                &
                (self.dataset.art_page_id.isin(data_test.art_page_id) == False)]
            dataset_sample = dataset_sample.sample(
                self.config['training set size'] * self.config['SMOTE factor'])

            dataset_sample[self.config['labels']] = dataset_sample.loc[dataset_sample.index[0], self.config['labels']]

            synth_base = pd.concat([
                training_sclass,
                dataset_sample
            ], ignore_index=True)

            ## Keep only the relevant columns, split into X & Y, then resample
            X = synth_base[self.config['predictors']]
            Y = self.le.transform(synth_base[self.config['labels']])

            sm = SMOTE(kind='regular')
            X_resampled, Y_resampled = sm.fit_sample(X, Y)

            smote_class_idx = self.le.transform([self.config['SMOTE class']])[0]

            ## Keep the new training data
            data_training = X_resampled[Y_resampled == smote_class_idx]
            labels_training = Y_resampled[Y_resampled == smote_class_idx]

            ## Combine the new training data with random training data
            ## from the other classes

            ## give me everything that is not in the SMOTE class and
            ## that is not in the test set
            dataset_sample = self.dataset[
                (self.dataset[self.config['labels']] != self.config['SMOTE class'])
                &
                (self.dataset.art_page_id.isin(data_test.art_page_id) == False)]

            data_training = pd.DataFrame(data_training)
            data_training.columns = X.columns
            
            ## Sample the same number of articles from each of those
            new_samples = [data_training]
            new_labels = [np.asarray(labels_training)]
            for imp_cat in dataset_sample[self.config['labels']].unique():
                if imp_cat == self.config['SMOTE class']:
                    continue
                
                cur_sample = dataset_sample[
                    dataset_sample[
                        self.config['labels']] == imp_cat].sample(
                            self.config['training set size'] *
                            self.config['SMOTE factor'])

                new_samples.append(cur_sample[self.config['predictors']])
                new_labels.append(self.le.transform(
                    cur_sample[self.config['labels']]))
            
            data_training = pd.concat(new_samples)
            labels_training = np.concatenate(new_labels)
        else:
            ## Keep only the relevant columns
            data_training = data_training[self.config['predictors']]
            labels_training = self.le.transform(labels_training)

        # Do the same for test data
        data_test = data_test[self.config['predictors']]
        labels_test = self.le.transform(labels_test)

        return(Dataset(data_training, labels_training,
                       data_test, labels_test))

    def save_model(self):
        '''
        Write the model out to the model file.
        '''

        with open(self.config['model file'], 'wb') as outfile:
            pickle.dump(self.model, outfile)

        return()
            
def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to train a Gradient Boost Model for a WikiProject"
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

    trainer = ModelTrainer(args.config_file)
    trainer.read_dataset()
    
    ## Make a training/test set and evaluate model performance
    split_dataset = trainer.split_train_test()
    trainer.train_model(split_dataset)
    trainer.test_model(split_dataset)

    ## Make a final dataset and train and save the model
    final_dataset = trainer.make_final()

    trainer.train_model(final_dataset)
    trainer.test_model(final_dataset)

    trainer.save_model()
    
    return()

if __name__ == '__main__':
    main()
