CREATE OR REPLACE FUNCTION user_banned(in_username text, in_ban_gt integer, in_ban_lt integer, in_return_ban_reason boolean DEFAULT 'f' )
RETURNS integer AS
$$
DECLARE
	v_ban_ptr_row ban_ptr%ROWTYPE;
        
BEGIN
	SELECT * INTO v_ban_ptr_row FROM ban_ptr WHERE username=in_username;

	if NOT FOUND THEN 
		return 0;
	end if;

	if v_ban_ptr_row.ban_reason BETWEEN in_ban_gt AND in_ban_lt AND 
	   v_ban_ptr_row.ban_till_ts > now() THEN
		if in_return_ban_reason = 'f' THEN
			return 1;
		else
			return v_ban_ptr_row.ban_reason;
		end if;
	end if;

	return 0;

END;
$$ LANGUAGE plpgsql;

--ban reason integers : 1->soft, 2->spam/offtopic, 3->illegal/inappropriate
CREATE OR REPLACE FUNCTION ban_user(in_username text, in_ban_reason integer, in_ban_duration interval, 
	in_mod_log_id integer)
RETURNS integer AS
$$
DECLARE
	v_ban_ptr_row ban_ptr%ROWTYPE;

BEGIN
	SELECT * INTO v_ban_ptr_row FROM ban_ptr WHERE username=in_username;
	if FOUND THEN
		if v_ban_ptr_row.ban_till_ts > now() THEN

			if in_ban_reason > v_ban_ptr_row.ban_reason THEN
				v_ban_ptr_row.ban_reason = in_ban_reason;
				v_ban_ptr_row.mod_log_id = in_mod_log_id;
			end if;

			UPDATE ban_ptr SET 
			(ban_reason, ban_till_ts, mod_log_id)=(v_ban_ptr_row.ban_reason, v_ban_ptr_row.ban_till_ts + in_ban_duration, v_ban_ptr_row.mod_log_id)
			WHERE username=in_username;
		else 
			UPDATE ban_ptr SET 
			(ban_reason, ban_till_ts, mod_log_id)=(in_ban_reason, now() + in_ban_duration, in_mod_log_id)
			WHERE username=in_username;
		end if;
		return 2;  -- return 2 if updated a user who was already banned before
	else 		
		INSERT INTO ban_ptr (username, ts, ban_till_ts, ban_reason, mod_log_id)
		VALUES (in_username, now(), now()+in_ban_duration, in_ban_reason, in_mod_log_id);
		return 1;  -- return 1 if user is banned for first time
	end if;
	return 0;  -- should not reach here ever
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION unban_user(in_username text)
RETURNS integer AS
$$
DECLARE
	v_ban_ptr_row ban_ptr%ROWTYPE;

BEGIN
	SELECT * INTO v_ban_ptr_row FROM ban_ptr WHERE username=in_username;
	if FOUND THEN
		if v_ban_ptr_row.ban_till_ts > now() THEN
			UPDATE ban_ptr SET (ban_till_ts)=( now() ) WHERE username=in_username;
			return 1;
		end if;
	end if;
	return 0;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION create_account(in_username text, in_user_id text, in_password_md5 text, 
	OUT out_status integer, OUT out_status_text text) AS
$$
DECLARE
	v_accounts_created_by_user_id integer;

	v_session_id text;

BEGIN
	-- if user_id is not rabid creating accounts
	-- if username doesn't exist already

	SELECT count(*) INTO v_accounts_created_by_user_id FROM users WHERE created_ts > now() - INTERVAL '60m' 
	AND user_id = in_user_id;

	if v_accounts_created_by_user_id > 3 THEN
		out_status = -1;
		out_status_text = 'please create an account after some time';
		RETURN;
	end if;

	PERFORM * FROM users WHERE username = in_username;

	if FOUND THEN
		out_status = -1;
		out_status_text = 'username already in use';
		RETURN;
	end if;


	-- now we proceed to add the user account to the database
	SELECT * INTO v_session_id FROM get_new_session_id();

	INSERT INTO users (username, password_md5, user_id, session_id) 
		VALUES (in_username, in_password_md5, in_user_id, v_session_id);

	out_status = 1;
	out_status_text = v_session_id;
	
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION user_login(in_username text, in_user_id text, in_password_md5 text, OUT out_status integer, OUT out_status_text text)
AS
$$
DECLARE
	v_login_attempt_count integer := 0;
	v_users_row users%ROWTYPE;

	v_session_id text;

