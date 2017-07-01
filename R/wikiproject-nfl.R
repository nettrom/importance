## Data analysis and model building for WikiProject National Football League

## Note: the shared code loads all necessary libraries.
source('R/wikiproject-shared.R');

importance_ratings = c('Top', 'High', 'Mid', 'Low');

data_dir = 'datasets/wikiproject-nfl';
config_file = 'nfl-config.yaml';

## Read in the YAML configuration file.
proj_conf = yaml.load_file(data_path(config_file));

## Read in the project's data
proj_full = load_data(proj_conf)

## Check joins
proj_full[is.na(importance_rating)];
proj_full[is.na(n_from_art)];
proj_full[n_from_art == -1];

## Decide on how to split it into test & training datasets. First,
## number of articles per rating:
proj_full[, list(n_articles=sum(.N)), by=importance_rating];

## We have 366 Top-importance articles. Use 50 for a test set, 300 for training.
## Seek 450 samples in the training set with synthetic samples, because we're
## limited by the 516 High-importance articles.
n_samples_test = 50;
n_samples_training = 230;
n_samples_SMOTE = n_samples_training *2;
smote_rating = 'Top'; # rating we generate synthetic samples for

## We need a binary category for SMOTE, and it's used both in the
## training set and a sample, so it needs to be added here.
proj_full[, smote_cat := 0];
proj_full[importance_rating == smote_rating, smote_cat := 1];

## Label the test and training sets
proj_full[, is_training := 0];
proj_full[, is_test := 0];
proj_full[talk_page_id %in%
            proj_full[, .SD[sample(.N, n_samples_test)],
                      by='importance_rating']$talk_page_id, is_test := 1];
proj_full[talk_page_id %in% proj_full[!(talk_page_id %in% proj_full[is_test == 1]$talk_page_id),
                                      .SD[sample(.N, n_samples_training)],
                                      by='importance_rating']$talk_page_id, is_training := 1];
## Check that we got the right numbers
length(proj_full[is_test == 1]$talk_page_id) == n_samples_test * length(importance_ratings)
length(proj_full[is_training == 1]$talk_page_id) == n_samples_training * length(importance_ratings)

## Use SMOTE to create synthetic samples
## 1: Grab all the articles in the target category from the training set,
##    and also the right number of random samples (that are not in the test set)
proj_synth_base = rbind(
  proj_full[smote_cat == 1 & is_training == 1],
  proj_full[smote_cat == 0 & is_test == 0][
    sample(.N, n_samples_SMOTE)])[,
                                  list(art_page_id, prop_proj_inlinks, prop_from_art,
                                       prop_act_inlinks, rank_views_perc, rank_links_perc, smote_cat)];

## Generate synthetic samples
proj_synth_data = SMOTE(proj_synth_base[,
                                        list(prop_proj_inlinks, prop_from_art, prop_act_inlinks,
                                             rank_views_perc, rank_links_perc)],
                        proj_synth_base$smote_cat,
                        dup_size=1.5);

proj_training_set = rbind(
  proj_synth_data$data[class == 1][,
                                   list(prop_proj_inlinks, prop_from_art, prop_act_inlinks,
                                        rank_views_perc, rank_links_perc, class, importance_rating=smote_rating)],
  do.call(rbind, lapply(setdiff(importance_ratings, smote_rating),
                        function(x) {
                          proj_full[importance_rating == x[[1]] & is_test == 0][
                            sample(.N, n_samples_SMOTE)][,
                                                         list(prop_proj_inlinks, prop_from_art, prop_act_inlinks,
                                                              rank_views_perc, rank_links_perc, class=0, importance_rating=x)]
                        }))
);
proj_training_set[, importance_rating := ordered(importance_rating, importance_ratings)]

## Verify number of articles in each class
proj_training_set[, list(n_articles=sum(.N)), by=importance_rating]

## Train model
importance_relation = importance_rating ~ rank_views_perc + rank_links_perc +
  prop_proj_inlinks + prop_from_art + prop_act_inlinks;
nodesizes = 2**c(1:8);
cv_accuracy = crossvalidate_gbm(importance_relation,
                                proj_training_set, nodesizes, 7500);

## We chose min. nodesize of 8, as it has the lowest deviance
proj_gbm = gbm(importance_relation,
               data=proj_training_set,
               distribution='multinomial',
               n.trees = 5000,
               shrinkage = 0.01,
               n.minobsinnode = 8,
               n.cores = 2,
               cv.folds = 10);
