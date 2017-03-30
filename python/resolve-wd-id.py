#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that grabs a dataset of Wikidata identifiers and extends it
with the name of the identifier.

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

import requests
from time import sleep

class WikidataItem:
    def __init__(self, qid):
        self.qid = qid
        self.line = ""
        self.label = ""

class WDResolver:
    def __init__(self):
        ## How many items we process in a batch
        self.slice_size = 50

        ## WD API base URL for the query we'd like to run
        self.wd_url = "https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&ids="
        
        ## HTTP headers
        self._headers = {
            'User-Agent': 'SuggestBot/1.0',
            'From:': 'morten@cs.umn.edu',
            }

    def fetch_names(self, input_filename, output_filename, qid_col_idx):
        '''
        Read the given input TSV dataset, grab the QIDs in the given column,
        grab their English labels, and write out an extended TSV to the given
        output file.

        :param input_filename: path to the input TSV file
        :type input_filename: str

        :param output_filename: path to the output (extended) TSV file
        :type input_filename: str

        :param qid_col_idx: zero-based index of the QID column
        :type qid_col_idx: int
        '''

        ## Maps QID to item object
        all_items = {}
        header = ""

        with open(input_filename, 'r', encoding='utf-8') as infile:
            header = infile.readline().rstrip('\n')
            for line in infile:
                cols = line.rstrip('\n').split('\t')

                item = WikidataItem(cols[qid_col_idx])
                item.line = line.rstrip('\n')

                all_items[item.qid] = item

        # query Wikidata for the English label associated with these items
        wd_session = requests.Session()
        i = 0
        item_list = list(all_items.values())
        while i < len(item_list):
            subset = item_list[i : i + self.slice_size]
            item_url = "{base}{idlist}".format(
                base=self.wd_url, idlist="|".join([i.qid for i in subset]))
            response = wd_session.get(item_url)
            sleep(0.01)
            if response.status_code != 200:
                logging.warning('Wikidata returned status {}'.format(response.status_code))
                continue

            try:
                content = response.json()
                entity_data = content['entities']
            except ValueError:
                logging.warning('Unable to decode Wikidata response as JSON')
            except KeyError:
                logging.warning("Wikidata response keys not as expected")

            ## Iterate over the entities
            ## The QID is in entity['id']
            for entity in entity_data.values():
                try:
                    qid = entity['id']
                except KeyError:
                    logging.warning('unable to get QID for {}'.format(entity['id']))
                    continue

                item = all_items[qid]

                try:
                    label = entity['labels']['en']['value']
                except KeyError:
                    logging.warning('unable to get label for {}'.format(qid))

                item.label = label
                    
            i += self.slice_size

        with open(output_filename, 'w', encoding='utf-8') as outfile:
            outfile.write('{}\tlabel\n'.format(header))
            with open(input_filename, 'r', encoding='utf-8') as infile:
                infile.readline() # skip header
                for line in infile:
                    cols = line.rstrip('\n').split('\t')

                    qid = cols[qid_col_idx]
                    item = all_items[qid]
                    outfile.write('{}\t{}\n'.format(line.rstrip('\n'),
                                                    item.label))

        # ok, done
        return()
        
def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to get English labels for a dataset TSV with Wikidata identifiers"
    )

    cli_parser.add_argument("input_filename", type=str,
                            help="path to the input TSV dataset")

    cli_parser.add_argument("output_filename", type=str,
                            help="path to the output TSV extended dataset")

    cli_parser.add_argument("qid_col_idx", type=int,
                            help="zero-based index of the column holding the Wikidata QID values")
    
    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)
        

    resolver = WDResolver()
    resolver.fetch_names(args.input_filename, args.output_filename,
                         args.qid_col_idx)
    return()

if __name__ == '__main__':
    main()
