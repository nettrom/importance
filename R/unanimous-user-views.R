## Let's see if filtering views to just "user" has more signal.

setkey(unanimous_userviews, page_id);
unanimous_userviews = unanimous_dataset[unanimous_userviews];

unanimous_userviews$log_t28avg = log10(1 + unanimous_userviews$third28_avg);

## Split the data into a training and test set for simplicity
training.set = unanimous_userviews[is_training == 1];
test.set = unanimous_userviews[is_training == 0];

importance_columns = c('log_inlinks', 'log_t28avg');
importance_ratings = c('Top', 'High', 'Mid', 'Low');

n_folds = 10
training.set[, fold := seq(1, .N) %% n_folds];

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
imp_rfmodel.user = randomForest(x=training.set[, importance_columns, with=FALSE],
                             y=training.set$rating,
                             xtest=test.set[, importance_columns, with=FALSE],
                             ytest=test.set$rating,
                             ntree = 1001,
                             nodesize=512);
imp_rfmodel.user;

## Fascinating… this has lower prediction ability than using "all-agents"