BEGIN
	
	SELECT COUNT(*) INTO v_login_attempt_count FROM login_attempt_log WHERE user_id=in_user_id AND ts > now() - INTERVAL'15m';

	if v_login_attempt_count > 10 THEN
		out_status = -1;
		out_status_text = 'too many attempts to login. please login after some time';
		RETURN;
	end if;


	SELECT * INTO v_users_row FROM users WHERE username = in_username;

	if NOT FOUND THEN
		out_status = -1;
		out_status_text = 'user does not exist';
		RETURN;
	end if; 

	if v_users_row.password_md5 != in_password_md5 THEN

		INSERT INTO login_attempt_log (user_id) VALUES (in_user_id);

		out_status = -1;
		out_status_text = 'password incorrect';
		RETURN;
	end if;	
	


	if v_users_row.session_id IS NULL THEN
		SELECT * INTO v_session_id FROM get_new_session_id();
	else 
		v_session_id = v_users_row.session_id;
	end if;

	UPDATE users SET (last_activity_ts, session_id)=( now(), v_session_id) WHERE username = in_username;

	out_status = 1;
	out_status_text = v_session_id;

END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_new_session_id(OUT random_uuid text)
AS
$$
BEGIN
	SELECT * INTO random_uuid FROM concat(gen_random_uuid(), '-', md5(random()::text) );
END;
$$LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION update_last_activity_ts(in_username text, in_session_id text, OUT out_status integer) 
AS
$$
BEGIN
	UPDATE users SET (last_activity_ts)=(now() ) WHERE username = in_username AND session_id = in_session_id;
	out_status = 1;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION user_logout(in_username text, in_session_id text, OUT out_status integer, OUT out_status_text text)
AS
$$
DECLARE
	v_users_row users%ROWTYPE;
BEGIN
	SELECT * INTO v_users_row FROM users WHERE username = in_username AND session_id = in_session_id;

	if NOT FOUND THEN
		out_status = -1;
		out_status_text = 'user does not exist';
		RETURN;
	end if;

	UPDATE users SET (session_id)=(NULL) WHERE username = in_username;

	out_status = 1;

END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION check_login_status (in_username text, in_session_id text, OUT out_status integer)
AS
$$
DECLARE
	v_users_row users%ROWTYPE;	
BEGIN
	SELECT * INTO v_users_row FROM users WHERE username = in_username AND session_id = in_session_id;

	if NOT FOUND THEN
		out_status = -1;
		RETURN;
	end if;

	out_status = 1;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION check_login_status_and_mod_status (in_username text, in_session_id text, OUT out_status integer)
AS
$$
DECLARE
	v_login_status integer := -1;
BEGIN
	SELECT * INTO v_login_status FROM check_login_status(in_username, in_session_id);

	if v_login_status = -1 THEN
		out_status = -1;
		RETURN;
	end if;

	PERFORM * FROM moderator_list WHERE username=in_username;
	if FOUND THEN
		out_status = 1;
		RETURN;
	end if;

	out_status = -1;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION start_post ( in_thread_id int, in_username text, in_user_id text, in_session_id text, 
	in_text text, in_blob_name text, in_blob_type text, in_blob_info jsonb, in_bump int,
	OUT out_status integer, OUT out_status_text text ) 
AS
$$
DECLARE
	v_login_status integer;

	v_posts_by_username integer := 0;
	v_ban_reason integer := 0;
	v_thread_row threads%ROWTYPE;
	v_post_id integer := -1;

	v_last_ts_by_user_id timestamp := timestamp '2018-1-1';
	v_temp integer := 0;
	v_posters_increment integer := 0;

	v_mod_post integer := 0;
	
	v_mod_start_post_info text;
	v_mod_start_post_info_format CONSTANT text := '{"post_id" : %s, "thread_id" : %s}';

