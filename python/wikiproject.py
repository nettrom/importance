#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Library for WikiProject-related pages.

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

class RatedPage():
    def __init__(self, talk_page_id, talk_revision_id, talk_page_title,
                 talk_is_archive, importance_rating,
                 art_page_id = -1, art_revision_id = -1,
                 art_is_redirect = 0):
        '''
        Instantiate a page with a given importance rating.  This is
        intended for pages within a specific WikiProject, meaning an
        article only has a single importance rating.  Because WikiProjects
        rate articles through their talk pages and some talk pages do not
        associate with an actual article (e.g. because the project template
        is on an archived talk page), we default the article-related values
        to "there is no article".

        :param talk_page_id: page ID of the associated talk page
        :type talk_page_id: int

        :param talk_revision_id: revision ID of the most recent revision of
                                 the talk page at the time the dataset
                                 was gathered.

        :param talk_page_title: title of the talk page (without namespace)
        :type talk_page_title: str

        :param importance_rating: the importance rating of the article
                                  in the current WikiProject
        :type importance_rating: str

        :param talk_is_archive: is the talk page an archive page?
        :type talk_is_archive: int

        :param art_page_id: page ID of the rated article
        :type art_page_id: int

        :param art_revision_id: revision ID of the most recent revision of
                                the rated article at the time the dataset
                                was gathered.
        :type art_revision_id: int

        :param art_is_redirect: is the article a redirect
        :type art_is_redirect: int
        '''

        self.page_id = art_page_id
        self.revision_id = art_revision_id
        self.is_redirect = art_is_redirect
        self.talk_page_id = talk_page_id
        self.talk_page_title = talk_page_title
        self.talk_revision_id = talk_revision_id
        self.talk_is_archive = talk_is_archive
        self.importance_rating = importance_rating

        ## Additional data that we populate through additional data gathering:

        self.q = '' # Wikidata identifier
        self.num_inlinks = 0 # Number of inlinks across a Wikipedia edition
        self.num_proj_inlinks = 0 # Number of project-internal inlinks
        self.num_views = 0 # Number of views
     
        ## Data that we populate using the clickstream dataset

        self.n_clicks = 0 # views in the clickstream dataset
        self.n_from_articles = 0 # referrer refers to another article
        self.n_active_inlinks = 0 # no. of unique articles referred to

        self.n_from_project_articles = 0 # referrer refers to a project article
        self.n_project_active_inlinks = 0 # no. of unique project articles

        ## Sets used to track unique article inlinks
        self.active_inlinks = set()
        self.project_active_inlinks = set()

    def __hash__(self):
        return(self.talk_page_id)

    def __eq__(self, other):
        if not isinstance(other, RatedPage):
            return(False)

        return(self.talk_page_id == other.talk_page_id)
        
def read_snapshot(snapshot_filename):
    '''
    Open the given snapshot filename, read it in and return a list
    of RatedPage objects corresponding to all pages in the snapshot.

    :param snapshot_filename: path to the snapshot TSV file
    :type snapshot_filename: str
    '''
    pages = list()
    
    with open(snapshot_filename, 'r', encoding='utf-8') as infile:
        infile.readline() # skip header
        
        for line in infile:
            cols = line.strip().split('\t')

            ## The importance rating is last, but needs to be the
            ## fifth element for the list to work as a single parameter,
            ## so we splice it in:
            cols = cols[:4] + cols[-1:] + cols[4:-1]

            page = RatedPage(*cols)
            pages.append(page)
    
    return(pages)

def write_snapshot(pages, snapshot_filename):
    '''
    Write out a snapshot-formatted TSV of the given pages.

    :param pages: list (or other iterable) of the pages to write out
    :type pages: list

    :param snapshot_filename: path to write the snapshot TSV file
    :type snapshot_filename: str
    '''

    with open(snapshot_filename, 'w', encoding='utf-8') as outfile:
        outfile.write('talk_page_id\ttalk_revision_id\ttalk_page_title\ttalk_is_archive\tart_page_id\tart_revision_id\tart_is_redirect\timportance_rating\n')
        for page in pages:
            outfile.write('{0.talk_page_id}\t{0.talk_revision_id}\t{0.talk_page_title}\t{0.talk_is_archive}\t{0.page_id}\t{0.revision_id}\t{0.is_redirect}\t{0.importance_rating}\n'.format(page))

    # ok, done
    return()
