#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Script that processes a graph and identifies any parent node where 
a majority of its children are Low-importance.

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

import networkx as nx

from operator import attrgetter

class LowNode:
    def __init__(self, QID, n_low, n_rated, low_ratio, rel_types):
        self.qid = QID
        self.n_low = n_low
        self.n_rated = n_rated
        self.low_ratio = low_ratio
        self.rel_types = rel_types

def find_majority_low_nodes(input_filename, output_filename, min_children=3):
    '''
    Load the graph in from the input GEXF formatted file, then process
    all nodes and identify those that have at least `min_children` child
    nodes, and where a majority of them are Low-importance.
    '''

    graph = nx.read_gexf(input_filename)

    ## Maps label to number of nodes pointing to it
    found_nodes = dict()
    
    for (label, degree) in graph.degree().items():
        if degree >= min_children:
            n_low = 0
            n_rated = 0
            preds = graph.predecessors(label)
            etypes = set()
            for pred in preds:
                try:
                    rating = graph.node[pred]['rating']
                    if rating == "Low":
                        n_low += 1
                        ## Note: we are mainly interested in edges between
                        ## Low-importance items and this parent. 
                        etype = graph.get_edge_data(pred, label)
                        etypes.add(etype['ptype'])
                    n_rated += 1
                except KeyError:
                    # not an article
                    continue
            if n_rated >= min_children and n_low/n_rated > 0.5:
                found_nodes[label] = LowNode(label, n_low, n_rated,
                                             n_low/n_rated, etypes)

    with open(output_filename, 'w', encoding='utf-8') as outfile:
        outfile.write('QID\tn_children\tlow_ratio\trel_types\n')
        for low_node in sorted(found_nodes.values(),
                               key=attrgetter('n_low'),
                               reverse=True):
            outfile.write('{0.qid}\t{0.n_rated}\t{0.n_low}\t{0.low_ratio}\t{rel_types}\n'.format(low_node, rel_types=",".join(low_node.rel_types)))
                
    # ok, done
    return()

def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to find parents of majority Low-importance children"
    )

    cli_parser.add_argument("input_filename", type=str,
                            help="path to the input GEXF graph")

    cli_parser.add_argument("output_filename", type=str,
                            help="path to output TSV file")
    
    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    find_majority_low_nodes(args.input_filename, args.output_filename)
        
    return()

if __name__ == '__main__':
    main()

        
