## Shared code for building models for WikiProjects

library(yaml);
library(data.table);
library(smotefamily);
library(gbm);
library(caret);

data_path = function(filename) {
  paste0(data_dir, '/', filename);
}

load_data = function(project_config) {
  ## Read in datasets
  snapshot = fread(data_path(project_config[['snapshot file']]));
  dataset = fread(data_path(project_config['dataset']));
  clickstream = fread(data_path(project_config['clickstream file']));
  disambiguations = fread(data_path(project_config['disambiguation file']));
  
  ## Log transform number of inlinks, number of views, calculate prop_proj_inlinks
  dataset[, log_inlinks := log10(1 + num_inlinks)];
  dataset[, log_views := log10(1 + num_views)];
  dataset[, prop_proj_inlinks := 1 + num_proj_inlinks/(1 + num_inlinks)];
  
  ## Calculate the proportion of clicks from articles
  clickstream[, prop_from_art := pmin(1.0, n_from_art / (1 + n_clicks))];
  
  ## Join datasets
  setkey(snapshot, art_page_id);
  setkey(dataset, page_id);
  setkey(clickstream, page_id);
  
  full = snapshot[dataset[clickstream]];
  
  ## Filter out pages where the talk page is an archive
  full = full[talk_is_archive == 0];
  
  ## Filter out pages where the article is a redirect
  full = full[art_is_redirect == 0];
  
  ## Filter out pages where there is no corresponding article
  full = full[art_page_id > 0];
  
  ## Filter out disambiguations identified through the enwiki category
  full = full[!(art_page_id %in% disambiguations$page_id)];

  ## Calculate the last proportional variable, which requires the join
  full[, prop_act_inlinks := pmin(1.0, n_act_links / (1 + num_inlinks))];
  
  ## Add rank variables for views and inlinks and make them percentiles
  full[, rank_links := frank(full, num_inlinks, ties.method = 'min')];
  full[, rank_views := frank(full, num_views, ties.method = 'min')];
  full[, rank_links_perc := (rank_links-1)/max(full$rank_links)];
  full[, rank_views_perc := (rank_views-1)/max(full$rank_views)];
  
  ## Importance ratings are ordered
  full[, importance_rating := ordered(importance_rating, importance_ratings)];
  return(full);
}

crossvalidate_gbm = function(formula, dataset, nodesizes, n_trees, 
                             n_cores=2, n_folds=10, shrink=0.01) {
  accs = c();
  trees = c();
  for(k in nodesizes) {
    cv_gbm = gbm(formula, data=dataset,
                  distribution='multinomial',
                  n.trees = n_trees,
                  shrinkage = shrink,
                  n.minobsinnode = k,
                  n.cores = n_cores,
                  cv.folds = n_folds,
                  keep.data = FALSE); # don't need to keep the data for this one
    t = gbm.perf(cv_gbm);
    trees = append(trees, t);
    accs = append(accs, cv_gbm$cv.error[t]);
  }
  return(data.table(nodesize=nodesizes, forestsize=trees, accuracy=accs));
}

build_pred_wikitable = function(dataset) {
  wp_table = paste0('{| class="wikitable sortable"\n|-\n',
                    '! scope="col" style="width: 45%;" | Title\n',
                    '! scope="col" style="width: 15%;" | Pred. rating\n',
                    '! Notes\n');
  
  for(i in seq(1, length(dataset$talk_page_title))) {
    page_title = gsub('_', ' ', dataset[i,]$talk_page_title, fixed=TRUE);
    prediction = dataset[i,]$gbm_pred;
    wp_table = paste0(wp_table, "|-\n| [[", page_title, "]] <small>([[Talk:",
                      page_title, "|talk]])</small>\n| style='text-align: center;' | ", prediction, "\n| \n");
  }
  paste0(wp_table, "|}")
}
