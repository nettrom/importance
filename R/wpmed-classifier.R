## Training and testing a classifier for WikiProject Medicine.

library(randomForest);
library(e1071);
library(gbm);
library(caret);
library(smotefamily);

## First of all, we have to handle the problem of the project having
## only 90 articles in the Top class.  I suggest we put 40 articles
## in the test set, then use the remaining 50 to generate 200/450 synthetic
## examples using SMOTE.

## Labelling a test-set of 160 articles.
wpmed[, is_training := 1];
wpmed[talk_page_id %in% wpmed[, .SD[sample(.N, 40)], by='rating']$talk_page_id,
  is_training := 0];

## Splitting it up into a training and test set.
test.set = wpmed[is_training == 0];
training.set = wpmed[is_training == 1];

## We are generating synthetic examples for Top-importance, so we add a binary
## column for identifying those.
training.set[, is_top := 0];
training.set[rating == 'Top', is_top := 1];

## We want a dataset with 200 synthetic samples, and 450 synthetic samples
## (for a total of 250 Top-importance, and 500 Top-importance articles, respectively)
training_data.250 = rbind(
  training.set[is_top == 0][sample(.N, 250)],
  training.set[is_top == 1])[, list(art_page_id, log_links,
                                    log_projlinks, log_views, is_top)];
training_data.500 = rbind(
  training.set[is_top == 0 & !(art_page_id %in% training_data.250$art_page_id)][sample(.N, 500)],
  training.set[is_top == 1])[, list(art_page_id, log_links,
                                    log_projlinks, log_views, is_top)];

synth_data.250 = SMOTE(training_data.250[, list(log_links, log_projlinks, log_views)],
                       training_data.250$is_top);
synth_data.500 = SMOTE(training_data.500[, list(log_links, log_projlinks, log_views)],
                       training_data.500$is_top);

## We now create new training dataset using the real and synthetic Top-importance
## data, with a similar number of samples from each of the other three classes.
training.set.1000 = rbind(synth_data.250$data[class == 1][,
        list(log_links, log_projlinks, log_views, class, rating='Top')],
      training.set[rating == 'High'][sample(.N, 250)][,
        list(log_links, log_projlinks, log_views, rating, class=0)],
      training.set[rating == 'Mid'][sample(.N, 250)][,
        list(log_links, log_projlinks, log_views, rating, class=0)],
      training.set[rating == 'Low'][sample(.N, 250)][,
        list(log_links, log_projlinks, log_views, rating, class=0)]
      );

training.set.2000 = rbind(synth_data.500$data[class == 1][,
        list(log_links, log_projlinks, log_views, class, rating='Top')],
      training.set[rating == 'High'][sample(.N, 500)][,
        list(log_links, log_projlinks, log_views, rating, class=0)],
      training.set[rating == 'Mid'][sample(.N, 500)][,
        list(log_links, log_projlinks, log_views, rating, class=0)],
      training.set[rating == 'Low'][sample(.N, 500)][,
        list(log_links, log_projlinks, log_views, rating, class=0)]
);

## Now we can start training some classifiers!

importance_columns = c('log_links', 'log_views');
importance_ratings = c('Top', 'High', 'Mid', 'Low');

n_folds = 10
training.set.1000[, fold := seq(1, .N) %% n_folds];
training.set.2000[, fold := seq(1, .N) %% n_folds];

rf_crossvalidation = function(tset, pred_columns, ntrees, nodesize) {
  ## Run 10-fold cross-validation using a Random Forest classifier
  ## and return the overall accuracy.  Note that classes must be balanced
  ## for overall accuracy to be a useful measure of performance.
  
  n_folds = 10;
  tset[, fold := seq(1, .N) %% n_folds];
  set.seed(NULL);
  for(i in 0:(n_folds-1)) {
    cur_fold = i;
    imp_rfmodel = randomForest(x=tset[fold != cur_fold, pred_columns, with=FALSE],
                               y=tset[fold != cur_fold]$rating,
                               xtest = tset[fold == cur_fold, pred_columns, with=FALSE],
                               ytest = tset[fold == cur_fold]$rating,
                               ntree=ntrees,
                               nodesize=nodesize);
    tset[fold == cur_fold, pred := imp_rfmodel$test$predicted];
  }
  tset[, pred := ordered(pred, importance_ratings)];
  length(tset[pred == rating]$rating)/length(tset$rating);
}


