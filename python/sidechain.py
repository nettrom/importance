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

import yaml
import logging
import requests

from time import sleep
from collections import defaultdict

## Maximum number of articles, set to 50 for now, unless we get to be a bot,
## then it can be raised to 500.
MAX_ITEMS = 50

## Maximum number of retries we'll make to the Wikidata API
MAX_RETRIES = 3

## API URLs
WIKI_API_URL = 'https://{lang}.wikipedia.org/w/api.php'
WIKIDATA_API_URL = 'https://www.wikidata.org/w/api.php'

class RuleExistsError(Exception):
    '''
    A rule is attempted to be added that already exists.
    '''
    pass

class NoSuchRuleError(Exception):
    '''
    A rule is attempted to be modified that doesn't exist.
    '''
    pass

class TooManyItemsError(Exception):
    '''
    We are requested to investigate side-chaining for more items than
    we can process in single requests.
    '''
    pass

class PageTitleError(Exception):
    '''
    The Wikipedia API returned a page for which we do not have the title,
    suggesting something went terribly wrong.
    '''
    pass

class Ruleset:
    '''
    A set of rules defining side-chains through predicates (Wikidata properties)
    and objects (Wikidata entities) that cause certain articles to receive a
    pre-defined importance rating.
    '''
    def __init__(self):
        # Rules map a predicate (key) to an object (key)
        # to an importance rating (value). This allows for fast
        # lookup of whether a claim matches a rule.
        self.rules = defaultdict(dict)

    def add_rule(self, predicate_p, object_q, importance_rating):
        '''
        Add the given rule to the ruleset.

        :param predicate_p: identifier for the predicate property
        :type predicate_p: str

        :param object_q: identifier for the object of the predicate
        :type object_q: str

        :param importance_rating: the importance rating to give an article
                                  that matches the given predicate-object rule
        :type importance_rating: str
        '''

        if predicate_p in self.rules and \
           object_q in self.rules[predicate_p]:
            raise(RuleExistsException)

        self.rules[predicate_p][object_q] = importance_rating

    def modify_rule(self, predicate_p, object_q, importance_rating):
        '''
        Modify the given rule to match the supplied parameters.

        :param predicate_p: identifier for the predicate property
        :type predicate_p: str

        :param object_q: identifier for the object of the predicate
        :type object_q: str

        :param importance_rating: the importance rating to give an article
                                  that matches the given predicate-object rule
        :type importance_rating: str
        '''

        if not predicate_p in self.rules or \
           not object_q in self.rules[predicate_p]:
            raise(NoSuchRuleException)

        self.rules[predicate_p][object_q] = importance_rating

    def delete_rule(self, predicate_p, object_q):
        '''
        Delete the rule matching the given predicate and object. If there
        are no remaining rules for the given predicate, the predicate is
        also deleted.

        :param predicate_p: identifier for the predicate property
        :type predicate_p: str

        :param object_q: identifier for the object of the predicate
        :type object_q: str
        '''

        if not predicate_p in self.rules or \
           not object_q in self.rules[predicate_p]:
            raise(NoSuchRuleException)

        del(self.rules[predicate_p][object_q])

        if not self.rules[predicate_p]:
            del(self.rules[redicate_p])
        
def load(rule_file):
    '''
    Load in the rules defined in the given rule file and return it
    as a `Ruleset`

    :param rule_file: path to the file containing the rules
    :type rule_file: str
    '''

    with open(rule_file) as infile:
        rules = yaml.load(infile)

    project_name = ""
    ruleset = Ruleset()
        
    for (proj_name, pred_p, obj_q, imp_rating) in rules:
        project_name = proj_name

        ## Remove "wd:" and "wdt:" in pred_p and obj_q if present
        if ":" in pred_p:
            pred_p = pred_p.split(":")[1]
        if ":" in obj_q:
            obj_q = obj_q.split(":")[1]
        
        ruleset.add_rule(pred_p, obj_q, imp_rating)

    return((project_name, ruleset))

