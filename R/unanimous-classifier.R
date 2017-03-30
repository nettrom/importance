## Initial machine learning and evaluation on the dataset of unanimous ratings

library(randomForest);
library(e1071);
library(gbm);
library(caret);

## Split the data into a training and test set for simplicity
training.set = unanimous_dataset[is_training == 1];
test.set = unanimous_dataset[is_training == 0];

importance_columns = c('log_inlinks', 'log_views');
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
imp_rfmodel.1 = randomForest(x=training.set[, importance_columns, with=FALSE],
                             y=training.set$rating,
                             xtest=test.set[, importance_columns, with=FALSE],
                             ytest=test.set$rating,
                             ntree = 1001,
                             nodesize=512);
imp_rfmodel.1;

## Let's work on tuning the SVM (Support Vector Machine)
obj = tune(svm, rating ~ log_inlinks + log_views, data=training.set,
           ranges=list(gamma=seq(1.4, 1.5, by=0.01),
                       cost=seq(15, 17, by=1)),
           tunecontrol = tune.control(sampling='fix'));
summary(obj);
plot(obj);

## Based on an earlier run, I use gamma=1.40, cost=16, which produced err=0.5065
imp_svm = svm(rating ~ log_inlinks + log_views, data=training.set,
              cost=16, gamma=1.4, cross=10);
summary(imp_svm);

## Let's switch to evaluating the GBM (Gradient Boost Model)
imp_gbm = gbm(rating ~ log_inlinks + log_views,
              data=training.set,
              distribution='multinomial', n.trees=10000);
gbm.perf(imp_gbm); ## apparently this underestimates the number of trees

## http://allstate-university-hackathons.github.io/PredictionChallenge2016/GBM
## suggests to run cross-validation and then use gbm.perf
imp_gbm.cv = gbm(rating ~ log_inlinks + log_views,
                 data=training.set,
                 distribution='multinomial',
                 n.trees = 10000,
                 shrinkage = 0.01,
                 n.minobsinnode = 16,
                 cv.folds = 10,
                 n.cores = 1);
imp_gbm.cv.best = gbm.perf(imp_gbm.cv);
## Using 16 minimum observations in a node we need 1,024 trees.

## Based on our Random Forest test we know it has an error rate of 56.25% on
## the test set. Can the SVM or BGM fare better?
gbm_predictions = predict(object=imp_gbm.cv,
                          newdata=test.set,
                          n.trees = imp_gbm.cv.best,
                          type='response');
gbm_predictions = apply(gbm_predictions, 1, which.max);
gbm_predictions = sapply(gbm_predictions, function(x) { importance_ratings[x]; });
test.set$gbm_pred = gbm_predictions;
test.set$gbm_pred = ordered(test.set$gbm_pred, importance_ratings);

svm_predictions = predict(object=imp_svm,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;

## These can simply be copied over from the RF model :)
test.set$rf_pred = imp_rfmodel.1$test$predicted;

## Okay, let's generate some statistics...
conf_rf = table(test.set$rf_pred, test.set$rating);
conf_svm = table(test.set$svm_pred, test.set$rating);
conf_gbm = table(test.set$gbm_pred, test.set$rating);

confusionMatrix(conf_rf);
confusionMatrix(conf_svm);
confusionMatrix(conf_gbm);

## Show me Top-importance articles that the SVM labels as Mid- or Low-importance.
top_mislabelled = rbind(test.set[rating == 'Top' & svm_pred %in% c('Mid', 'Low')],
                        test.set[rating == 'Top' & svm_pred == 'Top']);
top_mislabelled[, is_correct := 'No'];
top_mislabelled[rating == 'Top' & svm_pred == 'Top', is_correct := 'Yes'];
top_mislabelled[, is_correct := factor(is_correct)];

## Give me plots of number of inlinks and number of views for these articles,
## and compare it to the correctly labelled articles.
ggplot(top_mislabelled, aes(x=log_inlinks, fill=is_correct, colour=is_correct)) +
  geom_density(alpha=0.75) + labs(x='Number of inlinks (log-10 scale)',
                                  title='Top-importance articles with Low/Mid-predictions');

ggplot(top_mislabelled, aes(x=log_views, fill=is_correct, colour=is_correct)) +
  geom_density(alpha=0.75) + labs(x='Number of views (log-10 scale)',
                                  title='Top-importance articles with Low/Mid-predictions');

## Looks like we have quite a number of Top-importance articles with less than
## 100 views and 100 inlinks. Let's investigate:
top_mislabelled[log_views < 2 & is_correct == 'No']$talk_page_title;

## Now, let's do this for Low-importance articles.
low_mislabelled = rbind(test.set[rating == 'Low' & svm_pred %in% c('Top', 'High')],
                        test.set[rating == 'Low' & svm_pred == 'Low']);
low_mislabelled[, is_correct := 'No'];
low_mislabelled[rating == 'Low' & svm_pred == 'Low', is_correct := 'Yes'];
low_mislabelled[, is_correct := factor(is_correct)];

## Give me plots of number of inlinks and number of views for these articles,
## and compare it to the correctly labelled articles.
ggplot(low_mislabelled, aes(x=log_inlinks, fill=is_correct, colour=is_correct)) +
  geom_density(alpha=0.75) + labs(x='Number of inlinks (log-10 scale)',
                                  title='Low-importance articles with Top/High-predictions');

ggplot(low_mislabelled, aes(x=log_views, fill=is_correct, colour=is_correct)) +
  geom_density(alpha=0.75) + labs(x='Number of views (log-10 scale)',
                                  title='Low-importance articles with Top/High-predictions');


## So, conversely to the Top-importance articles, 100 vies/inlinks appears to
## be a reasonable cutoff for identifying interesting examples.
low_mislabelled[log_views > 1.5 & log_inlinks > 1.5 & is_correct == 'No'];