## Random Forest
importance_columns = c('log_links', 'log_views');
for(nodesize in c(1,2,4,8,16,32,64,128)) {
  for(treesize in seq(1,10)*100+1) {
    print(paste(treesize, 'trees and nodesize', nodesize, 'accuracy:',
      rf_crossvalidation(training.set.1000, importance_columns,
                         treesize, nodesize)));
  }
}

## Based on performance we choose nodesize 16 and 301 trees and test this
## on the test set.
set.seed(42);
wpmed.rfmodel.1000.1 = randomForest(
  x=training.set.1000[, importance_columns, with=FALSE],
  y=training.set.1000$rating,
  xtest = test.set[, importance_columns, with=FALSE],
  ytest = test.set$rating,
  ntree=301,
  nodesize=16);
wpmed.rfmodel.1000.1;

## Using project-interal wikilinks
importance_columns = c('log_projlinks', 'log_views');
for(nodesize in c(1,2,4,8,16,32,64,128)) {
  for(treesize in seq(1,10)*100+1) {
    print(paste(treesize, 'trees and nodesize', nodesize, 'accuracy:',
                rf_crossvalidation(training.set.1000, importance_columns,
                                   treesize, nodesize)));
  }
}

## Combining both global and project-specific links
importance_columns = c('log_links', 'log_projlinks', 'log_views');
for(nodesize in c(1,2,4,8,16,32,64,128)) {
  for(treesize in seq(1,10)*100+1) {
    print(paste(treesize, 'trees and nodesize', nodesize, 'accuracy:',
                rf_crossvalidation(training.set.1000, importance_columns,
                                   treesize, nodesize)));
  }
}

## Based on performance we choose nodesize 4 and 1001 trees and test this
## on the test set.
set.seed(42);
wpmed.rfmodel.1000.2 = randomForest(
  x=training.set.1000[, importance_columns, with=FALSE],
  y=training.set.1000$rating,
  xtest = test.set[, importance_columns, with=FALSE],
  ytest = test.set$rating,
  ntree=1001,
  nodesize=4);
wpmed.rfmodel.1000.2;

## Let's repeat the procedure using the larger training set.
## Random Forest
importance_columns = c('log_links', 'log_views');
accs = c();
for(nodesize in c(1,2,4,8,16,32,64,128)) {
  for(treesize in seq(1,10)*100+1) {
    accs = append(accs, rf_crossvalidation(training.set.2000, importance_columns,
                                           treesize, nodesize))
  }
}
acc.matrix = matrix(100*accs, ncol=10, byrow=TRUE);
colnames(acc.matrix) = as.character(seq(1,10)*100+1)
rownames(acc.matrix) = as.character(c(1,2,4,8,16,32,64,128));

## Based on performance we choose nodesize 16 and 201 trees and test this
## on the test set.
set.seed(42);
wpmed.rfmodel.2000.1 = randomForest(
  x=training.set.2000[, importance_columns, with=FALSE],
  y=training.set.2000$rating,
  xtest = test.set[, importance_columns, with=FALSE],
  ytest = test.set$rating,
  ntree=201,
  nodesize=16);
wpmed.rfmodel.2000.1;

## Let's use internal wikilinks instead
importance_columns = c('log_projlinks', 'log_views');
accs = c();
for(nodesize in c(1,2,4,8,16,32,64,128)) {
  for(treesize in seq(1,10)*100+1) {
    accs = append(accs, rf_crossvalidation(training.set.2000, importance_columns,
                                           treesize, nodesize))
  }
}
acc.matrix = matrix(100*accs, ncol=10, byrow=TRUE);
colnames(acc.matrix) = as.character(seq(1,10)*100+1)
rownames(acc.matrix) = as.character(c(1,2,4,8,16,32,64,128));

