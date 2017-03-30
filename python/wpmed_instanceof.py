#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that grabs all "instance of" attributes for all articles associated
with a certain category containing talk pages.

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
import pywikibot
from pywikibot.data.api import Request

import requests
from time import sleep

class WikidataItem:
    def __init__(self, title):
        '''
        Instantiate an object of this class.

        :param title: title of the page associated with this item
        :type title: str
        '''
        self.title = title
        self.Q = "" # Wikidata item identifier
        self.instance_of = []

class InstanceGrabber:
    def __init__(self):
        self.lang = 'en' # Wikipedia edition with our category

        ## How many items we process in a batch
        self.slice_size = 50

        ## Base URL for getting an item from Wikidata
        ## self.wd_url = "https://www.wikidata.org/wiki/Special:EntityData/"

        ## Better, use the API
        self.wd_url = "https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&ids="
        
        ## HTTP headers
        self._headers = {
            'User-Agent': 'SuggestBot/1.0',
            'From:': 'morten@cs.umn.edu',
            }

    def get_instance_id(self, instance_data):
        '''
        Return the ID for the given instance.

        :param instance_data: dictionary of instance data from Wikidata
        :type instance_data: dict
        '''
        return(instance_data['mainsnak']['datavalue']['value']['id'])
        
    def get_instances(self, categoryname, output_filename, is_talk=True):
        '''
        Grab all pages in the given category and retrieve all the Wikidata
        "instance of" attributes assocaited with these pages.

        :param categoryname: Name of the category, with namespace
        :type categoryname: str

        :param output_filename: path to the output TSV file
        :type output_filename: str

        :param is_talk: does the category contain talk pages?
        :type is_talk: bool
        '''

        ## all the WikidataItem objects we create based on the category,
        ## mapping titles to objects because the API query returns titles
        all_items = {}
        
        # grab all members of the given category, limited to either Main
        # (if is_talk is False) or Talk (otherwise)
        site = pywikibot.Site(self.lang)
        cat = pywikibot.Category(site, categoryname)

        # store all the titles
        cat_namespaces = [0]
        if is_talk:
            cat_namespaces = [1]

        for cat_member in cat.articles(namespaces=cat_namespaces):
            item = WikidataItem(cat_member.title(withNamespace=False))
            all_items[item.title] = item
            
        # grab the wikibase_item pageprop for all these titles and store that
        i = 0
        item_list = list(all_items.values())
        while i < len(item_list):
            subset = item_list[i : i + self.slice_size]
            r = Request(site, action='query')
            r['prop'] = 'pageprops'
            r['ppprop'] = 'wikibase_item'
            r['titles'] = '|'.join([s.title for s in subset])
            r['redirects'] = "true" # automatically resolve redirects

            res = r.submit()
            redirects = {}
            if 'redirects' in res['query']:
                for redirect in res['query']['redirects']:
                    ## might as well delete this then
                    ## logging.warning('deleting redirect {}'.format(redirect['from']))
                    del(all_items[redirect['from']])
            
            pages = res['query']['pages']
            for pagedata in pages.values():
                if not pagedata['title'] in all_items:
                    ## Because we're resolving redirects, printing these out
                    ## makes no sense
                    # logging.warning('found {} in pages, but not in our dataset'.format(pagedata['title']))
                    continue

                item = all_items[pagedata['title']]
                try:
                    props = pagedata['pageprops']
                except KeyError:
                    logging.warning('no page properties for {}'.format(pagedata['title']))
                    item.Q = "None"
                    continue
                
                if 'wikibase_item' in props:
                    item.Q = props['wikibase_item'].upper() # uppercase that Q
                
            i += self.slice_size

        # query Wikidata for the instance of associated with these titles
        # and store that
        wd_session = requests.Session()
        i = 0
        item_list = list(all_items.values())
        while i < len(item_list):
            subset = item_list[i : i + self.slice_size]
            item_url = "{base}{idlist}".format(
                base=self.wd_url, idlist="|".join(
                    [i.Q for i in subset if i.Q != "None"]))
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
            ## article title is in entity['sitelinks']['enwiki']['title']
            for entity in entity_data.values():
                try:
                    title = entity['sitelinks']['enwiki']['title']
                except KeyError:
                    logging.warning('unable to get article title for {}'.format(entity['id']))
                    continue

                item = all_items[title]
                
                ## We're interested in a claim for property P31 ("instance of")
                ## Where we'll store the entity for that property.
                claims = entity['claims']
                if not 'P31' in claims:
                    logging.warning('{} is not an instance of anything'.format(item.title))
                    continue

                inst_data = claims['P31']
                ## P31 is either a list (multiple instances)
                ## or a dict (single instance)
                if isinstance(inst_data, list):
                    for inst_data_item in inst_data:
                        try:
                            item.instance_of.append(
                                self.get_instance_id(inst_data_item))
                        except KeyError:
                            logging.warning('unexpected data structure for P31 for {}'.format(item.title))
                else:
                    try:
                        item.instace_of.append(self.get_instance_id(inst_data))
                    except KeyError:
                        logging.warning('unexpected data structure for P31 for {}'.format(item.title))

            i += self.slice_size
            
        # write to the output file
        with open(output_filename, 'w', encoding='utf-8') as outfile:
            outfile.write('page_title\tQID\tinstance_of\n')
            for item in all_items.values():
                if not item.instance_of:
                    outfile.write('{}\t{}\tNone\n'.format(item.title, item.Q))
                else:
                    for inst_id in item.instance_of:
                        outfile.write('{}\t{}\t{}\n'.format(item.title,
                                                            item.Q,
                                                            inst_id))
        # ok, done
        return()

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to get Wikidata 'instance of' attributes for pages in a category"
    )

    cli_parser.add_argument("category", type=str,
                            help="name of the category (with namespace)")

    cli_parser.add_argument("output_filename", type=str,
                            help="path to the output TSV extended dataset")

    cli_parser.add_argument('-t', '--is_talk', action='store_true',
                            help='set if the category contains talk pages')

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)
        
    grabber = InstanceGrabber()
    grabber.get_instances(args.category, args.output_filename,
                          is_talk = args.is_talk)
    return()

if __name__ == '__main__':
    main()


