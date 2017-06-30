#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Library for identifying articles that require side-chaining in a prediction
model's workflow.

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

import sidechain
import wikiproject

## Maximum number of items in a batch
MAX_ITEMS = 50

def test_sidechain(lang, snapshot_file, ruleset_file, n_articles, rating=None):
    '''
    Load in the given snapshot and ruleset, grab n_articles (with a specific
    rating if defined), and test the sidechain.

    :param lang: language code of the Wikipedia we're testing for
    :type lang: str

    :param snapshot_file: path to the test WikiProject snapshot
    :type snapshot_file: str

    :param ruleset_file: path to the ruleset we are testing
    :type ruleset_file: str

    :param n_articles: number of articles to test with
    :type n_articles: int

    :param rating: only test on articles with a specific rating
    :type rating: str
    '''

    (project, rules) = sidechain.load(ruleset_file)
    print("Testing using rules from {}".format(project))

    articles = wikiproject.read_snapshot(snapshot_file)
    if rating:
        articles = [a for a in articles if a.importance_rating == rating]

    articles = [a.talk_page_title.replace("_", " ")
                for a in articles[:n_articles]]
    if len(articles) > MAX_ITEMS:
        side_chains = {}
        non_sidechains = []
        
        i = 0
        while i < len(articles):
            print("Processing subset [{}:{}]".format(i, i + MAX_ITEMS))
            subset = articles[i : i + MAX_ITEMS]

            result = sidechain.sidechain(lang, subset, rules)
            
            side_chains.update(result['sidechain'])
            non_sidechains.extend(result['non_sidechain'])
            
            i += MAX_ITEMS
    else:
        result = sidechain.sidechain(lang, articles, rules)
        side_chains = result['sidechain']
        non_sidechains = result['non_sidechain']
        
    print("Sidechained articles")
    print(side_chains)
    print("Non-sidechained articles")
    print(non_sidechains)

    return()

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to test the sidechain library"
    )

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    cli_parser.add_argument('-r', '--rating',
                            help='only test sidechaining for articles with a specific importance rating')

    cli_parser.add_argument('lang',
                            help='language code of the Wikipedia we are testing on')
        
    cli_parser.add_argument('snapshot_file',
                            help='path to the test WikiProject snapshot')

    cli_parser.add_argument('ruleset_file',
                            help='path to the test ruleset')

    cli_parser.add_argument('n_articles', type=int,
                            help='number of articles to test on')

    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    test_sidechain(args.lang, args.snapshot_file, args.ruleset_file,
                   args.n_articles, rating=args.rating)

    return()

if __name__ == '__main__':
    main()
