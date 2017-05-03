#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that processes a the snapshot and dataset from a WikiProject
to identify all related Wikidata items, then builds a network graph
based on relationships from those items. The graph is written out as
a GEXF file defined in the project's configuration.

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
import requests
import networkx as nx

from time import sleep
from collections import deque

import wikiproject as wp

class WDGraphBuilder:
    def __init__(self):
        self.graph = nx.DiGraph()

        # Number of items we process at a time
        self.slice_size = 50

        ## WD API base URL for the query we'd like to run
        self.wd_url = "https://www.wikidata.org/w/api.php?action=wbgetentities&format=json"
        
        ## HTTP headers
        self._headers = {
            'User-Agent': 'SuggestBot/1.0',
            'From:': 'morten@cs.umn.edu',
            }

        ## Max number of unlagged requests we make to WD API
        self.max_retries = 3

        ## Types of properties we use in the initial step out from
        ## the Wikidata items in the dataset. Extending this list
        ## might be necessary to better cover certain WikiProjects.
        self.allowed_claims = set([
            'P279', # subclass of
            'P31', # instance of
            'P361' # part of
            ])

        ## Types of properties we use for all other steps
        self.network_claims = set([
            'P279', # subclass of
            ])

    def make_api_request(self, items, http_session):
        '''
        Make an HTTP request to the Wikidata API for info on the given list
        of items using the given HTTP session.

        :param items: the QIDs of the items we'll be getting data about
        :type items: list

        :param http_session: the HTTP session we'll use
        :type http_session: requests.Session
        '''
        
        entity_data = {}

        done = False
        num_retries = 0
        while not done and num_retries < self.max_retries:
            ## We use a default of maxlag=5
            ## ref https://www.mediawiki.org/wiki/Manual:Maxlag_parameter
            item_url = "{base}{maxlag}&ids={idlist}".format(
                base=self.wd_url, maxlag="&maxlag=5",
                idlist="|".join(items))
            response = http_session.get(item_url)
            if response.status_code != 200:
                logging.warning('Wikidata returned status {}'.format(response.status_code))
                done = True
                continue

            try:
                content = response.json()
            except ValueError:
                logging.warning('Unable to decode Wikidata response as JSON')
                sleep(1)
                num_retries += 1
                continue
            except KeyError:
                logging.warning("Wikidata response keys not as expected")
                sleep(1)
                num_retries += 1
                continue

            if "error" in content and content['error']['code'] == 'maxlag':
                ## Pause before trying again
                ptime = max(5, int(response.headers['Retry-After']))
                logging.warning('WD API is lagged, waiting {} seconds to try again'.format(ptime))
                sleep(ptime)
                continue

            entity_data = content['entities']
            done = True
            continue

        return(entity_data)
        
    def build_graph(self, config_filename):
        '''
        Read in the WikiProject configuration file, then the associated
        snapshot and dataset. Use the defined Wikidata items to iteratively
        build the graph of connections between the articles.

        :param input_filename: path to the project's YAML configuration file
        :type input_filename: str
        '''

        with open(config_filename, 'r') as infile:
            proj_conf = yaml.load(infile)
        
        ## Read in the snapshot and build a map of page ID to object
        id_map = {p.page_id:p for p in
                  wp.read_snapshot(proj_conf['snapshot file'])
                  if p.page_id != "-1"}

        # read in the dataset
        with open(proj_conf['dataset'], 'r', encoding='utf-8') as infile:
            infile.readline() # skip header
            for line in infile:
                (page_id, wikidata_id, other) = line.strip().split('\t', 2)

                ## Some pages do not have an associated Wikidata item,
                ## print it out for reference
                if not wikidata_id:
                    continue
                
                try:
                    page = id_map[page_id]
                    self.graph.add_node(wikidata_id,
                                        title=page.talk_page_title,
                                        rating=page.importance_rating)
                except KeyError:
                    logging.warning('page ID {} not found in the snapshot'.format(page_id))

        # start the HTTP session
        wd_session = requests.Session()
                
        # get a list of all the nodes (which are now all our initial articles)
        items = self.graph.nodes()

        # things we've seen and processed (starting with our initial articles)
        seen_items = set(items)
        
        # create a queue of items to process
        queue = deque()
        
        # make a query to retrieve their claims from Wikidata
        # for each item in the query result:
        #   if the type of claim is "has part", ignore it
        #   
        #   if the destination of the claim is not seen:
        #     add the destination to the queue
        #     add the destination of the claim to the graph
        #
        #   Note: we must _always_ add the edge, otherwise we'll only have
        #         these edges for the first node that has this property.
        #   add an edge between the item and the destination

        ## Make a query to retrieve the claims for all initial items
        i = 0
        while i < len(items):
            logging.info('processing subset {}:{}'.format(i, i+self.slice_size))
            subset = items[i : i + self.slice_size]
            entity_data = self.make_api_request(subset, wd_session)
            sleep(0.01)
            ## Iterate over the entities
            ## The QID is in entity['id']
            for entity in entity_data.values():
                try:
                    qid = entity['id']
                except KeyError:
                    logging.warning('unable to get QID for {}'.format(entity['id']))
                    continue

                if not 'claims' in entity:
                    ## Item has no claims to help us
                    continue

                for (claim, cdata) in entity['claims'].items():
                    # ignore this claim? (see `self.allowed_claims`)
                    if not claim in self.allowed_claims:
                        continue

                    if isinstance(cdata, list):
                        for c in cdata:
                            try:
                                dest_id = c['mainsnak']['datavalue']['value']['id']
                            except KeyError:
                                # no valid destination for that claim
                                continue
                            except TypeError:
                                # 'value' is most likely not a dict
                                continue
                            
                            # Add the destination to the processing queue?
                            # Note that we'll label it when we process it.
                            if dest_id not in seen_items:
                                seen_items.add(dest_id)
                                queue.append(dest_id)
                                self.graph.add_node(dest_id)
                                
                            self.graph.add_edge(qid, dest_id, ptype=claim)

                    elif isinstance(cdata, dict):
                        try:
                            dest_id = cdata['mainsnak']['datavalue']['value']['id']
                        except KeyError:
                            # no valid destination for that claim
                            continue
                        
                        # Add the destination to the processing queue?
                        if dest_id not in seen_items:
                            seen_items.add(dest_id)
                            queue.append(dest_id)
                            self.graph.add_node(dest_id)
                            
                        self.graph.add_edge(qid, dest_id, ptype=claim)
                    
            i += self.slice_size

        # while the queue is not empty:
        while len(queue) > 0:
            logging.info('iterating... queue holds {} items'.format(len(queue)))
            
            # grab up to slice_size number of items from the queue
            items = []
            i = 0
            while len(queue) > 0 and i < self.slice_size:
                items.append(queue.popleft())
                i += 1
            
            # make a query to Wikidata to retrieve their claims
            entity_data = self.make_api_request(items, wd_session)

            ## Iterate over the entities
            ## The QID is in entity['id']
            for entity in entity_data.values():
                try:
                    qid = entity['id']
                except KeyError:
                    logging.warning('unable to get QID for {}'.format(entity['id']))
                    continue

                ## Grab the English label for this item, otherwise just
                ## use the QID
                try:
                    self.graph.add_node(qid, title=entity['labels']['en']['value'])
                except KeyError:
                    self.graph.add_node(qid, title=qid)
                
                if not 'claims' in entity:
                    ## Item has no claims to help us
                    continue

                for (claim, cdata) in entity['claims'].items():
                    ## We only concern ourselves with certain claims
                    if claim in self.network_claims:
                        if isinstance(cdata, list):
                            for c in cdata:
                                try:
                                    dest_id = c['mainsnak']['datavalue']['value']['id']
                                except KeyError:
                                    # no valid destination for that claim
                                    continue
                                except TypeError:
                                    # 'value' is most likely not a dict
                                    continue
                            
                                # Add the destination to the processing queue if
                                ## necessary. We'll label it when we process it.
                                if dest_id not in seen_items:
                                    seen_items.add(dest_id)
                                    queue.append(dest_id)
                                    self.graph.add_node(dest_id)
                                    
                                self.graph.add_edge(qid, dest_id, ptype=claim)
                        elif isinstance(cdata, dict):
                            try:
                                dest_id = cdata['mainsnak']['datavalue']['value']['id']
                            except KeyError:
                                # no valid destination for that claim
                                continue
        
                            if dest_id not in seen_items:
                                seen_items.add(dest_id)
                                queue.append(dest_id)
                                self.graph.add_node(dest_id)
                                
                            self.graph.add_edge(qid, dest_id, ptype=claim)

        # ok, the graph is built, write it out
        logging.info('build complete, writing out the graph')
        nx.write_gexf(self.graph, proj_conf['wikidata network'])

        # ok, done
        return()

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to build a Wikidata network based"
    )

    cli_parser.add_argument("config_filename", type=str,
                            help="path to the project's YAML configuration file")

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    builder = WDGraphBuilder()
    builder.build_graph(args.config_filename)

    return()

if __name__ == '__main__':
    main()


