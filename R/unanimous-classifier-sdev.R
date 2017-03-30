## Training a classifier with standard deviation data added
library(randomForest);
library(e1071);
library(gbm);
library(caret);

setkey(unanimous_viewdata, page_id);
setkey(unanimous_dataset, article_page_id);

unanimous_moreviews = unanimous_dataset[unanimous_viewdata];

## Let's first check that views still need log-transformation.
qplot(unanimous_moreviews$tot_avg, binwidth=500);
qplot(unanimous_moreviews$tot_sdev, binwidth=500);

## Answer is still heck, yes!
unanimous_moreviews$log_totavg = log10(1 + unanimous_moreviews$tot_avg);
unanimous_moreviews$log_f28avg = log10(1 + unanimous_moreviews$first28_avg);
unanimous_moreviews$log_s28avg = log10(1 + unanimous_moreviews$second28_avg);
unanimous_moreviews$log_t28avg = log10(1 + unanimous_moreviews$third28_avg);
unanimous_moreviews$log_w1avg = log10(1 + unanimous_moreviews$week1_avg);
unanimous_moreviews$log_w2avg = log10(1 + unanimous_moreviews$week2_avg);
unanimous_moreviews$log_w3avg = log10(1 + unanimous_moreviews$week3_avg);
unanimous_moreviews$log_w4avg = log10(1 + unanimous_moreviews$week4_avg);

unanimous_moreviews$log_totsdev = log10(1 + unanimous_moreviews$tot_sdev);
unanimous_moreviews$log_f28sdev = log10(1 + unanimous_moreviews$first28_sdev);
unanimous_moreviews$log_s28sdev = log10(1 + unanimous_moreviews$second28_sdev);
unanimous_moreviews$log_t28sdev = log10(1 + unanimous_moreviews$third28_sdev);
unanimous_moreviews$log_w1sdev = log10(1 + unanimous_moreviews$week1_sdev);
unanimous_moreviews$log_w2sdev = log10(1 + unanimous_moreviews$week2_sdev);
unanimous_moreviews$log_w3sdev = log10(1 + unanimous_moreviews$week3_sdev);
unanimous_moreviews$log_w4sdev = log10(1 + unanimous_moreviews$week4_sdev);

## Split the data into a training and test set for simplicity
training.set = unanimous_moreviews[is_training == 1];
test.set = unanimous_moreviews[is_training == 0];

importance_ratings = c('Top', 'High', 'Mid', 'Low');

n_folds = 10
training.set[, fold := seq(1, .N) %% n_folds];

importance_columns = c('log_inlinks', 'log_totavg', 'log_totsdev');
set.seed(42);
for(i in 0:(n_folds-1)) {
  cur_fold = i;
  imp_rfmodel = randomForest(x=training.set[fold != cur_fold,
                                            importance_columns, with=FALSE],
                             y=training.set[fold != cur_fold]$rating,
                             xtest = training.set[fold == cur_fold,
                                                  importance_columns, with=FALSE],
                             ytest = training.set[fold == cur_fold]$rating,
                             ntree=1001,
                             nodesize=512);
  training.set[fold == cur_fold, pred := imp_rfmodel$test$predicted];
}
training.set[, pred := ordered(pred, importance_ratings)];
length(training.set[pred == rating]$talk_page_id)/length(training.set$talk_page_id);

set.seed(42);
imp_rfmodel.7 = randomForest(x=training.set[, importance_columns, with=FALSE],
                             y=training.set$rating,
                             xtest=test.set[, importance_columns, with=FALSE],
                             ytest=test.set$rating,
                             ntree = 1001,
                             nodesize=512);
imp_rfmodel.7;

## We perform slightly better, but not a lot. What happens if we switch to the
## last 28 days and its standard deviation?
importance_columns = c('log_inlinks', 'log_t28avg', 'log_t28sdev');
set.seed(42);
for(i in 0:(n_folds-1)) {
  cur_fold = i;
  imp_rfmodel = randomForest(x=training.set[fold != cur_fold,
                                            importance_columns, with=FALSE],
                             y=training.set[fold != cur_fold]$rating,
                             xtest = training.set[fold == cur_fold,
                                                  importance_columns, with=FALSE],
                             ytest = training.set[fold == cur_fold]$rating,
                             ntree=1001,
                             nodesize=512);
  training.set[fold == cur_fold, pred := imp_rfmodel$test$predicted];
}
training.set[, pred := ordered(pred, importance_ratings)];
length(training.set[pred == rating]$talk_page_id)/length(training.set$talk_page_id);

set.seed(42);
imp_rfmodel.8 = randomForest(x=training.set[, importance_columns, with=FALSE],
                             y=training.set$rating,
                             xtest=test.set[, importance_columns, with=FALSE],
                             ytest=test.set$rating,
                             ntree = 1001,
                             nodesize=512);
imp_rfmodel.8;

## Nah, if we hypothesised that some type of articles would have different
## (non-correlated) values, the answer is no (their correlation is 0.95).

importance_columns = c('log_inlinks', 'log_w1avg', 'log_w1sdev',
                       'log_w2avg', 'log_w2sdev',
                       'log_w3avg', 'log_w3sdev',
                       'log_w4avg', 'log_w4sdev');
set.seed(42);
for(i in 0:(n_folds-1)) {
  cur_fold = i;
  imp_rfmodel = randomForest(x=training.set[fold != cur_fold,
                                            importance_columns, with=FALSE],
                             y=training.set[fold != cur_fold]$rating,
                             xtest = training.set[fold == cur_fold,
                                                  importance_columns, with=FALSE],
                             ytest = training.set[fold == cur_fold]$rating,
                             ntree=1001,
                             nodesize=512);
  training.set[fold == cur_fold, pred := imp_rfmodel$test$predicted];
}
training.set[, pred := ordered(pred, importance_ratings)];
length(training.set[pred == rating]$talk_page_id)/length(training.set$talk_page_id);

set.seed(42);
imp_rfmodel.9 = randomForest(x=training.set[, importance_columns, with=FALSE],
                             y=training.set$rating,
                             xtest=test.set[, importance_columns, with=FALSE],
                             ytest=test.set$rating,
                             ntree = 1001,
                             nodesize=512);
imp_rfmodel.9;

## No, we're not discovering information we did not already know based on the
## shorter timespan of view data.
