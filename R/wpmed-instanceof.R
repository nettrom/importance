## Investigation into what extent WPMED's articles have a Wikidata item associated
## with them, if that Wikidata item is an instance of anything, and if it is,
## what it is an instance of. We are particularly interested in the latter two for
## Low-importance articles.

library(ggplot2);
library(data.table);

## Load in the datasets
wpmed_instance_top = data.table(read.table('datasets/wpmed-topimportance-instances.tsv',
                                           header=TRUE, sep='\t', quote='',
                                           stringsAsFactors=FALSE));
wpmed_instance_high = data.table(read.table('datasets/wpmed-highimportance-instances.tsv',
                                           header=TRUE, sep='\t', quote='',
                                           stringsAsFactors=FALSE));
wpmed_instance_mid = data.table(read.table('datasets/wpmed-midimportance-instances.tsv',
                                            header=TRUE, sep='\t', quote='',
                                            stringsAsFactors=FALSE));
wpmed_instance_low = data.table(read.table('datasets/wpmed-lowimportance-instances.tsv',
                                            header=TRUE, sep='\t', quote='',
                                            stringsAsFactors=FALSE));
## Add rating
wpmed_instance_top$rating = "Top";
wpmed_instance_high$rating = "High";
wpmed_instance_mid$rating = "Mid";
wpmed_instance_low$rating = "Low";

## Make a combined dataset
wpmed_instance_all = rbind(wpmed_instance_top,
                           wpmed_instance_high,
                           wpmed_instance_mid,
                           wpmed_instance_low);

## First we check articles that don't appear to have a QID:
wpmed_instance_all[QID == 'None']

## We find that there are a few non-articles in our dataset, let's remove those.
non_articles = c('Death panel/Archive 1', 'Party and play/Archive 1',
                 'Equianalgesic/Archive 1', 'Rorschach test/top business',
                 'MDMA/Effects of MDMA on the human body talk page');
wpmed_instance_all = subset(wpmed_instance_all,
                            !(page_title %in% non_articles));

## Now we can use n_articles to calculate number of articles with a QID.
n_articles = length(wpmed_instance_all[, list(QID=unique(QID),
                                              rating=unique(rating), n_instances=sum(.N)), by=page_title]$page_title);
prop_no_qid = length(wpmed_instance_all[QID == 'None']$page_title)/n_articles;

## There are 69 articles that don't have a QID, accounting for 0.23% of all
## articles in WPMED. 
## Let's take those out and calculate how many articles that aren't an instance of
## anything.
wpmed_instance_all = wpmed_instance_all[QID != "None"];
n_articles = length(wpmed_instance_all[, list(QID=unique(QID),
                                              rating=unique(rating), n_instances=sum(.N)), by=page_title]$page_title);
prop_no_instance = length(wpmed_instance_all[instance_of == "None"]$page_title)/n_articles;

## There are 15,959 articles that are currently not an instance of anything.
## That's 54.4% of all of WPMED, and since most of WPMED are Low-importance articles
## it could mean that "instance of" is not solving the problem.

## Let's identify the most frequent instances for each of the ratings.
wpmed_instance_all[rating == "Top" & instance_of != "None",
                   list(n_instances=sum(.N)), by=instance_of][order(n_instances)];

wpmed_instance_all[rating == "High" & instance_of != "None",
                   list(n_instances=sum(.N)), by=instance_of][order(n_instances)];
wpmed_instance_all[rating == "High" & instance_of != "None",
                   list(n_instances=sum(.N)), by=instance_of][order(n_instances)][n_instances > 1];

wpmed_instance_all[rating == "Mid" & instance_of != "None",
                   list(n_instances=sum(.N)), by=instance_of][order(n_instances)];
wpmed_instance_all[rating == "Mid" & instance_of != "None",
                   list(n_instances=sum(.N)), by=instance_of][order(n_instances)][n_instances > 5]
plot_data = wpmed_instance_all[rating == "Mid" & instance_of != "None",
                               list(n_instances=sum(.N)), by=instance_of][order(n_instances)][n_instances > 1];
plot_data$idx = seq.int(nrow(plot_data));
ggplot(plot_data, aes(x=idx, y=n_instances)) + geom_line();

wpmed_instance_all[rating == "Low" & instance_of != "None",
                   list(n_instances=sum(.N)), by=instance_of][order(n_instances)];
wpmed_instance_all[rating == "Low" & instance_of != "None",
                   list(n_instances=sum(.N)), by=instance_of][order(n_instances)][n_instances > 1];

plot_data = wpmed_instance_all[rating == "Low" & instance_of != "None",
                               list(n_instances=sum(.N)), by=instance_of][order(n_instances)][n_instances > 1];
plot_data$idx = seq.int(nrow(plot_data));
ggplot(plot_data, aes(x=idx, y=n_instances)) + geom_line();

## Write out a TSV of all instances that are used for Low-importance articles.
write.table(wpmed_instance_all[rating == "Low" & instance_of != "None",
                   list(n_instances=sum(.N)), by=instance_of][order(n_instances)],
            file='datasets/wpmed-lowimportance-instances-used.tsv', sep='\t',
            quote=FALSE, row.names=FALSE);

## QIDs without an English label:
paste(c('Q20181809', 'Q1727131', 'Q3355775', 'Q1621078', 'Q28008646', 'Q2458474',
'Q1595418', 'Q1401195', 'Q10911316', 'Q3508425'), collapse="|")