n_trees = gbm.perf(proj_gbm);

## Test model
proj_test_set = proj_full[is_test == 1];
proj_test_set$gbm_pred = sapply(
  apply(
    predict(object=proj_gbm, newdata=proj_test_set,
            n.trees = n_trees, type='response'),
    1, which.max),
  function(x) { importance_ratings[x]; });
proj_test_set[, gbm_pred := ordered(proj_test_set$gbm_pred, importance_ratings)];
cf = confusionMatrix(table(proj_test_set$importance_rating,
                           proj_test_set$gbm_pred));
cf;

## Plotting the variables for reference
ggplot(proj_training_set,
       aes(x=100*rank_views_perc, y=100*rank_links_perc)) +
  geom_point(aes(colour=importance_rating)) + facet_grid(. ~ importance_rating) +
  xlab('Percentile of daily average views') + ylab('Percentile of inlinks');

ggplot(proj_test_set,
       aes(x=100*rank_views_perc, y=100*rank_links_perc)) +
  geom_point(aes(colour=importance_rating)) + facet_grid(. ~ importance_rating) +
  xlab('Percentile of daily average views') + ylab('Percentile of inlinks');

## If model is okay, building training set on full dataset!

## Let's have a look again at the number of articles per importance rating
proj_full[, list(n_articles=sum(.N)), by=importance_rating];

## 1: Select new sample sizes, almost full dataset
n_samples_training = 250;
n_samples_SMOTE = n_samples_training *2;
proj_full[, is_training := 0];
proj_full[talk_page_id %in%
            proj_full[, .SD[sample(.N, n_samples_training)],
                      by='importance_rating']$talk_page_id, is_training := 1];

## Create new dataset as a basis for synthetic samples
proj_synth_base = rbind(
  proj_full[smote_cat == 1 & is_training == 1],
  proj_full[smote_cat == 0][sample(.N, n_samples_SMOTE)])[,
                                                          list(art_page_id, prop_proj_inlinks, prop_from_art,
                                                               prop_act_inlinks, rank_views_perc, rank_links_perc, smote_cat)];

## Generate synthetic samples
proj_synth_data = SMOTE(proj_synth_base[,
                                        list(prop_proj_inlinks, prop_from_art, prop_act_inlinks,
                                             rank_views_perc, rank_links_perc)],
                        proj_synth_base$smote_cat);

## Grab the synthetic and true samples and sample from the other classes
proj_training_set = rbind(
  proj_synth_data$data[class == 1][,
                                   list(prop_proj_inlinks, prop_from_art, prop_act_inlinks,
                                        rank_views_perc, rank_links_perc, class, importance_rating=smote_rating)],
  do.call(rbind, lapply(setdiff(importance_ratings, smote_rating),
                        function(x) { proj_full[importance_rating == x[[1]]][
                          sample(.N, n_samples_SMOTE)][,
                                                       list(prop_proj_inlinks, prop_from_art, prop_act_inlinks,
                                                            rank_views_perc, rank_links_perc, class=0, importance_rating=x)]
                        }))
);
proj_training_set[, importance_rating := ordered(importance_rating, importance_ratings)]

## Verify number of articles in each class
proj_training_set[, list(n_articles=sum(.N)), by=importance_rating]

## Train model
nodesizes = 2**c(1:8)
cv_accuracy = crossvalidate_gbm(importance_relation,
                                proj_training_set, nodesizes, 5000);

## We chose min. nodesize of 32, as it has the lowest deviance
proj_gbm = gbm(importance_relation,
               data=proj_training_set,
               distribution='multinomial',
               n.trees = 7500,
               shrinkage = 0.01,
               n.minobsinnode = 32,
               n.cores = 2,
               cv.folds = 10);
n_trees = gbm.perf(proj_gbm);

## Make predictions, check confusion matrix
proj_full$gbm_pred = sapply(
  apply(
    predict(object=proj_gbm, newdata=proj_full,
            n.trees = n_trees, type='response'),
    1, which.max),
  function(x) { importance_ratings[x]; });
proj_full[, gbm_pred := ordered(gbm_pred, importance_ratings)];
cf = confusionMatrix(table(proj_full$importance_rating,
                           proj_full$gbm_pred));
cf;

## inspect predictions
proj_full[importance_rating == "Top" & gbm_pred == "High",
          list(talk_page_title, num_views, num_inlinks,
               rank_link_p=100*rank_links_perc,
               rank_view_p=100*rank_views_perc, prop_proj_inlinks,
               prop_from_art, prop_act_inlinks)];
