## Let's test how classification works when we extend the amount of view data
## we have available.

library(randomForest);
library(e1071);
library(gbm);
library(caret);

setkey(unanimous_viewdata, page_id);
setkey(unanimous_dataset, article_page_id);

unanimous_moreviews = unanimous_dataset[unanimous_viewdata];

## Let's first check that views still need log-transformation.
qplot(unanimous_moreviews$tot_avg, binwidth=500);

## Answer is, heck yes…
unanimous_moreviews$log_totavg = log10(1 + unanimous_moreviews$tot_avg);
unanimous_moreviews$log_f28avg = log10(1 + unanimous_moreviews$first28_avg);
unanimous_moreviews$log_s28avg = log10(1 + unanimous_moreviews$second28_avg);
unanimous_moreviews$log_t28avg = log10(1 + unanimous_moreviews$third28_avg);
unanimous_moreviews$log_w1avg = log10(1 + unanimous_moreviews$week1_avg);
unanimous_moreviews$log_w2avg = log10(1 + unanimous_moreviews$week2_avg);
unanimous_moreviews$log_w3avg = log10(1 + unanimous_moreviews$week3_avg);
unanimous_moreviews$log_w4avg = log10(1 + unanimous_moreviews$week4_avg);

## Split the data into a training and test set for simplicity
training.set = unanimous_moreviews[is_training == 1];
test.set = unanimous_moreviews[is_training == 0];

importance_columns = c('log_inlinks', 'log_totavg');
importance_ratings = c('Top', 'High', 'Mid', 'Low');

n_folds = 10
training.set[, fold := seq(1, .N) %% n_folds];

## We use 10-fold cross-validation to tune the nodesize parameter.
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
imp_rfmodel.2 = randomForest(x=training.set[, importance_columns, with=FALSE],
                             y=training.set$rating,
                             xtest=test.set[, importance_columns, with=FALSE],
                             ytest=test.set$rating,
                             ntree = 1001,
                             nodesize=512);
imp_rfmodel.2;

## Okay, that had no overall improvement, but some improvement to High-importance
## articles (meaning a slight decrease for the other three classes).

## What if we feed it the three 28-week averages?
importance_columns = c('log_inlinks', 'log_f28avg', 'log_s28avg', 'log_t28avg');

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
imp_rfmodel.3 = randomForest(x=training.set[, importance_columns, with=FALSE],
                             y=training.set$rating,
                             xtest=test.set[, importance_columns, with=FALSE],
                             ytest=test.set$rating,
                             ntree = 1001,
                             nodesize=512);
imp_rfmodel.3;

## Again the same issue as averaging across a longer timespan. Overall performance
## is slightly worse.

## What if we feed it the last four weeks?
importance_columns = c('log_inlinks', 'log_w1avg', 'log_w2avg', 'log_w3avg',
                       'log_w4avg');

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
imp_rfmodel.4 = randomForest(x=training.set[, importance_columns, with=FALSE],
                             y=training.set$rating,
                             xtest=test.set[, importance_columns, with=FALSE],
                             ytest=test.set$rating,
                             ntree = 1001,
                             nodesize=512);
imp_rfmodel.4;

## Same as before.
importance_columns = c('log_inlinks', 'log_s28avg',
                       'log_w1avg', 'log_w2avg', 'log_w3avg', 'log_w4avg');
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
imp_rfmodel.5 = randomForest(x=training.set[, importance_columns, with=FALSE],
                             y=training.set$rating,
                             xtest=test.set[, importance_columns, with=FALSE],
                             ytest=test.set$rating,
                             ntree = 1001,
                             nodesize=512);
imp_rfmodel.5;

## So… we don't see much improvement in the RF model with this. What about the SVM?
## Let's work on tuning the SVM (Support Vector Machine)
obj = tune(svm, rating ~ log_inlinks + log_f28avg + log_s28avg +
                log_w1avg + log_w2avg + log_w3avg + log_w4avg,
           data=training.set,
           ranges=list(gamma=seq(0.05, 0.25, by=0.05),
                       cost=seq(1, 10, by=1)),
           tunecontrol = tune.control(sampling='fix'));
summary(obj);
plot(obj);

## Based on the tuning output I use gamma=0.25 and cost=5
imp_svm = svm(rating ~ log_inlinks + log_f28avg + log_s28avg +
                log_w1avg + log_w2avg + log_w3avg + log_w4avg,
              data=training.set,
              cost=5, gamma=0.25, cross=10);
summary(imp_svm);

svm_predictions = predict(object=imp_svm,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;

conf_svm = table(test.set$svm_pred, test.set$rating);
confusionMatrix(conf_svm);

## Same as before.
importance_columns = c('log_inlinks', 'log_w3avg', 'log_w4avg');
set.seed(42);
imp_rfmodel.6 = randomForest(x=training.set[, importance_columns, with=FALSE],
                             y=training.set$rating,
                             xtest=test.set[, importance_columns, with=FALSE],
                             ytest=test.set$rating,
                             ntree = 1001,
                             nodesize=512);
imp_rfmodel.6;

## The RF Model appears to work better with just a couple of weeks of data.
## How about we try that?
obj = tune(svm, rating ~ log_inlinks + log_w3avg + log_w4avg,
           data=training.set,
           ranges=list(gamma=seq(0.05, 0.15, by=0.01),
                       cost=seq(2, 10, by=1)),
           tunecontrol = tune.control(sampling='fix'));
summary(obj);
plot(obj);

## Based on the tuning output I use gamma=0.1 and cost=6
imp_svm = svm(rating ~ log_inlinks + log_s28avg + log_w4avg,
              data=training.set,
              cost=6, gamma=0.1, cross=10);
summary(imp_svm);

svm_predictions = predict(object=imp_svm,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;

conf_svm = table(test.set$svm_pred, test.set$rating);
confusionMatrix(conf_svm);

## OK, I'm not getting any more signal out of this. All we get are shifts in
## some of the classes, there is no significant increase in overall performance.
