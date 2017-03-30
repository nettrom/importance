## Based on the results of the first classification round,
## does it make sense to combine Top- and High-importance articles?

wpmed_hightop = data.table(wpmed); ## Can't just assign it since it doesn't copy.
wpmed_hightop[rating == 'Top', rating := 'High'];

wpmed_hightop[, sum(.N), by=rating];
wpmed_hightop$rating = ordered(wpmed_hightop$rating, c('High', 'Mid', 'Low'));

## We create a test set of 100 random articles from each class.
hightop_test = rbind(wpmed_hightop[rating == 'High'][sample(.N, 100)],
                     wpmed_hightop[rating == 'Mid'][sample(.N, 100)],
                     wpmed_hightop[rating == 'Low'][sample(.N, 100)]
)

hightop_training = rbind(wpmed_hightop[rating == 'High'
                               & !(talk_page_id %in% hightop_test$talk_page_id)],
                         wpmed_hightop[rating == 'Mid'
                               & !(talk_page_id %in% hightop_test$talk_page_id)][
                                 sample(.N, 987)],
                         wpmed_hightop[rating == 'Low'
                               & !(talk_page_id %in% hightop_test$talk_page_id)][
                                 sample(.N, 987)]);

hightop_test$rating = ordered(hightop_test$rating,
                              c('High', 'Mid', 'Low'));
hightop_training$rating = ordered(hightop_training$rating,
                                  c('High', 'Mid', 'Low'));

## Tune and test an SVM with two or three variables on these datasets.
obj = tune(svm, rating ~ log_links + log_views, data=hightop_training,
           ranges=list(gamma=seq(1.0, 2.0, by=0.1),
                       cost=seq(60, 70, by=1)),
           tunecontrol = tune.control(sampling='fix'));
plot(obj);
summary(obj);

## We use gamma=1.7, cost=65, as suggested by the tuning result.
hightop_imp_svm.1 = svm(rating ~ log_links + log_views, data=hightop_training,
                gamma=1.7, cost=65, cross=10);
summary(hightop_imp_svm.1);

svm_predictions = predict(object=hightop_imp_svm.1,
                          newdata=hightop_test);
hightop_test$svm_pred = svm_predictions;
conf_svm = table(hightop_test$svm_pred, hightop_test$rating);
confusionMatrix(conf_svm);

obj = tune(svm, rating ~ log_links + log_projlinks + log_views, data=hightop_training,
           ranges=list(gamma=seq(0.1, 2.0, by=0.1),
                       cost=seq(10, 20, by=1)),
           tunecontrol = tune.control(sampling='fix'));
plot(obj);
summary(obj);

## We use gamma=0.2, cost=10, as suggested by the tuning result.
hightop_imp_svm.2 = svm(rating ~ log_links + log_views, data=hightop_training,
                        gamma=0.2, cost=10, cross=10);
summary(hightop_imp_svm.2);

svm_predictions = predict(object=hightop_imp_svm.2,
                          newdata=hightop_test);
hightop_test$svm_pred = svm_predictions;
hightop_conf_svm = table(hightop_test$svm_pred, hightop_test$rating);
confusionMatrix(hightop_conf_svm);

## Yes, when we combine the Top- and High-importance articles, that class
## becomes coherent, but it does not make the other two more coherent.
## Overall we're only seeing about 2/3 accuracy, so it's only slightly
## ahead of the results on the four-class problem. 77% accuracy on
## the merged Top+High class is nice, but we're only getting 55% accuracy
## on Mid-importance and 65% on Low-importance. Mid-importance mispredictions
## are kind of all over the board too.