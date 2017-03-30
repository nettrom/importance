## Adding information from the clickstream dataset to our models to see how
## that affects performance in the WPMED context. Note that in this case we
## have both global and project-specific measurements of incoming traffic
## from other articles.

library(randomForest);
library(e1071);
library(gbm);
library(caret);
library(smotefamily);

setkey(wpmed_clickstream, title);
setkey(wpmed, talk_page_title);

## In these datasets we overload "n_views", so make a new column called
## n_clicks in the clickstream dataset and delete the old column.
wpmed_clickstream[, n_clicks := n_views];
wpmed_clickstream[, n_views := NULL];

wpmed_clickstream = wpmed[wpmed_clickstream];

## Cleaning up the dataset and calculating all proportions.
wpmed_clickstream[talk_is_archive == 0 & art_is_redirect == 0 & n_inlinks == -1,
      n_inlinks := 0];
wpmed_clickstream[talk_is_archive == 0 & art_is_redirect == 0 & n_proj_inlinks == -1,
      n_proj_inlinks := 0];

wpmed_clickstream = wpmed_clickstream[talk_is_archive == 0];
wpmed_clickstream = wpmed_clickstream[art_is_redirect == 0];

## Take out articles that are disambiguation pages
wpmed_clickstream = wpmed_clickstream[!(talk_page_id %in% wpmed_disambig$page_id)]

## Correct the rating of the 129 articles about individuals that we've rerated
wpmed_clickstream[talk_page_title %in% wpmed_individuals$page_title,
                  rating := 'Low'];

wpmed_clickstream[n_from_art == -1, n_from_art := 0];
wpmed_clickstream[n_from_proj == -1, n_from_proj := 0];

wpmed_clickstream[, prop_from_art := n_from_art / n_clicks];
wpmed_clickstream[, prop_from_proj := n_from_proj / n_clicks];
wpmed_clickstream[, prop_act_inlinks := n_act_links / n_inlinks];
wpmed_clickstream[, prop_proj_inlinks := n_proj_act / n_inlinks];

wpmed_clickstream[is.na(prop_act_inlinks), prop_act_inlinks := 0];
wpmed_clickstream[is.na(prop_proj_inlinks), prop_proj_inlinks := 0];

## If the proportion of active inlinks is > 1, then we instead just use
## that number of active inlinks as our number of inlinks, thus setting it to 1.
wpmed_clickstream[prop_act_inlinks > 1, prop_act_inlinks := 1];
wpmed_clickstream[prop_proj_inlinks > 1, prop_proj_inlinks := 1];

## Create a randomly selected test set of 160 articles, similary as we
## did before (unfortunately our exact selection of articles is lost)
wpmed_clickstream[, is_training := 1];
wpmed_clickstream[talk_page_id %in% wpmed_clickstream[
  , .SD[sample(.N, 40)], by='rating']$talk_page_id, is_training := 0];

## Splitting it up into a training and test set.
wpmed_clickstream.test.set = wpmed_clickstream[is_training == 0];
wpmed_clickstream.training.set = wpmed_clickstream[is_training == 1];

## We are generating synthetic examples for Top-importance, so we add a binary
## column for identifying those.
wpmed_clickstream.training.set[, is_top := 0];
wpmed_clickstream.training.set[rating == 'Top', is_top := 1];

## We found the dataset with 200 synthetic samples to perform best, so we'll
## only generate that this time around and ignore the larger one.
training_data.250 = rbind(
  wpmed_clickstream.training.set[is_top == 0][sample(.N, 250)],
  wpmed_clickstream.training.set[is_top == 1])[, list(art_page_id, log_links,
                                    n_local_dampened, log_views, prop_from_art,
                                    prop_from_proj, prop_act_inlinks,
                                    prop_proj_inlinks, is_top)];
synth_data.250 = SMOTE(training_data.250[,
    list(log_links, log_views, n_local_dampened, prop_from_art, prop_from_proj,
         prop_act_inlinks, prop_proj_inlinks)], training_data.250$is_top);