proj_full[importance_rating == "Top" & gbm_pred == "Mid",
          list(talk_page_title, num_views, num_inlinks,
               rank_link_p=100*rank_links_perc,
               rank_view_p=100*rank_views_perc, prop_proj_inlinks,
               prop_from_art, prop_act_inlinks)];
proj_full[importance_rating == "Top" & gbm_pred == "Low",
          list(talk_page_title, num_views, num_inlinks,
               rank_link_p=100*rank_links_perc,
               rank_view_p=100*rank_views_perc, prop_proj_inlinks,
               prop_from_art, prop_act_inlinks)];

proj_full[importance_rating == "High" & gbm_pred == "Top",
          list(talk_page_title, num_views, num_inlinks,
               rank_link_p=100*rank_links_perc,
               rank_view_p=100*rank_views_perc, prop_proj_inlinks,
               prop_from_art, prop_act_inlinks)];
proj_full[importance_rating == "High" & gbm_pred == "Mid",
          list(talk_page_title, num_views, num_inlinks,
               rank_link_p=100*rank_links_perc,
               rank_view_p=100*rank_views_perc, prop_proj_inlinks,
               prop_from_art, prop_act_inlinks)];
proj_full[importance_rating == "High" & gbm_pred == "Low",
          list(talk_page_title, num_views, num_inlinks,
               rank_link_p=100*rank_links_perc,
               rank_view_p=100*rank_views_perc, prop_proj_inlinks,
               prop_from_art, prop_act_inlinks)];

proj_full[importance_rating == "Mid" & gbm_pred == "Top",
          list(talk_page_title, num_views, num_inlinks,
               rank_link_p=100*rank_links_perc,
               rank_view_p=100*rank_views_perc, prop_proj_inlinks,
               prop_from_art, prop_act_inlinks)];
proj_full[importance_rating == "Mid" & gbm_pred == "High",
          list(talk_page_title, num_views, num_inlinks,
               rank_link_p=100*rank_links_perc,
               rank_view_p=100*rank_views_perc, prop_proj_inlinks,
               prop_from_art, prop_act_inlinks)];
proj_full[importance_rating == "Mid" & gbm_pred == "Low",
          list(talk_page_title, num_views, num_inlinks,
               rank_link_p=100*rank_links_perc,
               rank_view_p=100*rank_views_perc, prop_proj_inlinks,
               prop_from_art, prop_act_inlinks)];

proj_full[importance_rating == "Low" & gbm_pred == "Top",
          list(talk_page_title, num_views, num_inlinks,
               rank_link_p=100*rank_links_perc,
               rank_view_p=100*rank_views_perc, prop_proj_inlinks,
               prop_from_art, prop_act_inlinks)];
proj_full[importance_rating == "Low" & gbm_pred == "High",
          list(talk_page_title, num_views, num_inlinks,
               rank_link_p=100*rank_links_perc,
               rank_view_p=100*rank_views_perc, prop_proj_inlinks,
               prop_from_art, prop_act_inlinks)];
proj_full[importance_rating == "Low" & gbm_pred == "Mid",
          list(talk_page_title, num_views, num_inlinks,
               rank_link_p=100*rank_links_perc,
               rank_view_p=100*rank_views_perc, prop_proj_inlinks,
               prop_from_art, prop_act_inlinks)];

## Grab examples. Similarly as for WPMED, we aim to get 96 articles, 24 from
## each, since that maps to 3x8, one for each other class.
proj_pred_reratings = rbind(
  proj_full[importance_rating == "High" & gbm_pred == "Top",
            list(talk_page_title, gbm_pred)][sample(.N, 8)],
  proj_full[importance_rating == "Mid" & gbm_pred == "Top",
            list(talk_page_title, gbm_pred)][sample(.N, 8)],
  proj_full[importance_rating == "Low" & gbm_pred == "Top",
            list(talk_page_title, gbm_pred)][sample(.N, 8)],
  proj_full[importance_rating == "Top" & gbm_pred == "High",
            list(talk_page_title, gbm_pred)][sample(.N, 8)],
  proj_full[importance_rating == "Mid" & gbm_pred == "High",
            list(talk_page_title, gbm_pred)][sample(.N, 8)],
  proj_full[importance_rating == "Low" & gbm_pred == "High",
            list(talk_page_title, gbm_pred)][sample(.N, 8)],
  ## 2 Top-importance articles where predicted to be Low, so
  ## the other two samples were adjusted to balance it out.
  proj_full[importance_rating == "Top" & gbm_pred == "Mid",
            list(talk_page_title, gbm_pred)],
  proj_full[importance_rating == "High" & gbm_pred == "Mid",
            list(talk_page_title, gbm_pred)][sample(.N, 11)],
  proj_full[importance_rating == "Low" & gbm_pred == "Mid",
            list(talk_page_title, gbm_pred)][sample(.N, 11)],
  ## 4 Top-importance articles predicted to be Low, so the other two samples
  ## were adjusted to balance it out.
  proj_full[importance_rating == "Top" & gbm_pred == "Low",
            list(talk_page_title, gbm_pred)],
  proj_full[importance_rating == "High" & gbm_pred == "Low",
            list(talk_page_title, gbm_pred)][sample(.N, 10)],
  proj_full[importance_rating == "Mid" & gbm_pred == "Low",
            list(talk_page_title, gbm_pred)][sample(.N, 10)]
);

