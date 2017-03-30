## Adding information from the clickstream dataset to the unanimous dataset
## and seeing how that affects our predictions.

library(data.table);
library(randomForest);
library(e1071);
library(gbm);
library(caret);

setkey(unanimous_clickstream, title);
setkey(unanimous_dataset, talk_page_title);

unanimous_clickstream = unanimous_dataset[unanimous_clickstream]

## Split the data into a training and test set for simplicity
training.set = unanimous_clickstream[is_training == 1];
test.set = unanimous_clickstream[is_training == 0];

importance_columns = c('log_inlinks', 'log_views');
importance_ratings = c('Top', 'High', 'Mid', 'Low');

n_folds = 10
training.set[, fold := seq(1, .N) %% n_folds];

rf_crossvalidation = function(tset, pred_columns, ntrees, nodesize) {
  ## Run 10-fold cross-validation using a Random Forest classifier
  ## and return the overall accuracy.  Note that classes must be balanced
  ## for overall accuracy to be a useful measure of performance.
  
  n_folds = 10;
  tset[, fold := seq(1, .N) %% n_folds];
  set.seed(NULL); # resets the RNG
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

## We'll first run some 10-fold cross-validation on the
## dataset with a Random Forest classifier just using links & views
## to tune the nodesize and treesize parameters.
importance_columns = c('log_inlinks', 'log_views');
accs = c();
for(nodesize in 2**c(0:10)) {
  for(treesize in seq(1,10)*100+1) {
    accs = append(accs, rf_crossvalidation(training.set, importance_columns,
                                           treesize, nodesize))
    print(paste('completed treesize', treesize, 'nodesize', nodesize));
  }
}
acc.matrix = matrix(100*accs, ncol=10, byrow=TRUE);
colnames(acc.matrix) = as.character(seq(1,10)*100+1)
rownames(acc.matrix) = as.character(2**c(0:10));
max(acc.matrix);

## So, nodesize 512, treesize 701 is our benchmark.
set.seed(42);
importance_columns = c('log_inlinks', 'log_views');
clickstream.benchmark = randomForest(
  x=training.set[, importance_columns, with=FALSE],
  y=training.set$rating,
  xtest = test.set[, importance_columns, with=FALSE],
  ytest = test.set$rating,
  ntree=701,
  nodesize=512);
clickstream.benchmark;

## Let's add the proportion of views metric.
training.set[, prop_from_art := n_from_art / n_views];
test.set[, prop_from_art := n_from_art / n_views];

## Some articles have n_views == -1 and n_from_art == -1, set those
## to 0 and prop_from_art to 0.
training.set[n_from_art == -1, prop_from_art := 0];
test.set[n_from_art == -1, prop_from_art := 0];
training.set[n_views == -1, n_views := 0];
test.set[n_views == -1, n_views := 0];
training.set[n_from_art == -1, n_from_art := 0];
test.set[n_from_art == -1, n_from_art := 0];

importance_columns = c('log_inlinks', 'log_views', 'prop_from_art');
accs = c();
for(nodesize in 2**c(0:10)) {
  for(treesize in seq(1,10)*100+1) {
    accs = append(accs, rf_crossvalidation(training.set, importance_columns,
                                           treesize, nodesize))
    print(paste('completed treesize', treesize, 'nodesize', nodesize));
  }
}
acc.matrix = matrix(100*accs, ncol=10, byrow=TRUE);
colnames(acc.matrix) = as.character(seq(1,10)*100+1);
rownames(acc.matrix) = as.character(2**c(0:10));
max(acc.matrix);

## So, nodesize 32, treesize 701 is our choice.
set.seed(42);
importance_columns = c('log_inlinks', 'log_views', 'prop_from_art');
clickstream.1 = randomForest(
  x=training.set[, importance_columns, with=FALSE],
  y=training.set$rating,
  xtest = test.set[, importance_columns, with=FALSE],
  ytest = test.set$rating,
  ntree=601,
  nodesize=1);
clickstream.1;

## Let's add the proportion of inlinks.
training.set[, prop_act_inlinks := n_act_links / num_inlinks];
training.set[num_inlinks == 0, prop_act_inlinks := 0];
test.set[, prop_act_inlinks := n_act_links / num_inlinks];
test.set[num_inlinks == 0, prop_act_inlinks := 0];

## Add the proportion of active inlinks variable
importance_columns = c('log_inlinks', 'log_views', 'prop_act_inlinks');
accs = c();
for(nodesize in 2**c(0:10)) {
  for(treesize in seq(1,10)*100+1) {
    accs = append(accs, rf_crossvalidation(training.set, importance_columns,
                                           treesize, nodesize))
    print(paste('completed treesize', treesize, 'nodesize', nodesize));
  }
}
acc.matrix = matrix(100*accs, ncol=10, byrow=TRUE);
colnames(acc.matrix) = as.character(seq(1,10)*100+1)
rownames(acc.matrix) = as.character(2**c(0:10));
max(acc.matrix);

## So, nodesize 256, treesize 101 is our choice
set.seed(42);
importance_columns = c('log_inlinks', 'log_views', 'prop_act_inlinks');
clickstream.2 = randomForest(
  x=training.set[, importance_columns, with=FALSE],
  y=training.set$rating,
  xtest = test.set[, importance_columns, with=FALSE],
  ytest = test.set$rating,
  ntree=101,
  nodesize=256);
clickstream.2;

## Lastly test with both new variables
importance_columns = c('log_inlinks', 'log_views',
                       'prop_from_art', 'prop_act_inlinks');
accs = c();
for(nodesize in 2**c(0:10)) {
  for(treesize in seq(1,10)*100+1) {
    accs = append(accs, rf_crossvalidation(training.set, importance_columns,
                                           treesize, nodesize))
    print(paste('completed treesize', treesize, 'nodesize', nodesize));
  }
}
acc.matrix = matrix(100*accs, ncol=10, byrow=TRUE);
colnames(acc.matrix) = as.character(seq(1,10)*100+1)
rownames(acc.matrix) = as.character(2**c(0:10));
max(acc.matrix);

## So, nodesize 128, treesize 901 is our choice
set.seed(42);
importance_columns = c('log_inlinks', 'log_views',
                       'prop_from_art', 'prop_act_inlinks');
clickstream.3 = randomForest(
  x=training.set[, importance_columns, with=FALSE],
  y=training.set$rating,
  xtest = test.set[, importance_columns, with=FALSE],
  ytest = test.set$rating,
  ntree=901,
  nodesize=128);
clickstream.3;

## Hmm, combining them don't add much. Are they typically correlated?
cor(training.set$prop_act_inlinks, training.set$prop_from_art);
## No, not really (r=0.25)

## OK, let's try the SVM instead.

## Our previous run suggests gamma=1.4, cost=16, but I want to verify that.
obj = tune(svm, rating ~ log_inlinks + log_views, data=training.set,
           ranges=list(gamma=seq(0.5, 1.5, by=0.1),
                       cost=seq(95, 115, by=1)),
           tunecontrol = tune.control(sampling='fix'));
plot(obj);
summary(obj);

## We find that gamma=1, cost=108 has good performance (basically any cost
## with gamma=1 seems to perform well)
clickstream.svm.benchmark = svm(rating ~ log_inlinks + log_views,
                               data=training.set,
                               cost=108, gamma=1, cross=10);
summary(clickstream.svm.benchmark);
svm_predictions = predict(object=clickstream.svm.benchmark,
                          newdata=test.set);
test.set$svm_pred = ordered(svm_predictions, importance_ratings);
confusionMatrix(table(test.set$rating, test.set$svm_pred));

## Add prop_from_art and tune that.
obj = tune(svm, rating ~ log_inlinks + log_views + prop_from_art,
           data=training.set,
           ranges=list(gamma=seq(0.1, 1.0, by=0.1),
                       cost=seq(40, 50, by=1)),
           tunecontrol = tune.control(sampling='fix'));
plot(obj);
summary(obj);

clickstream.svm.1 = svm(rating ~ log_inlinks + log_views + prop_from_art,
                        data=training.set,
                        cost=108, gamma=1, cross=10);
summary(clickstream.svm.1);
svm_predictions = predict(object=clickstream.svm.1,
                          newdata=test.set);
test.set$svm_pred = ordered(svm_predictions, importance_ratings);
confusionMatrix(table(test.set$rating, test.set$svm_pred));

## This is actually _less_ accurate than using just the two variables.
## Hmm…

## Add prop_act_inlinks and tune that.
obj = tune(svm, rating ~ log_inlinks + log_views + prop_act_inlinks,
           data=training.set,
           ranges=list(gamma=seq(4.0, 5.0, by=0.1),
                       cost=seq(10, 20, by=1)),
           tunecontrol = tune.control(sampling='fix'));
plot(obj);
summary(obj);

clickstream.svm.2 = svm(rating ~ log_inlinks + log_views + prop_act_inlinks,
                        data=training.set,
                        cost=17, gamma=4.5, cross=10);
summary(clickstream.svm.2);
svm_predictions = predict(object=clickstream.svm.2,
                          newdata=test.set);
test.set$svm_pred = ordered(svm_predictions, importance_ratings);
confusionMatrix(table(test.set$rating, test.set$svm_pred));

## Yeah, this is even less accurate. Strange?

## Add prop_from_art and tune that.
obj = tune(svm, rating ~ log_inlinks + log_views + prop_act_inlinks + prop_from_art,
           data=training.set,
           ranges=list(gamma=seq(0.1, 1.0, by=0.1),
                       cost=seq(50, 60, by=1)),
           tunecontrol = tune.control(sampling='fix'));
plot(obj);
summary(obj);

clickstream.svm.3 = svm(rating ~ log_inlinks + log_views + prop_act_inlinks + prop_from_art,
                        data=training.set,
                        cost=60, gamma=0.1, cross=10);
summary(clickstream.svm.3);
svm_predictions = predict(object=clickstream.svm.3,
                          newdata=test.set);
test.set$svm_pred = ordered(svm_predictions, importance_ratings);
confusionMatrix(table(test.set$rating, test.set$svm_pred));

## Fantastic! By themselves these don't really seem to provide any benefit,
## but put them together and you get +1% accuracy.

training.set$rating = ordered(training.set$rating, importance_ratings);

## Let's train a GBM for reference and one with all variables.
## Cross-validation fails (GBM's algorithm for sampling in CV
## is buggy, leads to "subscript out of bounds" errors)
imp_gbm = gbm(rating ~ log_inlinks + log_views,
              data=training.set,
              distribution='multinomial',
              n.trees = 2500,
              shrinkage = 0.01,
              n.minobsinnode = 8,
              n.cores = 4);
gbm.perf(imp_gbm);
gbm_predictions = predict(object=imp_gbm,
                          newdata=test.set,
                          n.trees = 299,
                          type='response');
gbm_predictions = apply(gbm_predictions, 1, which.max);
gbm_predictions = sapply(gbm_predictions, function(x) { importance_ratings[x]; });
test.set$gbm_pred = gbm_predictions;
test.set$gbm_pred = ordered(test.set$gbm_pred, importance_ratings);

confusionMatrix(table(test.set$rating, test.set$gbm_pred));

gbm_crossvalidation = function(tset, f, ntrees, nodesize) {
  ## Run 10-fold cross-validation using a GBM classifier
  ## and return the overall accuracy.  Note that classes must be balanced
  ## for overall accuracy to be a useful measure of performance.
  n_folds = 10;
  tset[, fold := seq(1, .N) %% n_folds];
  set.seed(NULL);
  for(i in 0:(n_folds-1)) {
    cur_fold = i;
    imp_gbm = gbm(f,
                  data=tset[fold != cur_fold],
                  distribution='multinomial',
                  n.trees = ntrees,
                  shrinkage = 0.01,
                  n.minobsinnode = nodesize,
                  n.cores = 1)
    pred_trees = gbm.perf(imp_gbm);
    gbm_predictions = predict(object=imp_gbm,
                              newdata=training.set[fold == cur_fold],
                              n.trees = pred_trees,
                              type='response');
    gbm_predictions = apply(gbm_predictions, 1, which.max);
    gbm_predictions = sapply(gbm_predictions, function(x) { importance_ratings[x]; });
    tset[fold == cur_fold, pred := gbm_predictions];
  }
  tset[, pred := ordered(pred, importance_ratings)];
  length(tset[pred == rating]$rating)/length(tset$rating);
}

## For the model with views & inlinks:
for(n in 2**c(0:10)) {
  x = gbm_crossvalidation(training.set, rating ~ log_inlinks + log_views,
                          5000, n);
  print(paste("min node size", n, "has accuracy", x));
  gc();
}
## "min node size 1 has accuracy 0.468333333333333"
## "min node size 2 has accuracy 0.467666666666667"
## "min node size 4 has accuracy 0.469166666666667"
## "min node size 8 has accuracy 0.4695"
## "min node size 16 has accuracy 0.467166666666667"
## "min node size 32 has accuracy 0.467166666666667"
## "min node size 64 has accuracy 0.4675"
## "min node size 128 has accuracy 0.467166666666667"
## "min node size 256 has accuracy 0.463166666666667"
## "min node size 512 has accuracy 0.4675"
## "min node size 1024 has accuracy 0.452166666666667"

## Node size 8 it is! I'll copy that back into our code further up.

## For the model with all four variables:
for(n in 2**c(9:10)) {
  x = gbm_crossvalidation(training.set,
                          rating ~ log_inlinks + log_views + prop_act_inlinks + prop_from_art,
                          5000, n);
  print(paste("min node size", n, "has accuracy", x));
  gc();
}

## "min node size 1 has accuracy 0.467666666666667"
## "min node size 2 has accuracy 0.464166666666667"
## "min node size 4 has accuracy 0.465166666666667"
## "min node size 8 has accuracy 0.465666666666667"
## "min node size 16 has accuracy 0.464666666666667"
## "min node size 32 has accuracy 0.465333333333333"
## "min node size 64 has accuracy 0.465833333333333"
## "min node size 128 has accuracy 0.465"
## "min node size 256 has accuracy 0.4635"
## "min node size 512 has accuracy 0.463833333333333"
## "min node size 1024 has accuracy 0.453333333333333"

## We'll use node size 64.
imp_gbm = gbm(rating ~ log_inlinks + log_views + prop_act_inlinks + prop_from_art,
              data=training.set,
              distribution='multinomial',
              n.trees = 2500,
              shrinkage = 0.01,
              n.minobsinnode = 64,
              n.cores = 4);
gbm.perf(imp_gbm);
gbm_predictions = predict(object=imp_gbm,
                          newdata=test.set,
                          n.trees = 417,
                          type='response');
gbm_predictions = apply(gbm_predictions, 1, which.max);
gbm_predictions = sapply(gbm_predictions, function(x) { importance_ratings[x]; });
test.set$gbm_pred = gbm_predictions;
test.set$gbm_pred = ordered(test.set$gbm_pred, importance_ratings);

confusionMatrix(table(test.set$rating, test.set$gbm_pred));

## Generate some plots
library(ggplot2);
res = data.frame(model=c('Benchmark', 'Prop views', 'Prop links', 'Both'),
                 acc=c(50.38, 49.38, 48.69, 51.44));
positions = c('Benchmark', 'Prop views', 'Prop links', 'Both');

ggplot(res, aes(x=model, y=acc)) + geom_bar(stat="identity") +
  labs(y='Overall accuracy in %') + ggtitle('Performance of clickstream models') +
  scale_x_discrete(limits = positions);


