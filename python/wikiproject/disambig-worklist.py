#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that uses a dataset of disambiguations as well as the Wikidata-based
network to identify disambiguation pages. The script prints to stdout a table
of all disambiguation pages with notes about whether they are found solely via
Wikidata, or through the enwiki category.

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

import networkx as nx

import wikiproject as wp

def print_disambiguations(config_file):
    '''
    Read in the WikiProject configuration file and necessary datasets,
    then identify disambiguation pages.

    :param config_file: path to the WikiProject YAML configuration file
    :type config_file: str
    '''

    with open(config_file, 'r') as infile:
        proj_conf = yaml.load(infile)

    all_pages = {p.page_id:p for p
                 in wp.read_snapshot(proj_conf['snapshot file'])
                 if p.page_id != "-1"}

    ## There are two sources of disambiguation pages
    ## 1: the disambiguation dataset, which uses the enwiki category:
    cat_disambigs = set()
    with open(proj_conf['disambiguation file'], 'r', encoding='utf-8') \
         as infile:
        infile.readline() # skip the header
        for line in infile:
            page_id, page_title = line.strip().split('\t')
            cat_disambigs.add(page_id)

    ## 2: the Wikidata graph, where disambiguation pages are instances
    ##    of Q4167410
    wd_disambigs = set()
    graph = nx.read_gexf(proj_conf['wikidata network'])
    try:
        disambig_preds = graph.predecessors('Q4167410')
        for pred in disambig_preds:
            etype = graph.get_edge_data(pred, 'Q4167410')
            if etype['ptype'] == 'P31': # instance of
                wd_disambigs.add(graph.node[pred]['title'])
    except KeyError:
        logging.warning('disambiguation (Q4167410) not found in graph')
    except nx.exception.NetworkXError:
        logging.warning('disambiguation (Q4167410) not found in graph')

    ## Intersect the Wikidata disambiguation pages with the snapshot dataset
    wd_disambigs = set([p.talk_page_title for p in all_pages.values()]) \
                   & wd_disambigs
    
    # Translate Wikidata page titles to page IDs
    title_map = {p.talk_page_title:p.page_id for p
                 in all_pages.values()}
    wd_disambig_ids = set()
    for wd_title in wd_disambigs:
        wd_disambig_ids.add(title_map[wd_title])

    ## We can now create three sets:
    ## 1: disambiguation pages found in both sets:
    both = cat_disambigs & wd_disambig_ids

    ## 2: disambiguation pages only found in the category
    only_cat = cat_disambigs - wd_disambig_ids

    ## 3: disambiguation pages only found through Wikidata
    only_wd = wd_disambig_ids - cat_disambigs

    ## Build a wikitable and print it out
    wikitable = '''{| class="wikitable sortable"
|-
! scope="col" style="width: 40%;" | Title (and talk)
! Rating
! Notes'''

    ## Add all that are in both sets
    for page_id in both:
        wikitable = '''{0}
|-
| [[{1}]] <small>([[Talk:{1}]])</small>
| {2}
|'''.format(wikitable, all_pages[page_id].talk_page_title.replace("_", " "),
            all_pages[page_id].importance_rating)

    ## Add those that are only in the category
    for page_id in only_cat:
        wikitable = '''{0}
|-
| [[{1}]] <small>([[Talk:{1}]])</small>
| {2}
| Found through [[:Category:All disambiguation pages]]'''.format(wikitable, all_pages[page_id].talk_page_title.replace("_", " "), all_pages[page_id].importance_rating)

    ## Add those that are only in Wikidata
    for page_id in only_wd:
        wikitable = '''{0}
|-
| [[{1}]] <small>([[Talk:{1}]])</small>
| {2}
| Labelled as a disambiguation page in Wikidata'''.format(wikitable, all_pages[page_id].talk_page_title.replace("_", " "), all_pages[page_id].importance_rating)

    print(wikitable + "\n|}")
    # ok, done
    return()
    
def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to print out a wikitable of disambiguation pages in a WikiProject that appear to be incorrectly rated"
    )

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    cli_parser.add_argument("config_file",
                            help="path to the YAML configuration file for the WikiProject")
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    print_disambiguations(args.config_file)
        
    return()

if __name__ == '__main__':
    main()
    

