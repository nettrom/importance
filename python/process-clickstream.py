#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that processes the clickstream dataset for extraction of information
about pages in a given other dataset.

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

class Article:
    def __init__(self, title):
        '''
        Create an ArticleClicks object for the article with the given title.
        '''
        self.title = title

        ## We want to calculate the proportion of views that come from
        ## other articles, and the proportion of inlinks that are actually
        ## used, so these are the associated variables.
        self.n_views = -1
        self.n_from_articles = -1
        self.n_active_inlinks = -1

        # set of titles of articles that are the source of a view of this article
        self.active_inlinks = set()

        ## Number of views from articles within the project
        ## and number of active inlinks from within the project.
        ## These are project-specific variants of the measures above.
        self.n_from_project_articles = -1
        self.n_project_active_inlinks = -1

        # set of titles of articles within the project that is the source
        # of a view of this article
        self.project_active_inlinks = set()

class ClickProcessor:
    def __init__(self):
        pass

    def process_clickstream(self, article_filename, clickstream_filename,
                            output_filename, title_col_idx, is_project=False):
        '''
        Process the clickstream, counting clicks for the articles defined
        in the given article dataset. Can also consider traffic from articles
        within a given WikiProject if options are set.

        :param article_filename: path to a TSV file with information on the
                                 articles that we are intersted in 
        :type article_filename: str

        :param clickstream_filename: path to the clickstream dataset
        :type clickstream_filename: str

        :param output_filename: path to the output file
        :type output_filename: str

        :param title_col_idx: zero-based index of the title column in the TSV
        :type title_col_idx: int

        :param is_project: are we processing a WikiProject?
        :type is_project: bool
        '''

        # Mapping titles (in clickstream format) to article objects
        title_map = dict()
        
        with open(article_filename, 'r', encoding='utf-8') as infile:
            infile.readline() # skip header
            for line in infile:
                cols = line.rstrip('\n').split('\t')

                # We store the dataset title in the object, then replace
                # any " " with "_" to match the clickstream dataset.
                art_obj = Article(cols[title_col_idx])
                click_title = cols[title_col_idx].replace(" ", "_")
                title_map[click_title] = art_obj

        logging.info('read in data on {} articles'.format(len(title_map)))
                
        # open the output file
        outfile = open(output_filename, 'w', encoding='utf-8')
        
        # Article title, total number of views, number of views from other
        # articles, number of other articles being sources of clicks,
        # number of views from articles within the WikiProject, and
        # number of other articles in the WikiProject being sources of clicks
        outfile.write('title\tn_views\tn_from_art\tn_act_links\tn_from_proj\tn_proj_act\n')

        # process the clickstream dataset
        i = 0
        with open(clickstream_filename, 'r', encoding='utf-8') as clickstream:
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
                art_obj.n_views += n
                
                if click_type == "link":
                    art_obj.n_from_articles += n
                    art_obj.active_inlinks.add(prev)
                    
                    # We're processing a WikiProject dataset and the source
                    # is an article in the project
                    if is_project and prev in title_map:
                        art_obj.n_from_project_articles += n
                        art_obj.project_active_inlinks.add(prev)

        ## ok, write out the results
        for art_obj in title_map.values():
            art_obj.n_active_inlinks = len(art_obj.active_inlinks)
            art_obj.n_project_active_inlinks = len(
                art_obj.project_active_inlinks)
            outfile.write('{0.title}\t{0.n_views}\t{0.n_from_articles}\t{0.n_active_inlinks}\t{0.n_from_project_articles}\t{0.n_project_active_inlinks}\n'.format(art_obj))
            
        ## ok, close the output file
        outfile.close()

        ## ok, done
        return()
    
def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to process clickstream data"
    )

    cli_parser.add_argument("input_filename", type=str,
                            help="path to the input TSV dataset")

    cli_parser.add_argument("clickstream_filename", type=str,
                            help="path to the clickstream dataset")
    
    cli_parser.add_argument("output_filename", type=str,
                            help="path to the output TSV extended dataset")

    cli_parser.add_argument("title_col_idx", type=int,
                            help="zero-based index of the article title column in the input TSV dataset")

    cli_parser.add_argument('-p', '--project', action='store_true',
                            help='set if process a WikiProject dataset, will then also add data on source articles within the project')

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    processor = ClickProcessor()
    processor.process_clickstream(args.input_filename, args.clickstream_filename,
                                  args.output_filename, args.title_col_idx,
                                  is_project=args.project)
    return()

if __name__ == '__main__':
    main()

