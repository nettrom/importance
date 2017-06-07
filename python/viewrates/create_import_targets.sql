-- Tables for storing data imported back from Hadoop
DROP TABLE IF EXISTS nettrom_vr_temp_newpage;
DROP TABLE IF EXISTS nettrom_vr_temp_oldpage;

CREATE TABLE nettrom_vr_temp_newpage (
    page_id BIGINT NOT NULL,
    view_year INT NOT NULL,
    view_month INT NOT NULL,
    view_day INT NOT NULL,
    num_views BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE nettrom_vr_temp_oldpage (
   page_id BIGINT NOT NULL,
   old_views BIGINT NOT NULL DEFAULT 0,
   new_views BIGINT NOT NULL DEFAULT 0
);
