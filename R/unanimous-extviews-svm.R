## Generating SVM classifier results for my work log writeup.

## Averaged across all 84 days of data.
obj = tune(svm, rating ~ log_inlinks + log_totavg,
           data=training.set,
           ranges=list(gamma=seq(0.05, 0.15, by=0.01),
                       cost=seq(2, 10, by=1)),
           tunecontrol = tune.control(sampling='fix'));
summary(obj);
plot(obj);

## Based on the tuning output I use gamma=0.05 and cost=4
imp_svm = svm(rating ~ log_inlinks + log_totavg,
              data=training.set,
              cost=4, gamma=0.05, cross=10);
summary(imp_svm);

svm_predictions = predict(object=imp_svm,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;

conf_svm.1 = table(test.set$svm_pred, test.set$rating);
confusionMatrix(conf_svm.1);

## Splitting it up into three groups of 28 days.
obj = tune(svm, rating ~ log_inlinks + log_f28avg + log_s28avg + log_t28avg,
           data=training.set,
           ranges=list(gamma=seq(0.05, 0.15, by=0.01),
                       cost=seq(5, 25, by=5)),
           tunecontrol = tune.control(sampling='fix'));
summary(obj);
plot(obj);

## Based on the tuning output I use gamma=0.06 and cost=20
imp_svm = svm(rating ~ log_inlinks + log_totavg,
              data=training.set,
              cost=20, gamma=0.06, cross=10);
summary(imp_svm);

svm_predictions = predict(object=imp_svm,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;

conf_svm.2 = table(test.set$svm_pred, test.set$rating);
confusionMatrix(conf_svm.2);

## Using the last week plus four weeks preceeding it.
obj = tune(svm, rating ~ log_inlinks + log_l1avg + log_l4avg,
           data=training.set,
           ranges=list(gamma=seq(0.05, 0.15, by=0.01),
                       cost=seq(1, 10, by=1)),
           tunecontrol = tune.control(sampling='fix'));
summary(obj);
plot(obj);

## Based on the tuning output I use gamma=0.15 and cost=3
imp_svm = svm(rating ~ log_inlinks + log_totavg,
              data=training.set,
              cost=3, gamma=0.15, cross=10);
summary(imp_svm);

svm_predictions = predict(object=imp_svm,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;

conf_svm.3 = table(test.set$svm_pred, test.set$rating);
confusionMatrix(conf_svm.3);

## Only using the last week
obj = tune(svm, rating ~ log_inlinks + log_l1avg,
           data=training.set,
           ranges=list(gamma=seq(0.05, 0.15, by=0.01),
                       cost=seq(1, 10, by=1)),
           tunecontrol = tune.control(sampling='fix'));
summary(obj);
plot(obj);

## Based on the tuning output I use gamma=0.08 and cost=10
imp_svm = svm(rating ~ log_inlinks + log_totavg,
              data=training.set,
              cost=10, gamma=0.08, cross=10);
summary(imp_svm);

svm_predictions = predict(object=imp_svm,
                          newdata=test.set);
test.set$svm_pred = svm_predictions;

conf_svm.4 = table(test.set$svm_pred, test.set$rating);
confusionMatrix(conf_svm.4);
