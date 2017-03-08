## RQ1: How many articles (in total and proportion of all articles) have at least one importance rating?

## Number of articles, based on https://quarry.wmflabs.org/query/17122
total_articles = 5073074

## Total number of articles that have importance ratings is defined by the
## number of rows where the talk page is not an archive and the article exists
## but is not a redirect.
length(impdata[talk_is_archive == 0 & page_id > 0 & is_redirect == 0]$page_id);

## What proportion?
100 * length(impdata[talk_is_archive == 0 & page_id > 0 & is_redirect == 0]$page_id)/total_articles;

## RQ2-7 concerns only articles, so lets get a dataset of only those
only_articles = impdata[talk_is_archive == 0 & page_id > 0 & is_redirect == 0];

## RQ2: Number of articles rated by a single project
length(only_articles[grep(",", only_articles$importance_ratings, invert=TRUE)]$page_id);

## RQ2: Proportion
100*length(only_articles[
  grep(",", only_articles$importance_ratings, invert=TRUE)
  ]$page_id)/length(only_articles$page_id);

## RQ3: Number of articles rated by multiple projects
length(only_articles[grep(",", only_articles$importance_ratings)]$page_id);

## RQ3: Proportion
100*length(only_articles[
  grep(",", only_articles$importance_ratings)
  ]$page_id)/length(only_articles$page_id);
