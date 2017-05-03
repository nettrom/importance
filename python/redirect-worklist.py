#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that processes a WikiProject snapshot and writes out a wikitable
with information on all project-tagged talk pages where the associated
main namespace page is a redirect.

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

def print_redirects(config_file):
    '''
    Read in the WikiProject configuration file and snapshot,
    identify redirects and print out a wikitable.

    :param config_file: path to the WikiProject YAML configuration file
    :type config_file: str
    '''
    
    with open(config_file, 'r') as infile:
        proj_conf = yaml.load(infile)

    all_pages = wp.read_snapshot(proj_conf['snapshot file'])

    ## Build a wikitable and print it out
    wikitable = '''{| class="wikitable sortable"
|-
! scope="col" style="width: 40%;" | Title (and talk)
! Rating
! Notes'''

    for page in all_pages:
        if page.is_redirect == "1":
            wikitable = '''{0}
|-
| [[{1}]] <small>([[Talk:{1}]])</small>
| {2}
| '''.format(wikitable, page.talk_page_title.replace("_", " "), page.importance_rating)

    print(wikitable + "\n|}")
    
    # ok, done
    return()

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to print out a wikitable of redirects in a WikiProject that appear to be incorrectly rated"
    )

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    cli_parser.add_argument("config_file",
                            help="path to the YAML configuration file for the WikiProject")
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    print_redirects(args.config_file)
        
    return()

if __name__ == '__main__':
    main()
    
