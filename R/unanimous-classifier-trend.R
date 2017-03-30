## What if we instead encode some kind of trend variable?
## We calculate a 99% confidence interval using the second 28-day timespan
## as our basis. Then, we process weeks 1/2/3/4 as follows:
## If an article is within the CI we label it "0",
## if it's above the CI, we label it "+"
## if it's below the CI, we label it "-".

setkey(unanimous_viewdata, page_id);
setkey(unanimous_dataset, article_page_id);

unanimous_moreviews = unanimous_dataset[unanimous_viewdata];

## Turn the four weekly labels into factor.
unanimous_moreviews$week1_label = factor(unanimous_moreviews$week1_label);
unanimous_moreviews$week2_label = factor(unanimous_moreviews$week2_label);
unanimous_moreviews$week3_label = factor(unanimous_moreviews$week3_label);
unanimous_moreviews$week4_label = factor(unanimous_moreviews$week4_label);
unanimous_moreviews$last_4_label = factor(unanimous_moreviews$last_4_label);
unanimous_moreviews$last_8_label = factor(unanimous_moreviews$last_8_label);

unanimous_moreviews$log_totavg = log10(1 + unanimous_moreviews$tot_avg);
unanimous_moreviews$log_f28avg = log10(1 + unanimous_moreviews$first28_avg);
unanimous_moreviews$log_s28avg = log10(1 + unanimous_moreviews$second28_avg);
unanimous_moreviews$log_t28avg = log10(1 + unanimous_moreviews$third28_avg);
unanimous_moreviews$log_w1avg = log10(1 + unanimous_moreviews$week1_avg);
unanimous_moreviews$log_w2avg = log10(1 + unanimous_moreviews$week2_avg);
unanimous_moreviews$log_w3avg = log10(1 + unanimous_moreviews$week3_avg);
unanimous_moreviews$log_w4avg = log10(1 + unanimous_moreviews$week4_avg);

unanimous_moreviews$log_l1avg = log10(1 + unanimous_moreviews$last_1_avg);
unanimous_moreviews$log_l1sdev = log10(1 + unanimous_moreviews$last_1_sdev);
unanimous_moreviews$log_l4avg = log10(1 + unanimous_moreviews$last_4_avg);
unanimous_moreviews$log_l4sdev = log10(1 + unanimous_moreviews$last_4_sdev);
unanimous_moreviews$log_l8avg = log10(1 + unanimous_moreviews$last_8_avg);
unanimous_moreviews$log_l8sdev = log10(1 + unanimous_moreviews$last_8_sdev);

## Add the last week's standard deviation as a percentage of the previous
## four/eight week's mean.
unanimous_moreviews$last_1_4_ratio = 100*unanimous_moreviews$last_1_sdev/unanimous_moreviews$last_4_avg;
unanimous_moreviews$last_1_8_ratio = 100*unanimous_moreviews$last_1_sdev/unanimous_moreviews$last_8_avg;

unanimous_moreviews[last_1_4_ratio == Inf, last_1_4_ratio := 0];
unanimous_moreviews[last_1_8_ratio == Inf, last_1_8_ratio := 0];

unanimous_moreviews[, log_last14ratio := log10(1 + last_1_4_ratio)];
unanimous_moreviews[, log_last18ratio := log10(1 + last_1_8_ratio)];

## Split the data into a training and test set for simplicity
training.set = unanimous_moreviews[is_training == 1];
test.set = unanimous_moreviews[is_training == 0];

importance_ratings = c('Top', 'High', 'Mid', 'Low');

n_folds = 10
training.set[, fold := seq(1, .N) %% n_folds];

importance_columns = c('log_inlinks', 'log_s28avg', 'week4_label');
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
imp_rfmodel.10 = randomForest(x=training.set[, importance_columns, with=FALSE],
                             y=training.set$rating,
                             xtest=test.set[, importance_columns, with=FALSE],
                             ytest=test.set$rating,
                             ntree = 1001,
                             nodesize=512);
imp_rfmodel.10;

importance_columns = c('log_inlinks', 'log_s28avg', 'week1_label',
                       'week2_label', 'week3_label', 'week4_label');
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
imp_rfmodel.11 = randomForest(x=training.set[, importance_columns, with=FALSE],
                              y=training.set$rating,
                              xtest=test.set[, importance_columns, with=FALSE],
                              ytest=test.set$rating,
                              ntree = 1001,
                              nodesize=512);
imp_rfmodel.11;

## OK, this doesn't work either.
## Question is, what do we want to encode, and how do we encode that.
## Are we mainly interested in discovering an article's "true" popularity?
## Is there something about variation in popularity that might tell us something
## about _importance_? Are we just interested in using one/two 28-day block(s)
## to determine if another 28-day block needs adjusting? If so, why don't we just
## use all 84 days?
## After reading a longer introduction to ARIMA in Python
## https://www.analyticsvidhya.com/blog/2016/02/time-series-forecasting-codes-python/
## I'm not sure if ARIMA is useful here either. Keep in mind that in the ICWSM
## paper, we only studied the most popular articles, in other words they most
## likely have a lot of data.

## What we might want is a measure of variation that is _not_ correlated with
## number of views. Say article X has `n`` number of views and std. dev. `s`.
## `n` and `s` are correlated (in our dataset, each of the four single week
## views have cor > 0.94 in log-space). This means that we won't be encoding
## additional information if we use both of them. Instead, what we want is
## some form of measurement of variation that describes dissimilarity with
## the rest of the group. I'm wondering if it's worth calculating the percentiles
## of standard deviation for each class, and then adding that as a variable
## (either as a raw number or as a category rounded to the nearest 5%).