## Based on performance we choose nodesize 32 and 101 trees and test this
## on the test set.
set.seed(42);
wpmed.rfmodel.2000.1 = randomForest(
  x=training.set.2000[, importance_columns, with=FALSE],
  y=training.set.2000$rating,
  xtest = test.set[, importance_columns, with=FALSE],
  ytest = test.set$rating,
  ntree=101,
  nodesize=32);
wpmed.rfmodel.2000.1;

## All three predictors.
importance_columns = c('log_links', 'log_projlinks', 'log_views');
accs = c();
for(nodesize in c(1,2,4,8,16,32,64,128)) {
  for(treesize in seq(1,10)*100+1) {
    accs = append(accs, rf_crossvalidation(training.set.2000, importance_columns,
                                           treesize, nodesize))
  }
}
acc.matrix = matrix(100*accs, ncol=10, byrow=TRUE);
colnames(acc.matrix) = as.character(seq(1,10)*100+1)
rownames(acc.matrix) = as.character(c(1,2,4,8,16,32,64,128));

## Based on performance we choose nodesize 32 and 101 trees and test this
## on the test set.
set.seed(42);
wpmed.rfmodel.2000.2 = randomForest(
  x=training.set.2000[, importance_columns, with=FALSE],
  y=training.set.2000$rating,
  xtest = test.set[, importance_columns, with=FALSE],
  ytest = test.set$rating,
  ntree=301,
  nodesize=16);
wpmed.rfmodel.2000.2;

## SVM classifier

## First we tune it, this is done iteratively through searching.
obj = tune(svm, rating ~ log_links + log_views, data=training.set.1000,
           ranges=list(gamma=seq(8, 12, by=0.5),
                       cost=seq(60, 100, by=10)),
           tunecontrol = tune.control(sampling='fix'));
summary(obj);
plot(obj);

## We use gamma=8, cost=90, as suggested by the tuning result.
imp_svm.1 = svm(rating ~ log_links + log_views, data=training.set.1000,
              cost=90, gamma=8, cross=10);
summary(imp_svm.1);

