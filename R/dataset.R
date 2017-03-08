## Load in the article importance dataset

library(data.table);

impdata = data.table(read.table('datasets/fixed_importance_dataset.tsv',
                                header=TRUE, sep='\t', quote='',
                                stringsAsFactors=FALSE,
                                colClasses = c('numeric', 'numeric', 'character',
                                               'numeric', 'numeric', 'numeric',
                                               'numeric', 'character', 'character')
));

## Check that we do not have duplicate talk pages in our dataset.
length(unique(impdata$talk_page_id)) == length(impdata$talk_page_id);

## Add the dataset on rating counts
rating_counts = data.table(fread('datasets/rating-counts.tsv',
                                      header=TRUE, sep='\t'));

## Load in the dataset of unanimous rated articles after it has been extended
## with inlink counts and views
unanimous_dataset = data.table(read.table(
  'datasets/unanimous-rated-articles-extended.tsv', header=TRUE,
  sep='\t', quote='', stringsAsFactors=FALSE));