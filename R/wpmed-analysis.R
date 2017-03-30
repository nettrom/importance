## Visual analysis of WPMED variables, similar to what we did
## for the global classifier.

library(ggplot2);

## 1: Summaries, overall and by class
summary(wpmed$n_inlinks);
summary(wpmed$n_proj_inlinks);
summary(wpmed$n_views);

## We have some -1 values in our inlink counts.
wpmed[n_inlinks == -1];

## Looks like we should set n_inlinks and n_proj_inlinks to 0
## for pages where the talk page is not an archive and the article
## is not a redirect.
wpmed[talk_is_archive == 0 & art_is_redirect == 0 & n_inlinks == -1,
      n_inlinks := 0];
wpmed[talk_is_archive == 0 & art_is_redirect == 0 & n_proj_inlinks == -1,
      n_proj_inlinks := 0];

## Filter out archive talk pages
wpmed = wpmed[talk_is_archive == 0];

## What about pages where the article is a redirect?
wpmed[art_is_redirect == 1];
## Looks like these are all valid redirects, but are given an actual
## importance rating, instead of rating them NA like some other projects do.
## We'll have to filter out those too.
wpmed = wpmed[art_is_redirect == 0];

## Argh, why did I not just name the column rating?
wpmed[, rating := importance_rating];
wpmed$rating = ordered(wpmed$rating, c('Top', 'High', 'Mid', 'Low'));

summary(wpmed[rating == 'Top']$n_inlinks);
summary(wpmed[rating == 'Top']$n_proj_inlinks);
summary(wpmed[rating == 'Top']$n_views);

summary(wpmed[rating == 'High']$n_inlinks);
summary(wpmed[rating == 'High']$n_proj_inlinks);
summary(wpmed[rating == 'High']$n_views);

summary(wpmed[rating == 'Mid']$n_inlinks);
summary(wpmed[rating == 'Mid']$n_proj_inlinks);
summary(wpmed[rating == 'Mid']$n_views);

summary(wpmed[rating == 'Low']$n_inlinks);
summary(wpmed[rating == 'Low']$n_proj_inlinks);
summary(wpmed[rating == 'Low']$n_views);

## Summaries suggest skewed distributions, let's plot some histograms
qplot(wpmed$n_inlinks, binwidth=100);
qplot(wpmed$n_proj_inlinks, binwidth=100);
qplot(wpmed$n_views, binwidth=100);

## The histograms all suggest we should try log-transforming these.
wpmed[, log_links := log10(1 + n_inlinks)];
wpmed[, log_projlinks := log10(1 + n_proj_inlinks)];
wpmed[, log_views := log10(1 + n_views)];

qplot(wpmed$log_links, binwidth=0.1);
qplot(wpmed$log_projlinks, binwidth=0.1);
qplot(wpmed$log_views, binwidth=0.1);

## These are not as neatly distributed as the global ones, probably due to
## the much smaller dataset. Does look better than without transformation, though.

## Next step, density plots by class.
## 2.1: Number of inlinks by rating class
ggplot(wpmed, aes(log_links, fill=rating, colour=rating)) +
  geom_density(alpha=0.25) + xlab('Number of inlinks (log-10 scale)');

## 2.2: Number of project-limited inlinks by rating class
ggplot(wpmed, aes(log_projlinks, fill=rating, colour=rating)) +
  geom_density(alpha=0.25) + xlab('Number of inlinks from project articles (log-10 scale)');

## 2.2: Number of viws by rating class
ggplot(wpmed, aes(log_views, fill=rating, colour=rating)) +
  geom_density(alpha=0.25) + xlab('Number of article views (log-10 scale)');

## These all look more clearly separated by class than what we saw for the
## global classifier. Not sure whether global inlink counts will perform
## better/worse than project-specific inlink counts, though, although I
## suspect it'll perform better.
