#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that processes WikiProject dataset and writes out information on all
articles that should be side-chained.

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

import sidechain
import wikiproject

def process_sidechain(config_file):
    '''
    Load in the given WikiProject configuration and its dataset,
    iterate through and write out a dataset of all articles that
    should be side-chained together with their ratings.

    :param config_file: path to the WikiProject YAML configuration file
    :type config_file: str
    '''

    with open(config_file) as infile:
        config = yaml.load(infile)
    
    (project, rules) = sidechain.load(config['ruleset file'])
    print("Testing using rules from the {} project".format(project))

    sidechained_articles = []
    
    # load in the dataset
    qid_pageid_map = {}
    with open(config['dataset']) as infile:
        infile.readline() # skip header
        for line in infile:
            (page_id, qid, num_links,
             num_proj_links, num_views) = line.strip().split('\t')
            if qid:
                qid_pageid_map[qid] = page_id

    qids = list(qid_pageid_map.keys())
    i = 0
    while i < len(qids):
        subset = qids[i:i + sidechain.MAX_ITEMS]
        sidechain_result = sidechain.sidechain_q(config['lang'],
                                                 subset,
                                                 rules)
        
        for (qid, ratings) in sidechain_result['sidechain'].items():
            sidechained_articles.append({'page_id': qid_pageid_map[qid],
                                         'ratings': ",".join(ratings)})


        logging.info('completed processing of subset [{}:{}], currently {} articles in the side chain'.format(i, i+sidechain.MAX_ITEMS, len(sidechained_articles)))
        i += sidechain.MAX_ITEMS

    with open(config['sidechain file'], 'w') as outfile:
        outfile.write('page_id\tratings\n')
        for article in sidechained_articles:
            outfile.write('{page_id}\t{ratings}\n'.format_map(article))
        
    return()

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to test the sidechain library"
    )

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    cli_parser.add_argument('config_file',
                            help='path to the WikiProject YAML configuration file')

    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    process_sidechain(args.config_file)

    return()

if __name__ == '__main__':
    main()