training.set.1000 = rbind(synth_data.250$data[class == 1][,
    list(log_links, log_views, n_local_dampened, prop_from_art, prop_from_proj,
         prop_act_inlinks, prop_proj_inlinks, class, rating='Top')],
                          wpmed_clickstream.training.set[rating == 'High'][sample(.N, 250)][,
    list(log_links, log_views, n_local_dampened, prop_from_art, prop_from_proj,
         prop_act_inlinks, prop_proj_inlinks, rating, class=0)],
                          wpmed_clickstream.training.set[rating == 'Mid'][sample(.N, 250)][,
    list(log_links, log_views, n_local_dampened, prop_from_art, prop_from_proj,
         prop_act_inlinks, prop_proj_inlinks, rating, class=0)],
                          wpmed_clickstream.training.set[rating == 'Low'][sample(.N, 250)][,
    list(log_links, log_views, n_local_dampened, prop_from_art, prop_from_proj,
         prop_act_inlinks, prop_proj_inlinks, rating, class=0)]
);

## The benchmark is the SVM classifier from wpmed-kamps.R, using local_dampened
obj = tune(svm, rating ~ log_links + log_views + n_local_dampened,
           data=training.set.1000,
           ranges=list(gamma=seq(2.0, 3.0, by=0.1),
                       cost=seq(65, 85, by=1)),
           tunecontrol = tune.control(sampling='fix'));
plot(obj);
summary(obj);

## We use gamma=2.1, cost=67, as suggested by the tuning result.
wpmed.svm.benchmark = svm(rating ~ log_links + log_views + n_local_dampened,
                    data=training.set.1000,
                    gamma=2.1, cost=67, cross=10);
summary(wpmed.svm.benchmark);

svm_predictions = predict(object=wpmed.svm.benchmark,
                          newdata=wpmed_clickstream.test.set);
wpmed_clickstream.test.set$svm_pred = svm_predictions;
confusionMatrix(table(wpmed_clickstream.test.set$rating,
                      wpmed_clickstream.test.set$svm_pred));

## Work on the global classifier suggested adding both variables at the same
## time was the only way to improve performance, so lets do that.
obj = tune(svm, rating ~ log_links + log_views + n_local_dampened
           + prop_from_art + prop_act_inlinks,
           data=training.set.1000,
           ranges=list(gamma=seq(0.01, 0.1, by=0.01),
                       cost=seq(1, 10, by=1)),
           tunecontrol = tune.control(sampling='fix'));
plot(obj);
summary(obj);

## We use gamma=0.04 and cost=1 as suggested by the tuning.
wpmed.svm.click1 = svm(rating ~ log_links + log_views + n_local_dampened
                       + prop_from_art + prop_act_inlinks,
                          data=training.set.1000,
                          gamma=0.04, cost=1, cross=10);
summary(wpmed.svm.click1);

svm_predictions = predict(object=wpmed.svm.click1,
                          newdata=wpmed_clickstream.test.set);
wpmed_clickstream.test.set$click_pred = svm_predictions;
confusionMatrix(table(wpmed_clickstream.test.set$rating,
                      wpmed_clickstream.test.set$click_pred));

## Now, let's test the various combinations of the two new project-specific
## proportions. We take the global ones out first and all prop_from_proj
obj = tune(svm, rating ~ log_links + log_views + n_local_dampened
           + prop_from_proj,
           data=training.set.1000,
           ranges=list(gamma=seq(0.1, 1.0, by=0.1),
                       cost=seq(1, 10, by=1)),
           tunecontrol = tune.control(sampling='fix'));
plot(obj);
summary(obj);

## We use gamma=0.3 and cost=7 as suggested by the tuning.
wpmed.svm.click2 = svm(rating ~ log_links + log_views + n_local_dampened
                       + prop_from_proj,
                       data=training.set.1000,
                       gamma=0.3, cost=7, cross=10);
summary(wpmed.svm.click2);

svm_predictions = predict(object=wpmed.svm.click2,
                          newdata=wpmed_clickstream.test.set);
