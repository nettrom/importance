#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that processes the clickstream dataset for information about pages
in a given WikiProject snapshot.

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

import wikiproject as wp

class ClickProcessor:
    def __init__(self):
        pass

    def process_clickstream(self, config_filename, clickstream_filename):
        '''
        Read in the configuration file and the snapshot dataset defined
        in it. Then stream the given clickstream dataset, counting clicks
        for the articles in the snapshot.

        :param config_filename: path to the YAML project configuration
        :type config_filename: str

        :param clickstream_filename: path to the clickstream dataset
        :type clickstream_filename: str
        '''

        with open(config_filename) as infile:
            proj_conf = yaml.load(infile)

        # Mapping titles (in clickstream format) to article objects
        title_map = {p.talk_page_title:p for p in
                     wp.read_snapshot(proj_conf['snapshot file'])
                     if p.page_id != "-1"}

        logging.info('read in snapshot with {} articles'.format(len(title_map)))
            
        # process the clickstream dataset
        i = 0
        with open(clickstream_filename, 'r', encoding='utf-8') as clickstream:
            clickstream.readline() # skip the header
            for line in clickstream:
                i += 1
                if i % 1000 == 0:
                    logging.info('processed {} lines of clickstream data'.format(i))
                
                (prev, curr, click_type, n) = line.strip().split('\t')

                # not in our dataset...
                if curr not in title_map:
                    continue

                n = int(n)
                art_obj = title_map[curr]
                art_obj.n_clicks += n
                
                if click_type == "link":
                    art_obj.n_from_articles += n
                    art_obj.active_inlinks.add(prev)
                    
                    # We're processing a WikiProject dataset and the source
                    # is an article in the project
                    if prev in title_map:
                        art_obj.n_from_project_articles += n
                        art_obj.project_active_inlinks.add(prev)

        # open the output file
        with open(proj_conf['clickstream file'], 'w',
                  encoding='utf-8') as outfile:
            # Article page ID, total number of views, number of views from other
            # articles, number of other articles being sources of clicks,
            # number of views from articles within the WikiProject, and
            # number of other articles in the WikiProject being sources of clicks
            outfile.write('page_id\tn_clicks\tn_from_art\tn_act_links\tn_from_proj\tn_proj_act\n')

            ## ok, write out the results
            for art_obj in title_map.values():
                art_obj.n_active_inlinks = len(art_obj.active_inlinks)
                art_obj.n_project_active_inlinks = len(
                    art_obj.project_active_inlinks)
                outfile.write('{0.page_id}\t{0.n_clicks}\t{0.n_from_articles}\t{0.n_active_inlinks}\t{0.n_from_project_articles}\t{0.n_project_active_inlinks}\n'.format(art_obj))
            
        ## ok, close the output file
        outfile.close()

        ## ok, done
        return()
    
def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to process clickstream data"
    )

    cli_parser.add_argument("config_filename", type=str,
                            help="path to the project YAML configuration file")

    cli_parser.add_argument("clickstream_filename", type=str,
                            help="path to the clickstream dataset")
    
    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    processor = ClickProcessor()
    processor.process_clickstream(args.config_filename,
                                  args.clickstream_filename)
    return()

if __name__ == '__main__':
    main()