BEGIN
	SELECT * INTO v_login_status FROM check_login_status(in_username, in_session_id);

	if v_login_status != 1 THEN
		out_status = -1;
		out_status_text = 'not logged in';
		RETURN;
	end if;


	PERFORM * FROM moderator_list WHERE username=in_username;
	if FOUND THEN
		v_mod_post = 1;
	end if;

	-- check if user is flooding sv with posts
	SELECT count(*) INTO v_posts_by_username FROM posts WHERE username=in_username AND ts > now() - INTERVAL '15m';
	if v_posts_by_username > 10 THEN		
		if ban_user(in_username, 1, '10m', NULL) > 0 THEN  -- softban for 10m
			out_status = -1;
			out_status_text = 'Please wait for a while before posting!';
			RETURN;
		end if;
	end if;


	SELECT * INTO v_thread_row  FROM threads WHERE post_id=in_thread_id FOR UPDATE; -- if thread is valid, Also, take note of "FOR UPDATE"
	if NOT FOUND THEN
		out_status = -1;
		out_status_text = 'mongodb exception : no variable ''id'' in line 23'; -- joke
		RETURN;
	end if;

	if v_thread_row.locked = 1 THEN  -- thread locked means can't post
		out_status = -1;
		out_status_text = 'thread is locked';
		RETURN;
	end if;

	v_ban_reason = user_banned(in_username, 1, 3, 't');

	if v_ban_reason > 0 THEN -- if banned
		if v_ban_reason = 1 THEN -- if soft banned
			out_status = -1;
			out_status_text = 'Please wait for a while before posting.';
		elsif v_ban_reason > 1 THEN -- if hard banned
			out_status = -1;
			out_status_text = 'banned';
		end if;

		RETURN;
	end if;


	if v_thread_row.delete_status > 0 OR v_thread_row.post_count >= 500 THEN
		out_status = -1;
		out_status_text = 'you can''t post in this thread anymore';
		RETURN;
	end if;


	SELECT ts INTO v_last_ts_by_user_id FROM posts WHERE user_id=in_user_id ORDER BY ts DESC LIMIT 1; 
	IF NOT FOUND THEN
		v_last_ts_by_user_id = timestamp '2018-1-1';
	END IF;

	INSERT INTO posts (thread_id, username, user_id, text, blob_savename, blob_type, blob_info, delete_status, mod_post) VALUES
	(v_thread_row.post_id, in_username, in_user_id, in_text, in_blob_name, in_blob_type, in_blob_info, 0, v_mod_post)
	RETURNING id INTO v_post_id;

	if in_bump > 0 AND v_thread_row.pinned = 0 AND v_thread_row.bump_ts < now() - INTERVAL '60s' 
	AND v_last_ts_by_user_id < now() - INTERVAL '60s' AND v_thread_row.post_count < 200 THEN -- if bumpable AND not a pinned thread AND thread not bumped recently  AND post_count is < 200
		v_thread_row.bump_ts = now();
	end if;

	-- posters_count get
	SELECT COUNT(*) INTO v_temp FROM posts WHERE thread_id=in_thread_id AND username=in_username;
	if v_temp = 1 THEN  -- SELECT FOR UPDATE above was done because of this :)
		v_posters_increment = 1;
	end if;

	UPDATE threads SET (bump_ts, post_count, posters_count)=(v_thread_row.bump_ts, post_count+1, posters_count + v_posters_increment)
	WHERE post_id = in_thread_id;

	if v_mod_post = 1 THEN
		v_mod_start_post_info = format(v_mod_start_post_info_format, v_post_id, v_thread_row.post_id);		
		PERFORM moderator_log_add( in_username, 'start_post', v_mod_start_post_info );
	end if;

	out_status = v_post_id;
	

END;
$$ LANGUAGE plpgsql;



CREATE OR REPLACE FUNCTION start_thread ( in_username text, in_user_id text, in_session_id text, 
	in_text text, in_blob_name text, in_blob_type text, in_blob_info jsonb,
	OUT out_status integer, OUT out_status_text text ) 
AS
$$
DECLARE
	v_login_status integer := 0;

	v_threads_created_by_username integer := 0;
	v_posts_by_username integer := 0;

	v_ban_reason integer := 0;
	v_post_id integer := 0;

	v_last_thread_post_id_arr integer[];
	v_idee integer;

	v_threads_per_stream integer := 200;

	v_mod_post integer := 0; 

		
	v_mod_start_post_info text;
	v_mod_start_post_info_format CONSTANT text := '{"post_id" : %s, "thread_id" : %s}';