write(build_pred_wikitable(proj_pred_reratings),
      file=data_path(proj_conf[['prediction table']]));

## Save the model for easy loading later.
wpnfl_gbm = proj_gbm;
save(wpnfl_gbm, file="datasets/wikiproject-nfl/wpnfl_gbm.Robj");

## Make list of the titles of the articles our previous model
## suggested be rerated:
candidates = c('Eddie_George', 'Justin_Tuck', '1960_NFL_season', 'Wes_Chandler',
               'NFC_West', 'Cam_Newton', 'Bill_Walsh_(American_football_coach)',
               'Wilber_Marshall', 'Steve_Tasker', 'Frank_Sinkwich', 'Ernie_Davis',
               'Tom_Bettis', 'Tight_end', 'Archie_Manning', '2003_NFL_Draft',
               'LeGarrette_Blount', 'Tim_Tebow', 'Joe_Kapp', 'Milwaukee_Mile',
               'Pat_Tillman', 'Shane_Matthews', 'Kerwin_Bell',
               'Charles_White_(American_football)', 'Angelo_Bertelli');
proj_full[talk_page_title %in% candidates,
          list(talk_page_title, num_views, num_inlinks,
               rank_link_p=100*rank_links_perc,
               rank_view_p=100*rank_views_perc, prop_proj_inlinks,
               prop_from_art, prop_act_inlinks)];

## Copy "importance_rating" to "rating" for prettier printing.
proj_full[, rating := importance_rating];
## Fix the rating of 
ggplot(proj_full,
       aes(x=100*rank_views_perc, y=100*rank_links_perc)) +
  geom_point(aes(colour=rating)) + facet_grid(. ~ rating) +
  xlab('Percentile of daily average views') + ylab('Percentile of inlinks');

proj_full[importance_rating == 'Top' & rank_links_perc < 0.25];
## I inspected those two articles, they've since been rerated Low-importance.
proj_full[talk_page_title %in% c("Mack_Gladden",
                                 "Dick_Flaherty"), importance_rating := "Low"];

## The model is mainly based on inlinks, what happens if I take views out of
## the equation?
## Train model
nodesizes = 2**c(1:8)
cv_accuracy = crossvalidate_gbm(importance_rating ~ rank_links_perc
                                + prop_proj_inlinks + prop_from_art
                                + prop_act_inlinks,
                                proj_training_set, nodesizes, 5000);

## We chose min. nodesize of 32, as it has the lowest deviance
noview_gbm = gbm(importance_rating ~ rank_links_perc
                 + prop_proj_inlinks + prop_from_art
                 + prop_act_inlinks,
               data=proj_training_set,
               distribution='multinomial',
               n.trees = 4000,
               shrinkage = 0.01,
               n.minobsinnode = 32,
               n.cores = 2,
               cv.folds = 10);
n_trees = gbm.perf(noview_gbm);

## Make predictions, check confusion matrix
proj_full$noview_pred = sapply(
  apply(
    predict(object=noview_gbm, newdata=proj_full,
            n.trees = n_trees, type='response'),
    1, which.max),
  function(x) { importance_ratings[x]; });
proj_full[, noview_pred := ordered(noview_pred, importance_ratings)];
cf_noview = confusionMatrix(table(proj_full$importance_rating,
                           proj_full$noview_pred));
cf_noview;

## There is very little difference between this model and the one with article
## views in it. The main gain comes in High-importance articles. Fascinating
## that we can get this high performance using mainly inlink counts.
