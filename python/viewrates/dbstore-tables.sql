DROP TABLE IF EXISTS nettrom_vr_status;
DROP TABLE IF EXISTS nettrom_vr_page;
DROP TABLE IF EXISTS nettrom_vr_newpage;
DROP TABLE IF EXISTS nettrom_vr_newpage_data;

CREATE TABLE nettrom_vr_status (
    latest_update DATETIME DEFAULT NULL
);
INSERT INTO nettrom_vr_status VALUES (NULL);

CREATE TABLE nettrom_vr_page (
    page_id INT UNSIGNED NOT NULL PRIMARY KEY,
    page_title VARCHAR(255) BINARY NOT NULL,
    num_views INT DEFAULT 0
);

CREATE TABLE nettrom_vr_newpage (
    page_id INT UNSIGNED NOT NULL PRIMARY KEY,
    first_edit DATETIME
);

CREATE TABLE nettrom_vr_newpage_data (
    page_id INT UNSIGNED NOT NULL,
    view_date DATE NOT NULL,
    num_views INT DEFAULT 0,
    PRIMARY KEY (page_id, view_date)
);