BEGIN

	SELECT * INTO v_login_status FROM check_login_status(in_username, in_session_id);

	if v_login_status != 1 THEN
		out_status = -1;
		out_status_text = 'not logged in.';
		RETURN;
	end if;

	-- check if user is flooding sv with posts
	SELECT count(*) INTO v_posts_by_username FROM posts WHERE username=in_username AND ts > now() - INTERVAL '15m';
	if v_posts_by_username > 10 THEN
		if ban_user(in_username, 1, '10m', NULL) > 0 THEN  -- softban for 10m
			out_status = -1;
			out_status_text = 'Please wait for a while before posting!';
			RETURN;
		end if;
	end if;

	v_ban_reason = user_banned(in_username, 1, 3, 't');
	if v_ban_reason > 0 THEN -- if banned
		if v_ban_reason = 1 THEN -- if soft banned
			out_status = -1;
			out_status_text = 'Please wait for a while before posting.';
		elsif v_ban_reason > 1 THEN -- if hard banned
			out_status = -1;
			out_status_text = 'banned';
		end if;

		RETURN;
	end if;

	PERFORM * FROM moderator_list WHERE username=in_username;
	if FOUND THEN
		v_mod_post = 1;
	end if;
		
	-- no of threads created by this user in last 60 min
	SELECT count(post_id) INTO v_threads_created_by_username FROM threads WHERE 
	username=in_username AND ts > now() - INTERVAL'60m';

	if v_threads_created_by_username <= 2 THEN  -- max 3 threads allowed
		
		INSERT INTO posts (thread_id, username, user_id, text, blob_savename, blob_type, blob_info, delete_status, mod_post) VALUES
		( currval('posts_id_seq'), in_username, in_user_id, in_text, in_blob_name, in_blob_type, in_blob_info, 0, v_mod_post )
		RETURNING id INTO v_post_id;
		
		INSERT INTO threads (post_id, username, user_id, post_count, posters_count, bump_ts, delete_status, locked, pinned ) VALUES
		( v_post_id, in_username, in_user_id, 1, 1, now(), 0, 0, 0 );

		-- marking last thread in the board and the post as 1 ( removed naturally delete_status = 1 )
		v_last_thread_post_id_arr = array( SELECT post_id FROM threads WHERE delete_status = 0 ORDER BY bump_ts DESC OFFSET v_threads_per_stream );
		FOREACH v_idee IN ARRAY v_last_thread_post_id_arr
		LOOP
			UPDATE threads SET delete_status = 1 WHERE post_id = v_idee;
			UPDATE posts SET delete_status = 1 WHERE id = v_idee;
		END LOOP;

		if v_mod_post = 1 THEN
			v_mod_start_post_info = format(v_mod_start_post_info_format, v_post_id, v_post_id);
			PERFORM moderator_log_add( in_username, 'start_post', v_mod_start_post_info );
		end if;			

		out_status = v_post_id;
	else
		out_status = -1;
		out_status_text = 'Please create a new thread after some time.';
	end if;		
	
END;
$$ LANGUAGE plpgsql;


-- post_id, ts, bump_ts, post_count, text, blobx3 fields
CREATE OR REPLACE FUNCTION get_stream( in_login_status integer, in_username text, in_session_id text )
RETURNS TABLE (post_id int, ts double precision, bump_ts double precision, post_count int, username text, 
		txt text, locked int, pinned int, mod_post int, blob_savename text )
AS 
$$
BEGIN	
	RETURN QUERY SELECT threads.post_id, extract(epoch from threads.ts), extract(epoch from threads.bump_ts), threads.post_count, 
	posts.username, posts.text,	threads.locked, threads.pinned, posts.mod_post, posts.blob_savename FROM threads INNER JOIN posts ON posts.id=threads.post_id
 	WHERE threads.delete_status=0 ;

 	/* update the last activity ts if user is logged in*/
 	if in_login_status = 1 THEN
 		PERFORM * FROM update_last_activity_ts(in_username, in_session_id);
 	end if;
END;
$$ LANGUAGE plpgsql;


/*
	returns rows of the posts table
	note : the ts column changed to utc in posts_utc
*/
CREATE OR REPLACE VIEW posts_utc AS SELECT id, thread_id, username, user_id, 
extract(epoch from ts) AS utc, text, 
blob_savename, blob_type, blob_info, delete_status, mod_post FROM posts;



CREATE OR REPLACE FUNCTION get_post( in_thread_id integer )
RETURNS SETOF posts_utc
AS
$$
BEGIN
	RETURN QUERY SELECT * FROM posts_utc WHERE thread_id=in_thread_id AND delete_status != 10 ORDER BY utc;

END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION get_update( in_thread_id integer, in_last_id integer )
RETURNS SETOF posts_utc
AS
$$
DECLARE	
	v_last_id_utc double precision := 0;
BEGIN	
	SELECT utc INTO v_last_id_utc FROM posts_utc WHERE id>=in_last_id 
	AND thread_id=in_thread_id ORDER BY utc LIMIT 1;
	
	RETURN QUERY SELECT * FROM posts_utc WHERE thread_id=in_thread_id AND utc>=v_last_id_utc AND delete_status != 10 ORDER BY utc;

END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION report_post( in_username text, in_session_id text,
	in_thread_id integer, in_post_id integer, in_report_reason integer,
	OUT out_status integer, OUT out_status_text text )
