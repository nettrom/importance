#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that fixes None-values in the art_is_redirect column in our
importance dataset.

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

def fix_none(input_filename, output_filename, none_col,
             replacement):
    '''
    Open the input TSV file and change all None-values in
    the given column to 0.

    :param input_filename: path to the input TSV file
    :type input_filename: str

    :param output_filename: path to write the fixed TSV file
    :type output_filename: str

    :param none_col: zero-based index of the column with None-values
    :type none_col: int

    :param replacement: what value to replace "None" with
    :type replacement: str
    '''

    line_no = 1
    with open(output_filename, 'w', encoding='utf-8') as outfile:
        with open(input_filename, 'r', encoding='utf-8') as infile:
            outfile.write(infile.readline()) # write the header
            for line in infile:
                cols = line.rstrip('\n').split('\t')
                if cols[none_col] == 'None':
                    cols[none_col] = replacement

                outfile.write('\t'.join(cols))
                outfile.write('\n')

                line_no += 1
                if line_no % 1000 == 0:
                    logging.info('{} lines'.format(line_no))

    # ok, done
    return()


def main():
    # Parse CLI options
    import argparse;

    cli_parser = argparse.ArgumentParser(
        description="Script to fix None-values in columns in our dataset"
        )

    ## Path to the intput file
    cli_parser.add_argument('input_filename', type=str,
                            help="path to the input TSV file")
    
    ## Path to the output file
    cli_parser.add_argument('output_filename', type=str,
                            help="path to the output TSV file")

    cli_parser.add_argument("-v", "--verbose", action="store_true",
                            help="write informational output");

    cli_parser.add_argument("-c", "--column", type=int, default=6,
                            help="zero-based index of the column to modify (default: 6)")

    cli_parser.add_argument("-r", "--replacement", type=str, default='0',
                            help="value to replace the column with (default: '0')")

    args = cli_parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)

        
    fix_none(args.input_filename, args.output_filename,
             args.column, args.replacement)
        
    return()

if __name__ == '__main__':
    main()
