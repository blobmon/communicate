CREATE EXTENSION pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    username text PRIMARY KEY,
    password_md5 text NOT NULL,
    created_ts timestamp NOT NULL default now(),
    user_id text,
    last_activity_ts timestamp NOT NULL default now(),
    session_id text,

    about text,
    info jsonb

);

CREATE TABLE IF NOT EXISTS login_attempt_log (
    id SERIAL PRIMARY KEY,
    user_id text NOT NULL, -- create index
    ts timestamp NOT NULL default now()
);

CREATE INDEX IF NOT EXISTS  login_attempt_user_idx  ON login_attempt_log(user_id);

CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,    
    thread_id int NOT NULL,  -- add index
    username text NOT NULL, -- add index
    user_id text NOT NULL,  -- add index
    ts timestamp NOT NULL default now(),
    text text,
    blob_savename text,
    blob_type text,
    blob_info jsonb,  -- filename img_size file_size
    delete_status int NOT NULL DEFAULT 0,
    mod_post int NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS posts_thread_idx ON posts (thread_id);
CREATE INDEX IF NOT EXISTS posts_username_idx ON posts (username);
CREATE INDEX IF NOT EXISTS posts_userid_idx ON posts (user_id);

ALTER SEQUENCE posts_id_seq RESTART WITH 100;

CREATE TABLE IF NOT EXISTS threads (
    post_id int REFERENCES posts(id) ON DELETE CASCADE ON UPDATE CASCADE,
    username text NOT NULL,     
    user_id text NOT NULL,
    ts timestamp NOT NULL default now(),
    post_count int NOT NULL,
    posters_count int NOT NULL,
    bump_ts timestamp NOT NULL,
    delete_status int NOT NULL DEFAULT 0,
    locked int NOT NULL DEFAULT 0,
    pinned int NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS report_src (
    id SERIAL PRIMARY KEY,
    reporter_username text NOT NULL, -- add index
    post_id int REFERENCES posts(id) ON DELETE CASCADE ON UPDATE CASCADE,  -- add index
    ts timestamp NOT NULL default now(),
    reported_username text NOT NULL,
    reason int NOT NULL,
    consumed boolean NOT NULL
);

CREATE INDEX IF NOT EXISTS reportsrc_idsrc_idx ON report_src (reporter_username);
CREATE INDEX IF NOT EXISTS reportsrc_postid_idx ON report_src (post_id);


CREATE TABLE IF NOT EXISTS ban_ptr (
    username text REFERENCES users(username) ON DELETE CASCADE ON UPDATE CASCADE PRIMARY KEY,
    ts timestamp NOT NULL default now(),
    ban_till_ts timestamp NOT NULL,
    ban_reason int NOT NULL,
    --ban_reason_text text NOT NULL,
    --ban_post_id int
    mod_log_id int
);


-- tables for moderator things

CREATE TABLE IF NOT EXISTS moderator_list (
    username text REFERENCES users(username) ON DELETE CASCADE ON UPDATE CASCADE PRIMARY KEY,
    actions_per_hour int NOT NULL DEFAULT 10
);

CREATE TABLE IF NOT EXISTS moderator_log (
    id SERIAL PRIMARY KEY,
    moderator_username text, -- REFERENCES moderator_list(username)
    ts timestamp NOT NULL default now(),  -- add index
    action text NOT NULL,

    info jsonb
);

CREATE INDEX IF NOT EXISTS  moderator_log_ts_idx ON moderator_log(ts);