AS
$$
DECLARE
	v_login_status integer;

	v_posts_row posts%ROWTYPE;
	v_threads_row threads%ROWTYPE;

	v_reportsrc_row report_src%ROWTYPE;

	v_ban_reason integer := 0;
	v_rabid_report_count integer := 0;

	v_post_deletable integer := 0;
	v_delete_threshold integer := 1000;  -- previously this number was 4, but changed it to large number because of abuse

	v_1_report_count integer := 0;
	v_2_report_count integer := 0;

	v_temp integer:= 0;

	v_delete_status_to_set integer := 2;  -- default is deleted by other users. will be set to 4 if reporter is same as poster

	v_undelete_thread_id integer;
BEGIN
	-- if user is logged in
	-- if user not banned	
	-- post_id exists and not deleted and thread_exists and not deleted
	-- user_id not rabid reporting
	-- user_id not already reported for the post_id


	SELECT * INTO v_login_status FROM check_login_status(in_username, in_session_id);

	if v_login_status != 1 THEN
		out_status = -1;
		out_status_text = 'not logged in.';
		RETURN;
	end if;


	v_ban_reason = user_banned(in_username, 1, 3, 't');
	if v_ban_reason > 0 THEN -- if banned
		if v_ban_reason = 1 THEN -- if soft banned
			out_status = -1;
			out_status_text = 'Please wait for a while before posting.';
		elsif v_ban_reason > 1 THEN -- if hard banned
			out_status = -1;
			out_status_text = 'banned';
		end if;

		RETURN;
	end if;	

	SELECT * INTO v_posts_row FROM posts WHERE id = in_post_id AND thread_id=in_thread_id;

	if NOT FOUND THEN
		out_status = -1;
		out_status_text = 'post does not exist';
		RETURN;	
	end if;

	SELECT * INTO v_threads_row FROM threads WHERE post_id=v_posts_row.thread_id;

	if NOT FOUND THEN
		out_status = -1;
		out_status_text = 'post does not exist';
		RETURN;	
	end if;

	if v_posts_row.delete_status > 0 OR v_threads_row.delete_status > 0 THEN -- if they aren't deleted already
		out_status = -1;
		out_status_text = 'post does not exist.';
		RETURN;
	end if;

	SELECT COUNT(*) INTO v_rabid_report_count FROM report_src WHERE reporter_username=in_username AND ts > now() - INTERVAL '10m';
	if v_rabid_report_count > 6 THEN  -- if rabid report
		if ban_user(in_username, 1, '1m', NULL) > 0 THEN  -- softban for 1m
			out_status = -1;
			out_status_text = 'Please wait for a while before posting.';
			RETURN;
		end if;
	end if;
		
	PERFORM * FROM report_src WHERE reporter_username=in_username AND post_id=in_post_id AND consumed='f';  -- already reported check
	if FOUND THEN 
		out_status = -1;
		out_status_text = 'you have already reported for this post.';
		RETURN;
	end if;

	-- all checks passed. report request is processable now
	if v_posts_row.username=in_username THEN  -- if poster himself is the reporter
		INSERT INTO report_src (reporter_username, post_id, reported_username, reason, consumed)
		VALUES (in_username, in_post_id, v_posts_row.username, in_report_reason, 't');

		v_post_deletable = 1;
		v_delete_status_to_set = 4;
		out_status_text = 'delete';
	else
		INSERT INTO report_src (reporter_username, post_id, reported_username, reason, consumed)
		VALUES (in_username, in_post_id, v_posts_row.username, in_report_reason, 'f');


	end if;


	if v_post_deletable = 1 THEN
		if v_posts_row.id=v_posts_row.thread_id THEN -- if it is a thread
			UPDATE threads SET delete_status=v_delete_status_to_set WHERE post_id=in_post_id; -- will be 4 if post deleted by submitter

			-- try to undelete the last thread which was pruned (delete_status = 1 ) if it exists			
			SELECT post_id INTO v_undelete_thread_id FROM threads WHERE delete_status=1 ORDER BY bump_ts DESC LIMIT 1;
			if FOUND THEN
				UPDATE threads SET delete_status=0 WHERE post_id = v_undelete_thread_id;
				UPDATE posts SET delete_status=0 WHERE id = v_undelete_thread_id;
			end if;


		end if;

		UPDATE posts SET delete_status=v_delete_status_to_set WHERE id=in_post_id; 

	end if;

	out_status = 1;  -- all good

END;
$$ LANGUAGE plpgsql;