svm_predictions = predict(object=imp_svm.1,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;
conf_svm = table(test.set$svm_pred, test.set$rating);
confusionMatrix(conf_svm);

## Tune again using internal links
obj = tune(svm, rating ~ log_projlinks + log_views, data=training.set.1000,
           ranges=list(gamma=seq(5, 7, by=0.25),
                       cost=seq(55, 65, by=1)),
           tunecontrol = tune.control(sampling='fix'));
summary(obj);
plot(obj);

## We use gamma=6, cost=60, as suggested by the tuning result.
imp_svm.2 = svm(rating ~ log_projlinks + log_views, data=training.set.1000,
                cost=60, gamma=6, cross=10);
summary(imp_svm.2);

svm_predictions = predict(object=imp_svm.2,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;
conf_svm = table(test.set$svm_pred, test.set$rating);
confusionMatrix(conf_svm);

## Tune again using all three predictors
obj = tune(svm, rating ~ log_links + log_projlinks + log_views, data=training.set.1000,
           ranges=list(gamma=seq(1, 4, by=0.25),
                       cost=seq(1, 25, by=1)),
           tunecontrol = tune.control(sampling='fix'));
summary(obj);
plot(obj);

## We use gamma=1.25, cost=19, as suggested by the tuning result.
imp_svm.3 = svm(rating ~ log_links + log_projlinks + log_views, data=training.set.1000,
                cost=19, gamma=1.25, cross=10);
summary(imp_svm.3);

svm_predictions = predict(object=imp_svm.3,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;
conf_svm = table(test.set$svm_pred, test.set$rating);
confusionMatrix(conf_svm);

## Now we repeat this procedure with the larger training set.
## Tuning of the first model...
obj = tune(svm, rating ~ log_links + log_views, data=training.set.2000,
           ranges=list(gamma=seq(5, 10, by=0.5),
                       cost=seq(10, 20, by=1)),
           tunecontrol = tune.control(sampling='fix'));
summary(obj);
plot(obj);

## We use gamma=8, cost=16, as suggested by the tuning result.
imp_svm.4 = svm(rating ~ log_links + log_views, data=training.set.2000,
                cost=90, gamma=8, cross=10);
summary(imp_svm.4);

svm_predictions = predict(object=imp_svm.4,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;
conf_svm = table(test.set$svm_pred, test.set$rating);
confusionMatrix(conf_svm);

## Tune again using internal links
obj = tune(svm, rating ~ log_projlinks + log_views, data=training.set.2000,
           ranges=list(gamma=seq(6, 10, by=0.25),
                       cost=seq(65, 85, by=1)),
           tunecontrol = tune.control(sampling='fix'));
summary(obj);
plot(obj);

## We use gamma=8.5, cost=82, as suggested by the tuning result.
imp_svm.5 = svm(rating ~ log_projlinks + log_views, data=training.set.2000,
                cost=82, gamma=8.5, cross=10);
summary(imp_svm.5);

svm_predictions = predict(object=imp_svm.5,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;
conf_svm = table(test.set$svm_pred, test.set$rating);
confusionMatrix(conf_svm);

## Tune again using all three predictors
obj = tune(svm, rating ~ log_links + log_projlinks + log_views, data=training.set.2000,
           ranges=list(gamma=seq(0.1, 1.0, by=0.1),
                       cost=seq(5, 15, by=1)),
           tunecontrol = tune.control(sampling='fix'));
summary(obj);
plot(obj);

## We use gamma=0.5, cost=8, as suggested by the tuning result.
imp_svm.6 = svm(rating ~ log_links + log_projlinks + log_views, data=training.set.2000,
                cost=19, gamma=1.25, cross=10);
summary(imp_svm.6);

svm_predictions = predict(object=imp_svm.6,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;
conf_svm = table(test.set$svm_pred, test.set$rating);
confusionMatrix(conf_svm);

## How about that GBM?

## We use cross-validation to identify the best number of trees as
## we reported on in the global classifier training.
## I adjusted the n.trees parameter down from 10,000 to 5,000 because
## in this case we never need that many.
gbm_cvtest = function(f, dataset, nodesizes) {
  n_trees = c();
  min_errors = c();
  for(nsize in nodesizes) {
    imp_gbm.cv = gbm(f,
                     data=dataset,
                     distribution='multinomial',
                     n.trees = 5000,
                     shrinkage = 0.01,
                     n.minobsinnode = nsize,
                     cv.folds = 10,
                     n.cores = 1);
    n_trees = append(n_trees, gbm.perf(imp_gbm.cv));
    min_errors = append(min_errors, min(imp_gbm.cv$cv.error));
  }
  data.frame(nsize=nodesizes, ntrees=n_trees, cv.error=min_errors);  
}

gbm_cvtest(rating ~ log_links + log_views,
           training.set.1000, 2**seq(0,6));
## Using 1 minimum observations in a node we need 1,101 trees,
## with CV deviance 0.847
## Using 2 minimum observations in a node we need 1,086 trees,
## with CV deviance 0.850
## Using 4 minimum observations in a node we need 1,222 trees,
## with CV deviance 0.850
## Using 8 minimum observations in a node we need 1,221 trees,
## with CV deviance 0.846
## Using 16 minimum observations in a node we need 1,134 trees,
## with CV deviance 0.855
## Using 32 minimum observations in a node we need 1,532 trees,
## with CV deviance 0.846
## Using 64 minimum observations in a node we need 1,568 trees,
## with CV deviance 0.857

## We choose 8 minimum observations and 1,221 trees, as that is
## a simpler model than 32/1532, which had the same reported CV error.
imp_gbm.1 = gbm(rating ~ log_links + log_views,
                 data=training.set.1000,
                 distribution='multinomial',
                 n.trees = 1221,
                 shrinkage = 0.01,
                 n.minobsinnode = 8,
                 n.cores = 1);
gbm_predictions = predict(object=imp_gbm.1,
                          newdata=test.set,
                          n.trees = 1221,
                          type='response');
gbm_predictions = apply(gbm_predictions, 1, which.max);
gbm_predictions = sapply(gbm_predictions, function(x) { importance_ratings[x]; });
test.set$gbm_pred = gbm_predictions;
test.set$gbm_pred = ordered(test.set$gbm_pred, importance_ratings);
conf_gbm = table(test.set$gbm_pred, test.set$rating);
confusionMatrix(conf_gbm);

## Run the CV test using project-internal links
gbm_cvtest(rating ~ log_projlinks + log_views,
           training.set.1000, 2**seq(0,6));

## We choose 16 minimum observations and 1,435 trees, which had
## the lowest reported CV error.
imp_gbm.2 = gbm(rating ~ log_projlinks + log_views,
                data=training.set.1000,
                distribution='multinomial',
                n.trees = 1435,
                shrinkage = 0.01,
                n.minobsinnode = 16,
                n.cores = 1);
gbm_predictions = predict(object=imp_gbm.2,
                          newdata=test.set,
                          n.trees = 1435,
                          type='response');
gbm_predictions = apply(gbm_predictions, 1, which.max);
gbm_predictions = sapply(gbm_predictions, function(x) { importance_ratings[x]; });
test.set$gbm_pred = gbm_predictions;
test.set$gbm_pred = ordered(test.set$gbm_pred, importance_ratings);
conf_gbm = table(test.set$gbm_pred, test.set$rating);
confusionMatrix(conf_gbm);

## Run the CV test using both types of links
gbm_cvtest(rating ~ log_links + log_projlinks + log_views,
           training.set.1000, 2**seq(0,6));

## We choose 32 minimum observations and 1,830 trees, which had
## the lowest reported CV error.
imp_gbm.3 = gbm(rating ~ log_links + log_projlinks + log_views,
                data=training.set.1000,
                distribution='multinomial',
                n.trees = 1830,
                shrinkage = 0.01,
                n.minobsinnode = 32,
                n.cores = 1);
gbm_predictions = predict(object=imp_gbm.3,
                          newdata=test.set,
                          n.trees = 1830,
                          type='response');
gbm_predictions = apply(gbm_predictions, 1, which.max);
gbm_predictions = sapply(gbm_predictions, function(x) { importance_ratings[x]; });
test.set$gbm_pred = gbm_predictions;
test.set$gbm_pred = ordered(test.set$gbm_pred, importance_ratings);
conf_gbm = table(test.set$gbm_pred, test.set$rating);
confusionMatrix(conf_gbm);

## Now we do it again on the larger dataset!
## Because of the larger dataset, test up to 256.
gbm_cvtest(rating ~ log_links + log_views,
           training.set.2000, 2**seq(0,8));

## We choose minimum node size of 64 and 2,278 trees.
## We choose 32 minimum observations and 1,830 trees, which had
## the lowest reported CV error.
imp_gbm.4 = gbm(rating ~ log_links + log_views,
                data=training.set.2000,
                distribution='multinomial',
                n.trees = 2278,
                shrinkage = 0.01,
                n.minobsinnode = 64,
                n.cores = 1);
gbm_predictions = predict(object=imp_gbm.4,
                          newdata=test.set,
                          n.trees = 1830,
                          type='response');
gbm_predictions = apply(gbm_predictions, 1, which.max);
gbm_predictions = sapply(gbm_predictions, function(x) { importance_ratings[x]; });
test.set$gbm_pred = gbm_predictions;
test.set$gbm_pred = ordered(test.set$gbm_pred, importance_ratings);
conf_gbm = table(test.set$gbm_pred, test.set$rating);
confusionMatrix(conf_gbm);

## Using project-internal links
gbm_cvtest(rating ~ log_projlinks + log_views,
           training.set.2000, 2**seq(0,8));

## We choose 4 minimum observations and 2,486 trees, which had
## the lowest reported CV error.
imp_gbm.5 = gbm(rating ~ log_links + log_views,
                data=training.set.2000,
                distribution='multinomial',
                n.trees = 2486,
                shrinkage = 0.01,
                n.minobsinnode = 4,
                n.cores = 1);
gbm_predictions = predict(object=imp_gbm.5,
                          newdata=test.set,
                          n.trees = 2486,
                          type='response');
gbm_predictions = apply(gbm_predictions, 1, which.max);
gbm_predictions = sapply(gbm_predictions, function(x) { importance_ratings[x]; });
test.set$gbm_pred = gbm_predictions;
test.set$gbm_pred = ordered(test.set$gbm_pred, importance_ratings);
conf_gbm = table(test.set$gbm_pred, test.set$rating);
confusionMatrix(conf_gbm);

## Lastly all three predictors
gbm_cvtest(rating ~ log_links + log_projlinks + log_views,
           training.set.2000, 2**seq(0,8));

## We choose 32 minimum observations and 2,497 trees, which had
## the lowest reported CV error.
imp_gbm.6 = gbm(rating ~ log_links + log_views,
                data=training.set.2000,
                distribution='multinomial',
                n.trees = 2497,
                shrinkage = 0.01,
                n.minobsinnode = 32,
                n.cores = 1);
gbm_predictions = predict(object=imp_gbm.6,
                          newdata=test.set,
                          n.trees = 2497,
                          type='response');
gbm_predictions = apply(gbm_predictions, 1, which.max);
gbm_predictions = sapply(gbm_predictions, function(x) { importance_ratings[x]; });
test.set$gbm_pred = gbm_predictions;
test.set$gbm_pred = ordered(test.set$gbm_pred, importance_ratings);
conf_gbm = table(test.set$gbm_pred, test.set$rating);
confusionMatrix(conf_gbm);

## Let's inspect some of the incorrectly predicted articles by the SVM
## with the highest performance.

svm_predictions = predict(object=imp_svm.3,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;
conf_svm = table(test.set$svm_pred, test.set$rating);
confusionMatrix(conf_svm);

test.set[rating == 'Low' & svm_pred == 'High'];
test.set[rating == 'Low' & svm_pred == 'Top'];

test.set[rating == 'Mid' & svm_pred == 'Top'];

test.set[rating == 'High' & svm_pred == 'Low'];

test.set[rating == 'Top' & svm_pred == 'Mid'];
test.set[rating == 'Top' & svm_pred == 'Low'];

## I think we should also predict ratings for all articles in the dataset.
## I'm curious to learn more about Top/Low misclassifications, and I'm sure
## the project members will ask about it if we don't.
svm_predictions = predict(object=imp_svm.3,
                          newdata=wpmed);
wpmed$svm_pred = svm_predictions;
conf_svm = table(wpmed$svm_pred, wpmed$rating);
confusionMatrix(conf_svm);

# We have 2 Top-importance articles predicted to be Mid- or Low-importance.
## We have 78 High-importance articles predicted to be Low-importance.
## We have 325 Mid-importance articles predicted to be Top-importance.
## We have 70 Low-importance articles predicted to be Top-importance.
## We have 1,339 Low-importance articles predicted to be High-importance.

wpmed[rating == "Top" & svm_pred == "Low"];
wpmed[rating == "Top" & svm_pred == "Mid"];

wpmed[rating == "High" & svm_pred == "Low"];

make_wiki_list = function(dataset, true_rating, pred_rating) {
  ## Make a UL of all titles in the dataset where their
  ## true and predicted rating are as given.
  output_str = c("<ul>");
  titles = sort(gsub('_', ' ', dataset[rating == true_rating & svm_pred == pred_rating]$talk_page_title));
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

cat(make_wiki_list(wpmed, "Low", "High"));
cat(make_wiki_list(wpmed, "Low", "Top"));
