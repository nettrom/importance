## Kamps & Koolen (2008) use a TF/IDF-inspired approach to dampen the influence
## of local indegree if the global indegree is high. Since our dataset is
## limited to WikiProject Medicine articles, this might provide us with
## some good signal as well.

library(randomForest);
library(e1071);
library(gbm);
library(caret);
library(smotefamily);

## Based on the earlier results, we take the 1,000 item training dataset
## and add a dampened local inlink count to that dataset and the test set.

training.set.1000[, n_local_dampened := 1 + (10^log_projlinks/(1 + 10^log_links))];
test.set[, n_local_dampened := 1 + (10^log_projlinks/(1 + 10^log_links))];

## What's the distribution of that local measure?
ggplot(training.set.1000, aes(n_local_dampened, fill=rating, colour=rating)) +
  geom_density(alpha=0.25) + xlab('Number of project inlinks (dampened)');

ggplot(training.set.1000, aes(x=log_links, y=n_local_dampened,
       fill=rating, colour=rating)) + geom_point();

ggplot(training.set.1000, aes(x=log_projlinks, y=n_local_dampened,
                              fill=rating, colour=rating)) + geom_point();

ggplot(training.set.1000, aes(x=log_views, y=n_local_dampened,
                              fill=rating, colour=rating)) + geom_point();

## Not sure how well it'll perform, but we'll test it.
obj = tune(svm, rating ~ log_links + log_views + n_local_dampened,
           data=training.set.1000,
           ranges=list(gamma=seq(0.5, 2.0, by=0.1),
                       cost=seq(1, 10, by=1)),
           tunecontrol = tune.control(sampling='fix'));
plot(obj);
summary(obj);

## We use gamma=1, cost=3, as suggested by the tuning result.
imp_svm.kamps = svm(rating ~ log_links + log_views + n_local_dampened,
                    data=training.set.1000,
                    gamma=1, cost=3, cross=10);
summary(imp_svm.kamps);

svm_predictions = predict(object=imp_svm.kamps,
                          newdata=test.set);
test.set$kamps_pred = svm_predictions;
conf_kamps = table(test.set$kamps_pred, test.set$rating);
confusionMatrix(conf_kamps);

test.set[rating == 'Top' & kamps_pred == 'Low'];
test.set[rating == 'Top' & kamps_pred == 'Mid'];

test.set[rating == 'High' & kamps_pred == 'Low'];

test.set[rating == 'Mid' & kamps_pred == 'Top'];

test.set[rating == 'Low' & kamps_pred == 'High'];
test.set[rating == 'Low' & kamps_pred == 'Top'];

## In order to learn more about how proportion of project inlinks affects
## classification, I run the classifier on the entire WPMED dataset and
## study the results.
wpmed[, n_local_dampened := 1 + (10^log_projlinks/(1 + 10^log_links))];
svm_predictions = predict(object=imp_svm.kamps,
                          newdata=wpmed);
wpmed$kamps_pred = svm_predictions;
cf_kamps = confusionMatrix(table(wpmed$rating, wpmed$kamps_pred));

## Looking at the confusion matrix, we find 1,002 Low-importance articles predicted
## to be High-importance. That's too many to list all of them, so how about I sample
## 50 for us to look at? We can grab all the articels from the other categories.

wpmed[rating == 'Top' & kamps_pred == 'Low']; # no articles
wpmed[rating == 'Top' & kamps_pred == 'Mid'];

wpmed[rating == 'High' & kamps_pred == 'Low',
      list(talk_page_title, n_inlinks, n_proj_inlinks, n_views, n_local_dampened)];
qplot(wpmed[rating == 'High' & kamps_pred == 'Low']$n_local_dampened,
      binwidth=0.05);

wpmed[rating == 'Mid' & kamps_pred == 'Top'];

wpmed[rating == 'Low' & kamps_pred == 'High'];
wpmed[rating == 'Low' & kamps_pred == 'Top'];

make_wiki_list = function(dataset, true_rating, pred_rating) {
  ## Make a UL of all titles in the dataset where their
  ## true and predicted rating are as given.
  output_str = c("<ul>");
  titles = sort(gsub('_', ' ', dataset[rating == true_rating & kamps_pred == pred_rating]$talk_page_title));
  for(title in titles) {
    output_str = append(output_str, paste('<li>[[:en:', title, '|', title, ']]</li>', sep=''));
  }
  output_str = append(output_str, "</ul>");
  paste(output_str, sep='', collapse="\n");
}

cat(make_wiki_list(wpmed, "Top", "Low"));
cat(make_wiki_list(wpmed, "Top", "Mid"));

cat(make_wiki_list(wpmed, "High", "Low"));

cat(make_wiki_list(wpmed, "Mid", "Top"));

cat(make_wiki_list(wpmed, "Mid", "Top"));

cat(make_wiki_list(wpmed, "Low", "High"));
cat(make_wiki_list(wpmed, "Low", "Top"));

## Take out articles that are disambiguation pages
wpmed = wpmed[!(talk_page_id %in% wpmed_disambig$page_id)]

## How many articles do we have, and how many do we correctly predict?
length(wpmed$talk_page_id);
length(wpmed[rating == kamps_pred]$talk_page_id);
18654/29320;
