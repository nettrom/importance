#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that processes the `importance_ratings` column in our dataset and
produces additional columns with various counts of the number of ratings
and such.

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

from collections import defaultdict

def count_ratings(input_filename, output_filename, id_col, rating_col):
    '''
    Process the given rating column in our dataset and produce a new
    dataset with statistics on the number of ratings and such.

    :param input_filename: path to the input TSV file
    :type input_filename: str

    :param output_filename: path to the output TSV file
    :type output_filename: str

    :param id_col: zero-based index of the column with unique ID information
                  (e.g. the page ID of the talk page with the ratings)
    :type id_col: int

    :param rating_col: zero-based index of the column with the ratings
    :type rating_col: int
    '''

    with open(input_filename, 'r', encoding='utf-8') as infile:
        with open(output_filename, 'w', encoding='utf-8') as outfile:
            ## Grab the header line and write out the ID column
            cols = infile.readline().rstrip('\n').split('\t')
            outfile.write('{}\tn_ratings\tn_top\tn_high\tn_mid\tn_low\tn_unknown\tn_na\n'.format(cols[id_col]))

            ## Process all the other lines and munge the ratings
            i = 0
            for line in infile:
                cols = line.rstrip('\n').split('\t')
                ratings = cols[rating_col].split(',')

                counts = defaultdict(int)
                for rating in ratings:
                    counts[rating] += 1

                counts['n_ratings'] = sum([counts[k] for k in ['top', 'high', 'mid', 'low', 'unknown', 'na']]
                counts['id'] = cols[id_col]
                
                outfile.write('{id}\t{n_ratings}\t{top}\t{high}\t{mid}\t{low}\t{unknown}\t{na}\n'.format(**counts))

                i += 1
                if i % 1000 == 0:
                    logging.info('processed {} lines'.format(i))

        # ok, done
        return()

def main():
    # Parse CLI options
    import argparse;

    cli_parser = argparse.ArgumentParser(
        description="Script to process ratings data and produce count statistics"
        )

    ## Path to the intput file
    cli_parser.add_argument('input_filename', type=str,
                            help="path to the input TSV file")
    
    ## Path to the output file
    cli_parser.add_argument('output_filename', type=str,
                            help="path to the output TSV file")

    ## unique ID column
    cli_parser.add_argument('id_column', type=int,
                            help="zero-based index of the column holding the unique ID (e.g. talk page ID) to be used in the output dataset")
    
    ## unique ID column
    cli_parser.add_argument('rating_column', type=int,
                            help="zero-based index of the column holding the ratings")
    
    cli_parser.add_argument("-v", "--verbose", action="store_true",
                            help="write informational output");

    args = cli_parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    count_ratings(args.input_filename, args.output_filename, args.id_column,
                  args.rating_column)
        
    return()

if __name__ == '__main__':
    main()