## An alternative is perhaps to do some simple edge-detection to flag articles
## with view surges in the 4th week. A key thing to keep in mind is that we cannot
## know an article's "true view rate", if we want it, just average over the whole
## 84 days or something. But, we can understand if an article's views in a given
## week appears somewhat out of the ordinary.

## Okay, we have all that data. Let's first investigate using the last week's avg
## together with the four/eight weeks preceeding it.

importance_columns = c('log_inlinks', 'log_l1avg', 'log_l4avg');
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
imp_rfmodel.12 = randomForest(x=training.set[, importance_columns, with=FALSE],
                              y=training.set$rating,
                              xtest=test.set[, importance_columns, with=FALSE],
                              ytest=test.set$rating,
                              ntree = 1001,
                              nodesize=512);
imp_rfmodel.12;

importance_columns = c('log_inlinks', 'log_l1avg', 'log_l8avg');
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
imp_rfmodel.13 = randomForest(x=training.set[, importance_columns, with=FALSE],
                              y=training.set$rating,
                              xtest=test.set[, importance_columns, with=FALSE],
                              ytest=test.set$rating,
                              ntree = 1001,
                              nodesize=512);
imp_rfmodel.13;

## No, we're still basically just moving some articles around, although overall
## performance is slightly better. Let's try the labels and the ratio.

importance_columns = c('log_inlinks', 'log_l1avg', 'log_l4avg', 'last_4_label');
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
imp_rfmodel.19 = randomForest(x=training.set[, importance_columns, with=FALSE],
                              y=training.set$rating,
                              xtest=test.set[, importance_columns, with=FALSE],
                              ytest=test.set$rating,
                              ntree = 1001,
                              nodesize=512);
imp_rfmodel.19;

importance_columns = c('log_inlinks', 'last_8_label', 'log_l8avg');
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
imp_rfmodel.15 = randomForest(x=training.set[, importance_columns, with=FALSE],
                              y=training.set$rating,
                              xtest=test.set[, importance_columns, with=FALSE],
                              ytest=test.set$rating,
                              ntree = 1001,
                              nodesize=512);
imp_rfmodel.15;

importance_columns = c('log_inlinks', 'last_1_4_ratio', 'log_l4avg');
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
imp_rfmodel.15 = randomForest(x=training.set[, importance_columns, with=FALSE],
                              y=training.set$rating,
                              xtest=test.set[, importance_columns, with=FALSE],
                              ytest=test.set$rating,
                              ntree = 1001,
                              nodesize=512);
imp_rfmodel.15;

importance_columns = c('log_inlinks', 'last_1_8_ratio', 'log_l8avg');
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
imp_rfmodel.16 = randomForest(x=training.set[, importance_columns, with=FALSE],
                              y=training.set$rating,
                              xtest=test.set[, importance_columns, with=FALSE],
                              ytest=test.set$rating,
                              ntree = 1001,
                              nodesize=512);
imp_rfmodel.16;

## Yeah, we're still just moving a couple of dozens of articles around, there
## does not appear to be any significant additional information here.

importance_columns = c('log_inlinks', 'log_last14ratio', 'log_l4avg');
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
imp_rfmodel.17 = randomForest(x=training.set[, importance_columns, with=FALSE],
                              y=training.set$rating,
                              xtest=test.set[, importance_columns, with=FALSE],
                              ytest=test.set$rating,
                              ntree = 1001,
                              nodesize=512);
imp_rfmodel.17;

importance_columns = c('log_inlinks', 'log_last18ratio', 'log_l8avg');
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
imp_rfmodel.18 = randomForest(x=training.set[, importance_columns, with=FALSE],
                              y=training.set$rating,
                              xtest=test.set[, importance_columns, with=FALSE],
                              ytest=test.set$rating,
                              ntree = 1001,
                              nodesize=512);
imp_rfmodel.18;

## Does an SVM fare better?
## The RF Model appears to work better with just a couple of weeks of data.
## How about we try that?
obj = tune(svm, rating ~ log_inlinks + log_last14ratio + log_l4avg,
           data=training.set,
           ranges=list(gamma=seq(1,10, by=1),
                       cost=seq(10, 100, by=10)),
           tunecontrol = tune.control(sampling='fix'));
summary(obj);
plot(obj);

## Based on the tuning output I use gamma=1 and cost=50
imp_svm = svm(rating ~ log_inlinks + log_last14ratio + log_l4avg,
              data=training.set,
              cost=6, gamma=0.1, cross=10);
summary(imp_svm);

svm_predictions = predict(object=imp_svm,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;

conf_svm = table(test.set$svm_pred, test.set$rating);
confusionMatrix(conf_svm);

## Yeah, it's just not better…
obj = tune(svm, rating ~ log_inlinks + log_l4avg,
           data=training.set,
           ranges=list(gamma=seq(1,10, by=1),
                       cost=seq(10, 100, by=10)),
           tunecontrol = tune.control(sampling='fix'));
summary(obj);
plot(obj);

## Based on the tuning output I use gamma=0.2 and cost=10
imp_svm = svm(rating ~ log_inlinks + log_last14ratio + log_l4avg,
              data=training.set,
              cost=10, gamma=0.2, cross=10);
summary(imp_svm);

svm_predictions = predict(object=imp_svm,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;

conf_svm = table(test.set$svm_pred, test.set$rating);
confusionMatrix(conf_svm);
