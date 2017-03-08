## Let's sample some of the unanimously rated articles to see if they're good
## candidates for usage as a site-wide importance dataset.

only_articles[n_top > 1 & n_high == 0 & n_mid == 0 & n_low == 0 & n_unknown == 0 & n_na == 0][sample(.N, 12), list(talk_page_title)];
only_articles[n_top == 0 & n_high > 1 & n_mid == 0 & n_low == 0 & n_unknown == 0 & n_na == 0][sample(.N, 12), list(talk_page_title)];
only_articles[n_top == 0 & n_high == 0 & n_mid > 1 & n_low == 0 & n_unknown == 0 & n_na == 0][sample(.N, 12), list(talk_page_title)];
only_articles[n_top == 0 & n_high == 0 & n_mid == 0 & n_low > 1 & n_unknown == 0 & n_na == 0][sample(.N, 12), list(talk_page_title)];

## The articles we sampled are:
## Top-importance:
##   Albania–Kosovo_relations
##             Small_business
##             Massina_Empire
##   Women_in_the_Middle_Ages
##      Prophecy_(Shia_Islam)
##          Cinema_of_Algeria
##             United_Kingdom
##                       Sejm
##             Jean_Metzinger
## Political_status_of_Kosovo
##                   Gaborone
##                  Fiduciary

## High-importance:
##                              Graphyne
##                               Utamaro
##                        Gopinath_(god)
##                                 FedEx
##                   Competitor_analysis
## The_Mind_Is_a_Terrible_Thing_to_Taste
##                                Rostec
##              Distinction_(philosophy)
##                        Protein_family
## Indigenous_peoples_of_the_Philippines
##                 Origin_of_replication
##       Resident_Evil_(1996_video_game)

## Mid-importance:
##                               Désiré_Munyaneza
## Disseminated_superficial_actinic_porokeratosis
##             Poland_at_the_1996_Summer_Olympics
##                                    Sun_Jianguo
##                                  Orleans_Canal
##            Elliptic_curve_point_multiplication
##                            Isilkulsky_District
##                             Parque_de_la_Costa
##                                         Ataxia
##                                           AH82
##                                Port_of_Jiaxing
##      Owensboro_Community_and_Technical_College

## Low-importance:
##                                             Tha_Hall_of_Game
##                                               Stephanie_Sheh
## Department_of_State_Development,_Infrastructure_and_Planning
##                                                Ridhima_Ghosh
##                              Australian_Natives'_Association
##                                    Badminton_railway_station
##                           Indefinite_detention_without_trial
##                                                     Pyeonyuk
##                                   Andrei_Ivanovich_Gorchakov
##                                          Uroballus_henicurus
##                                              Sabine_(crater)
##                                                     Singikat

## Sanity check against quality-based categories… looks sane to me!
## (Note: we're ignoring the "rocks and minerals" WikiProject because
## I didn't want to adapt the regex to it).
only_articles[n_top > 1 & n_high == 0 & n_mid == 0 & n_low == 0 & n_unknown == 0 & n_na == 0][grep('-class', wikiprojects, fixed=TRUE)][grep('(russia|geology|mcb)', wikiprojects, invert = TRUE)];
only_articles[n_top == 0 & n_high > 1 & n_mid == 0 & n_low == 0 & n_unknown == 0 & n_na == 0][grep('-class', wikiprojects, fixed=TRUE)][grep('(russia|geology|mcb|palaeontology)', wikiprojects, invert = TRUE)];
only_articles[n_top == 0 & n_high == 0 & n_mid > 1 & n_low == 0 & n_unknown == 0 & n_na == 0][grep('-class', wikiprojects, fixed=TRUE)][grep('(russia|geology|mcb|palaeontology)', wikiprojects, invert = TRUE)];
only_articles[n_top == 0 & n_high == 0 & n_mid == 0 & n_low > 1 & n_unknown == 0 & n_na == 0][grep('-class', wikiprojects, fixed=TRUE)][grep('(russia|geology|mcb|palaeontology)', wikiprojects, invert = TRUE)];
