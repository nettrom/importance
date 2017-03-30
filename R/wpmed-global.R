## Comparing the global classifier on the WPMED dataset, and vice versa.
## This involves a little bit of fiddling because our measure of proportions
## of inlinks from WPMED is not in the global dataset. But we'll get to that later…

## Global classifier on the WPMED dataset.

## This is the classifier we used on that dataset.
## Based on an earlier run, I use gamma=1.40, cost=16, which produced err=0.5065
## imp_svm = svm(rating ~ log_inlinks + log_views, data=training.set,
##              cost=16, gamma=1.4, cross=10);
summary(imp_svm);

## Our current test set is the WPMED test set, but I decided to name the
## log_inlinks column differently, let's fix that
test.set[, log_inlinks := log_links];
wpmed[, log_inlinks := log_links];

svm_predictions = predict(object=imp_svm,
                          newdata=test.set);
test.set$global_pred = svm_predictions;
conf_svm = table(test.set$global_pred, test.set$rating);
confusionMatrix(conf_svm);

test.set[rating == "Top" & global_pred == 'High'];

test.set[rating == "High" & global_pred == 'Top'];

svm_predictions = predict(object=imp_svm,
                          newdata=wpmed);
wpmed$global_pred = svm_predictions;
conf_svm = table(wpmed$rating, wpmed$global_pred);
cf = confusionMatrix(conf_svm);

## Switch the test set to the unanimous one we previously used.
test.set = unanimous_dataset[is_training == 0];

## Add the n_local_dampened to the test.set with a default value of 1
## (which means no inlinks are from WPMED)
test.set[, n_local_dampened := 1.0];

## Let's see if any articles in this test set are in WPMED.
test.set[talk_page_id %in% wpmed$talk_page_id];

## We find 28 articles in WPMED, set their value to the one in the WPMED dataset.
for(page in test.set[talk_page_id %in% wpmed$talk_page_id]$talk_page_id) {
  test.set[talk_page_id == page,
           n_local_dampened := wpmed[talk_page_id == page]$n_local_dampened];
}

## Also need to rename log_inlinks to log_links
test.set[, log_links := log_inlinks];

## Looks like that worked, let's make some predictions!
svm_predictions = predict(object=imp_svm.kamps,
                          newdata=test.set);
test.set$kamps_pred = svm_predictions;
cf_global_kamps = confusionMatrix(table(test.set$rating, test.set$kamps_pred))
