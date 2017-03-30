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

## Load in the dataset of unanimously rated articles after verification of
## their ratings using the talk pages
unanimous_verified = data.table(read.table(
  'datasets/unanimous-rated-articles-verified.tsv', header=TRUE,
  sep='\t', quote='', stringsAsFactors = FALSE
));

unanimous_viewdata = data.table(read.table(
  'datasets/unanimous-rated-articles-user-views-processed.tsv', header=TRUE,
  sep='\t', quote='', stringsAsFactors = FALSE
));

unanimous_userviews = data.table(read.table(
  'datasets/unanimous-rated-articles-user-views-processed.tsv', header=TRUE,
  sep='\t', quote='', stringsAsFactors = FALSE
));

unanimous_clickstream = data.table(read.table(
  'datasets/unanimous-clickdata.tsv', header=TRUE, sep='\t', quote='',
  stringsAsFactors=FALSE));

## Load in the WikiProject Medicine dataset
wpmed = data.table(read.table(
  'datasets/wpmed-dataset.tsv', header=TRUE, sep='\t', quote='',
  stringsAsFactors=FALSE
));

## Load in the WikiProject Medicine disambiguation pages
wpmed_disambig = data.table(read.table('datasets/wpmed-disambiguation-pages.tsv',
                                       header=TRUE, sep='\t', quote='',
                                       stringsAsFactors=FALSE));

## Load in the WikiProject Medicine clickstream dataset
wpmed_clickstream = data.table(read.table('datasets/wpmed-clickstream.tsv',
                                          header=TRUE, sep='\t', quote='',
                                          stringsAsFactors=FALSE));

## Load in the WikiProject Medicine dataset on individuals that we rated Low-importance
wpmed_individuals = data.table(read.table('datasets/wpmed-non-low-importance-people.tsv',
                                          header=TRUE, sep='\t', quote='',
                                          stringsAsFactors=FALSE));