def sidechain(lang, articles, ruleset):
    ''''
    Determine which of the articles should be side-chained in the given
    context of a WikiProject, per the given set of rules.

    :param lang: language code for the Wikipedia edition we are working with
    :type lang: str

    :param articles: article titles to determine side-chaining for
    :type articles: list

    :param ruleset: the set of rules to be checked for side-chaining
    :type ruleset: `Ruleset`
    '''

    if len(articles) > MAX_ITEMS:
        raise(TooManyItemsError)

    ## By default, all articles are not sidechained, we'll move them over
    ## if we find evidence to the contrary.
    non_sidechain = set(articles)
    sidechain = defaultdict(list)

    # Note: For future reference and performance improvements, this can be
    # easily looked up in the page_props table, but requires a DB connection.
    wiki_query_params = {'action': 'query',
                         'prop': 'pageprops',
                         'titles': '',  # titles added later
                         'format': 'json'}

    wikidata_query_params = {'action': 'wbgetentities',
                             'sites': '{}wiki'.format(lang),
                             'ids': '', # added later
                             'languages': lang,
                             'maxlag': 5,
                             'format': 'json'}

    ## Mapping Wikidata identifier to article title
    q_title_map = {}
    
    # get the Wikidata item associated with every article
    wiki_query_params['titles'] = '|'.join(articles)
    r = requests.get(WIKI_API_URL.format(lang=lang),
                     params=wiki_query_params)
    r_json = r.json()

    pages = r_json['query']['pages']
    for pagedata in pages.values():
        ## Q: should we handle title normalization in results?

        ## Title doesn't match any known page in this Wikipedia
        if "missing" in pagedata:
            continue
        
        page_title = pagedata['title']
        if not page_title in non_sidechain:
            print('Missing page title {}'.format(page_title))
            raise(PageTitleError)

        try:
            wikibase_item = pagedata['pageprops']['wikibase_item']
            q_title_map[wikibase_item] = page_title
        except KeyError:
            continue # article does not have a Wikidata item associated with it
            
    # get the Wikidata entities for all the associated articles
    wikidata_query_params['ids'] = "|".join(q_title_map.keys())
    wikidata = wd_api_request(wikidata_query_params)
    for entity in wikidata['entities'].values():
        try:
            qid = entity['id']
        except KeyError:
            logging.warning('unable to get QID for {}'.format(entity))
            continue

        if not 'claims' in entity:
            ## No claims about this entity, it should not be side-chained
            continue

        if not qid in q_title_map:
            logging.warning('found QID {}, but does not map to any known title'.format(qid))
            continue

        ## Importance ratings of matched rules for this entity
        ratings = []
        
        for (claim, claimdata) in entity['claims'].items():
            ## If this claim does not occur in the ruleset, this claim
            ## cannot lead to the article being side-chained
            if not claim in ruleset.rules:
                continue

            if isinstance(claimdata, dict):
                try:
                    object_q = claimdata['mainsnak']['datavalue']['value']['id']
                    if object_q in ruleset.rules[claim]:
                        ratings.append(ruleset.rules[claim][object_q])
                except KeyError:
                    ## Claim does not point to a Wikidata entity
                    continue
                except TypeError:
                    ## Something along the line might not be a dict,
                    ## which means there is not a side-chain possibility
                    continue
            elif isinstance(claimdata, list):
                for c in claimdata:
                    try:
                        object_q = c['mainsnak']['datavalue']['value']['id']
                        if object_q in ruleset.rules[claim]:
                            ratings.append(ruleset.rules[claim][object_q])
                    except KeyError:
                        ## Claim does not point to a Wikidata entity
                        continue
                    except TypeError:
                        ## Something along the line might not be a dict,
                        ## which means there is not a side-chain possibility
                        continue

        if ratings:
            ## This entity needs to be side-chained
            page_title = q_title_map[qid]
            non_sidechain.remove(page_title)
            sidechain[page_title] = ratings
                    
    ## Return the sidechain and the non-sidechain
    return({'sidechain': sidechain,
            'non_sidechain': list(non_sidechain)})
        
def wd_api_request(params):
    '''
    Make an HTTP request to the Wikidata API with the given parameters and
    return the JSON dict fro mit.
    
    :param params: URL parameters
    :type params: dict
    '''
        
    content = {}

    done = False
    num_retries = 0
    while not done and num_retries < MAX_RETRIES:
        response = requests.get(WIKIDATA_API_URL, params=params)
        if response.status_code != 200:
            logging.warning('Wikidata returned status {}'.format(
                response.status_code))
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

        done = True
        continue

    return(content)
