## Inspection of number of views & inlinks for our different classes
## in the unanimously rated dataset.

library(ggplot2);

## 1: Summaries, overall and by class
summary(unanimous_dataset$num_inlinks);
summary(unanimous_dataset$num_views);

summary(unanimous_dataset[rating == 'Top']$num_inlinks);
summary(unanimous_dataset[rating == 'Top']$num_views);

summary(unanimous_dataset[rating == 'High']$num_inlinks);
summary(unanimous_dataset[rating == 'High']$num_views);

summary(unanimous_dataset[rating == 'Mid']$num_inlinks);
summary(unanimous_dataset[rating == 'Mid']$num_views);

summary(unanimous_dataset[rating == 'Low']$num_inlinks);
summary(unanimous_dataset[rating == 'Low']$num_views);

## Curious about articles with 0 inlinks, let's look at those:
unanimous_dataset[num_inlinks == 0];

## 2.0 Log-transformation and ordering
unanimous_dataset[, log_inlinks := log10(1 + num_inlinks)];
unanimous_dataset[, log_views := log10(1 + num_views)];

unanimous_dataset$rating = ordered(unanimous_dataset$rating,
                                   c('Top', 'High', 'Mid', 'Low'));

## 2: Graphs
## 2.1: Number of inlinks by rating class

ggplot(unanimous_dataset, aes(log_inlinks, fill=rating, colour=rating)) +
  geom_density(alpha=0.25) + xlab('Number of inlinks (log-10 scale)');

## 2.2: Number of views by rating class
ggplot(unanimous_dataset, aes(log_views, fill=rating, colour=rating)) +
  geom_density(alpha=0.25) + xlab('Number of views (log-10 scale)');

## 2.3: Faceted scatterplot of views/inlinks
ggplot(unanimous_dataset, aes(x=log_inlinks, y=log_views, colour=rating)) +
  geom_point(alpha=0.75) + facet_grid(. ~ rating) +
  xlab('Number of inlinks (log-10 scale)') +
  ylab('Number of views (log-10 scale)');

ggplot(unanimous_dataset, aes(x=log_inlinks, y=log_views, colour=rating)) +
  geom_point(alpha=0.5) +
  xlab('Number of inlinks (log-10 scale)') +
  ylab('Number of views (log-10 scale)');