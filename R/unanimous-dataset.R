## Create a dataset of articles with unanimous ratings

## Columns I want in the dataset:
## talk_page_id
## talk_revision_id
## talk_page_title
## page_id (let's rename it article_page_id)
## revision_id (let's rename it article_revision_id)
## rating (Top/High/Mid/Low)
## is_training (is it training (1) or test data? (0))

## We have 1,900 Top-rated articles, we all add of them.
unanimous_dataset = only_articles[
  n_top > 1 & n_high == 0 & n_mid == 0 & n_low == 0 & n_unknown == 0 & n_na == 0,
  list(talk_page_id, talk_revision_id, talk_page_title,
       'article_page_id'=page_id, 'article_revision_id'=revision_id)
  ][, rating := 'Top'][, is_training := 1];

## Now, let's sample 1,900 articles from each of the other classes and add
## them to the dataset.
unanimous_dataset = rbind(unanimous_dataset, only_articles[
  n_top == 0 & n_high > 1 & n_mid == 0 & n_low == 0 & n_unknown == 0 & n_na == 0,
  list(talk_page_id, talk_revision_id, talk_page_title,
       'article_page_id'=page_id, 'article_revision_id'=revision_id)
  ][sample(.N, 1900)][, rating := 'High'][, is_training := 1]);
unanimous_dataset = rbind(unanimous_dataset, only_articles[
  n_top == 0 & n_high == 0 & n_mid > 1 & n_low == 0 & n_unknown == 0 & n_na == 0,
  list(talk_page_id, talk_revision_id, talk_page_title,
       'article_page_id'=page_id, 'article_revision_id'=revision_id)
  ][sample(.N, 1900)][, rating := 'Mid'][, is_training := 1]);
unanimous_dataset = rbind(unanimous_dataset, only_articles[
  n_top == 0 & n_high == 0 & n_mid == 0 & n_low > 1 & n_unknown == 0 & n_na == 0,
  list(talk_page_id, talk_revision_id, talk_page_title,
       'article_page_id'=page_id, 'article_revision_id'=revision_id)
  ][sample(.N, 1900)][, rating := 'Low'][, is_training := 1]);

## Let's ensure that no article is found multiple times here
length(unanimous_dataset$article_page_id) == length(unique(unanimous_dataset$article_page_id))
length(unanimous_dataset$talk_page_id) == length(unique(unanimous_dataset$talk_page_id))

## Now, sample 400 articles from each of the three other categories and assign
## them to the test set.
unanimous_dataset[
  talk_page_id %in% unanimous_dataset[, .SD[sample(.N, 400)], by='rating']$talk_page_id,
  is_training := 0]

## Dataset looks good, write it out.
write.table(unanimous_dataset, file='datasets/unanimous-rated-articles.tsv',
            quote=FALSE, sep='\t', fileEncoding='UTF-8', row.names=FALSE);
