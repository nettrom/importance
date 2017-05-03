#!/bin/bash

python ../../python/disambig-worklist.py $1 > disambiguation-worklist.txt
python ../../python/redirect-worklist.py $1 > redirect-worklist.txt
python ../../python/wikidata-worklist.py $1 > wikidata-worklist.txt
