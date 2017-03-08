## Research questions 4-7

library(ggplot2);

## RQ4: How is number of ratings distributed?
## First, we join the article and rating count datasets.
setkey(only_articles, talk_page_id);
setkey(rating_counts, talk_page_id);

only_articles = only_articles[rating_counts];
## Note: this was a full join that left a bunch of articles with no titles
## since they're not actually articles, we'll have to remove those.
only_articles = only_articles[!is.na(talk_page_title)]

summary(only_articles$n_ratings);
quantile(only_articles$n_ratings, probs=seq(0,1,0.05))

only_articles[n_ratings > 50];

only_articles[, log_nratings := log2(1 + n_ratings)];
## qplot(only_articles$log_nratings, binwidth=0.1, xlab='number of ratings (log2-scale)');
qplot(only_articles$n_ratings, binwidth=1, xlab='number of ratings');

## I also want to know how many articles has each type of rating:
data.table(
  rating=c('Top', 'High', 'Mod', 'Low'),
  n_ratings=c(
    sum(only_articles$n_top),
    sum(only_articles$n_high),
    sum(only_articles$n_mid),
    sum(only_articles$n_low)
  )
);

## RQ5: How many articles have unanimous ratings

## Note: in this case we regard articles with a single rating as unanimous,
## there's another RQ later that looks at the union of articles.

n_unanimous_1 = data.table(
  rating=c('Top', 'High', 'Mid', 'Low'),
  n_unanimous=c(
    length(only_articles[n_top > 0 & n_high == 0 & n_mid == 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high > 0 & n_mid == 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high == 0 & n_mid > 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high == 0 & n_mid == 0 & n_low > 0 & n_unknown == 0 & n_na == 0]$talk_page_id)
  )
);
n_unanimous_1$rating = ordered(n_unanimous_1$rating,
                               c('Top', 'High', 'Mid', 'Low'));

ggplot(n_unanimous_1, aes(x=rating, y=n_unanimous)) + geom_bar(stat='identity') +
  xlab('Importance rating') + ylab('Number of articles (log10-scale)') +
  scale_y_log10();

## Side note: quite a few articles with unanimous top ratings are also
## in some kind of NA-importance category.
only_articles[n_top > 0 & n_high == 0 & n_mid == 0 & n_low == 0 & n_na > 0]$talk_page_id;

## RQ6: How many are rated by more than one project and unanimously rated?
## Note: we further restrict this one by removing articles with non-zero
## unknonwn or NA ratings.
n_unanimous = data.table(
  rating=c('Top', 'High', 'Mid', 'Low'),
  n_unanimous=c(
    length(only_articles[n_top > 1 & n_high == 0 & n_mid == 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high > 1 & n_mid == 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high == 0 & n_mid > 1 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high == 0 & n_mid == 0 & n_low > 1 & n_unknown == 0 & n_na == 0]$talk_page_id)
  )
);
n_unanimous$rating = ordered(n_unanimous$rating,
                             c('Top', 'High', 'Mid', 'Low'));

ggplot(n_unanimous, aes(x=rating, y=n_unanimous)) + geom_bar(stat='identity') +
  xlab('Importance rating') + ylab('Number of articles (log10-scale)') +
  scale_y_log10();

## RQ7: What is the overlap between ratings?
## We will investigate this by making a 4x4 matrix counting the pairwise
## overlap between ratings. Again we will remove unknown- and NA-rated articles.

overlap_pairs = matrix(
  c(length(only_articles[n_top > 0 & n_high == 0 & n_mid == 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top > 0 & n_high > 0 & n_mid == 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top > 0 & n_high == 0 & n_mid > 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top > 0 & n_high == 0 & n_mid == 0 & n_low > 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top > 0 & n_high > 0 & n_mid == 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high > 0 & n_mid == 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high > 0 & n_mid > 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high > 0 & n_mid == 0 & n_low > 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top > 0 & n_high == 0 & n_mid > 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high > 0 & n_mid > 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high == 0 & n_mid > 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high == 0 & n_mid > 0 & n_low > 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top > 0 & n_high == 0 & n_mid == 0 & n_low > 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high > 0 & n_mid == 0 & n_low > 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high == 0 & n_mid > 0 & n_low > 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high == 0 & n_mid == 0 & n_low > 0 & n_unknown == 0 & n_na == 0]$talk_page_id)
  ), byrow=TRUE, ncol=4
);
colnames(overlap_pairs) = c('Top', 'High', 'Mid', 'Low');
rownames(overlap_pairs) = c('Top', 'High', 'Mid', 'Low');

overlap_triplets = matrix(
  c(length(only_articles[n_top > 0 & n_high > 0 & n_mid > 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top > 0 & n_high > 0 & n_mid == 0 & n_low > 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high > 0 & n_mid > 0 & n_low == 0 & n_unknown == 0 & n_na == 0]$talk_page_id),
    length(only_articles[n_top == 0 & n_high > 0 & n_mid > 0 & n_low > 0 & n_unknown == 0 & n_na == 0]$talk_page_id)
  ), byrow=TRUE, ncol=2
);
colnames(overlap_triplets) = c('Mid', 'Low');
rownames(overlap_triplets) = c('Top+High', 'High+Mid');

## RQ8: How many articles have more than two ratings?
## I want to know how many articles have pairs of ratings, triplets, and all four.
## To get the pairs and triplets, I can just add together the numbers from
## the previous tables.
n_pairs = 5347+4224+2402+23904+21626+177397;
n_triplets = 2698+1083+12334;
n_quads = length(only_articles[n_top > 0 & n_high > 0 & n_mid > 0 & n_low > 0 & n_unknown == 0 & n_na == 0]$talk_page_id);

n_combos = data.table(
  n_ratings=c(2,3,4),
  n_articles=c(n_pairs, n_triplets, n_quads)
);

ggplot(n_combos, aes(x=n_ratings, y=n_articles)) + geom_bar(stat='identity') +
  xlab('Number of ratings') + ylab('Number of articles (log 10 scale)') +
  scale_y_log10();