wpmed_clickstream.test.set$click_pred = svm_predictions;
confusionMatrix(table(wpmed_clickstream.test.set$rating,
                      wpmed_clickstream.test.set$click_pred));

## This seems similar to the global model, that adding just one variable
## makes little to no difference in the predictions.
obj = tune(svm, rating ~ log_links + log_views + n_local_dampened
           + prop_proj_inlinks,
           data=training.set.1000,
           ranges=list(gamma=seq(0.1, 1.0, by=0.1),
                       cost=seq(5, 20, by=1)),
           tunecontrol = tune.control(sampling='fix'));
plot(obj);
summary(obj);

## We use gamma=0.3 and cost=12 as suggested by the tuning.
wpmed.svm.click3 = svm(rating ~ log_links + log_views + n_local_dampened
                       + prop_proj_inlinks,
                       data=training.set.1000,
                       gamma=0.3, cost=12, cross=10);
summary(wpmed.svm.click3);

svm_predictions = predict(object=wpmed.svm.click3,
                          newdata=wpmed_clickstream.test.set);
wpmed_clickstream.test.set$click_pred = svm_predictions;
confusionMatrix(table(wpmed_clickstream.test.set$rating,
                      wpmed_clickstream.test.set$click_pred));

## Yes, it continues to follow the global classifier in that it performs
## roughly similar as without the variable. So, we add both of them…
obj = tune(svm, rating ~ log_links + log_views + n_local_dampened
           + prop_from_proj + prop_proj_inlinks,
           data=training.set.1000,
           ranges=list(gamma=seq(0.1, 1.0, by=0.1),
                       cost=seq(0.1, 1.5, by=0.1)),
           tunecontrol = tune.control(sampling='fix'));
plot(obj);
summary(obj);

## We use gamma=0.2, cost=0.8 as suggested by the tuning.
wpmed.svm.click4 = svm(rating ~ log_links + log_views + n_local_dampened
                       + prop_from_proj + prop_proj_inlinks,
                       data=training.set.1000,
                       gamma=0.3, cost=12, cross=10);
summary(wpmed.svm.click4);

svm_predictions = predict(object=wpmed.svm.click4,
                          newdata=wpmed_clickstream.test.set);
wpmed_clickstream.test.set$click_pred = svm_predictions;
confusionMatrix(table(wpmed_clickstream.test.set$rating,
                      wpmed_clickstream.test.set$click_pred));

## This is actually poorer than not using these!
## What happens if we add all the proportional variables?
obj = tune(svm, rating ~ log_links + log_views + n_local_dampened
           + prop_from_art + prop_act_inlinks
           + prop_from_proj + prop_proj_inlinks,
           data=training.set.1000,
           ranges=list(gamma=seq(0.1, 0.4, by=0.01),
                       cost=seq(1, 20, by=1)),
           tunecontrol = tune.control(sampling='fix'));
plot(obj);
summary(obj);

## We use gamma=0.2, cost=2 as suggested by the tuning.
wpmed.svm.click5 = svm(rating ~ log_links + log_views + n_local_dampened
                       + prop_from_art + prop_act_inlinks
                       + prop_from_proj + prop_proj_inlinks,
                       data=training.set.1000,
                       gamma=0.2, cost=2, cross=10);
summary(wpmed.svm.click5);

svm_predictions = predict(object=wpmed.svm.click5,
                          newdata=wpmed_clickstream.test.set);
wpmed_clickstream.test.set$click_pred = svm_predictions;
confusionMatrix(table(wpmed_clickstream.test.set$rating,
                      wpmed_clickstream.test.set$click_pred));

## Conclusion: nope, doesn't add anything useful at this stage.

library(ggplot2);
res = data.frame(model=c('Benchmark', 'Global', 'Global+Proj'),
                 acc=c(55.62, 68.12, 63.75));
positions = c('Benchmark', 'Global', 'Global+Proj');

ggplot(res, aes(x=model, y=acc)) + geom_bar(stat="identity") +
  labs(y='Overall accuracy in %') + ggtitle('Performance of WPMED clickstream models') +
  scale_x_discrete(limits = positions);

