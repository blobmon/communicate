#!/usr/bin/env python
# coding: utf-8 -*- 

import psycopg2
import psycopg2.extensions
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)

import time
import datetime
import re
import os
from app import app # circular import sorta

from flask import render_template, jsonify, request, session, redirect

from blobHandler import BlobHandler

import base64, hashlib

from PIL import Image

class Handler:

	def __init__ (self, connect=True) : 
		if connect == True :
			self.con = psycopg2.connect("dbname='{}' user='{}'".format(app.config['DB_NAME'], app.config['DB_ROLE']) )		
		else :
			self.con = None

	def __del__ (self) :		
		if self.con :
			self.con.close()
	
	def login(self) :
		user_id = Handler.user_id()

		username, session_id = self.get_username_and_session_id()		

		goto = '/'

		if 'goto' in request.args :
			if len(request.args['goto']) > 0 :
				goto = Handler.html_escape(request.args['goto'] )


		goto_hidden_input = "<input type='hidden' name='goto' value='{}'>".format(goto)		

		if request.method == 'GET' :
			return render_template('login_page.html', show_login=1, goto_hidden_input=goto_hidden_input)

		else :
			show_login = 0
			show_create_account = 0

			error_status = ''

			username = request.form['username'].lower()
			password = request.form['password']
			goto = Handler.html_escape(request.form['goto'])

			if len(goto) > 0 :
				goto_hidden_input = "<input type='hidden' name='goto' value='{}'>".format(goto)	

			input_type = request.form['input_type']

			if len(username) == 0 :				
				error_status = 'username is empty'

			elif len(password) == 0 :				
				error_status = 'password is empty'				

			elif len(password) > 100 :
				error_status = 'password is too long'


			if len(error_status) > 0 :
				if input_type == 'login' :
					return render_template('login_page.html', error_status=error_status, username_top=username, password_top=password, show_login=1, goto_hidden_input=goto_hidden_input)

				elif input_type == 'create_account' :
					return render_template('login_page.html', error_status=error_status, username_bot=username, password_bot=password, goto_hidden_input=goto_hidden_input)

			if input_type == 'login' :
				if Handler.check_username_validity(username) == False :
					error_status = 'username is invalid'
					return render_template('login_page.html', error_status=error_status, username_top=username, password_top=password, show_login=1, goto_hidden_input=goto_hidden_input)

				md5 = hashlib.md5()
				md5.update(password.encode('utf-8'))
				password_md5 = md5.hexdigest()

				cur = self.con.cursor()
				cur.execute("SELECT * FROM  user_login(%s, %s, %s)", (username, user_id, password_md5) )
				res = cur.fetchall()
				self.con.commit()

				row = res[0]

				if row[0] == -1 :
					error_status = row[1]
					return render_template('login_page.html', error_status=error_status, username_top=username, password_top=password, show_login=1, goto_hidden_input=goto_hidden_input)

				#all good. set session and return
				session.permanent = True
				app.permanent_session_lifetime = datetime.timedelta(days=500)
				session['username'] = username
				session['session_id'] = row[1]

				return redirect(goto)

			else :
				if Handler.check_username_validity(username) == False :
					error_status = 'username can only contain letters, digits, dashes and underscores and has to be less than 16 characters long'
					return render_template('login_page.html', error_status=error_status, username_bot=username, password_bot=password, goto_hidden_input=goto_hidden_input)

				md5 = hashlib.md5()
				md5.update(password.encode('utf-8'))
				password_md5 = md5.hexdigest()

				cur = self.con.cursor()
				cur.execute("SELECT * FROM create_account(%s,%s,%s)", (username, user_id, password_md5) )
				res = cur.fetchall()
				self.con.commit()

				row = res[0]

				if row[0] == -1 :
					error_status = row[1]
					return render_template('login_page.html', error_status=error_status, username_bot=username, password_bot=password, goto_hidden_input=goto_hidden_input)

				session.permanent = True
				app.permanent_session_lifetime = datetime.timedelta(days=500)
				session['username'] = username
				session['session_id'] = row[1]

				return redirect(goto)



	def handle_userpage(self, un) :
		if Handler.check_username_validity(un) == False :
			return 'invalid user', 400

		username, session_id = self.get_username_and_session_id()
		self.login_status = self.check_login_status(username, session_id)

		#preparing header elements		
		header = self.prepare_header_elements(username, '/user/{}/'.format(un) )

				
		cur = self.con.cursor()
		cur.execute("SELECT username, created_ts, last_activity_ts, about, info FROM  users WHERE username=%s", (un,) )
		res = cur.fetchall()

		
		if not res :
			return render_template('user_page.html', error_status='user not found', header=header), 404

		row = res[0]
		un, created_ts, last_activity_ts, about, info = row

		i_am = False
		if self.login_status == 1 and un == username :
			i_am = True

		created_ago = Handler.getAgeFromDatetime(created_ts)
		last_activity_ago = Handler.getAgeFromDatetime(last_activity_ts)
		if about == None :
			about = ''

		if i_am == False :
			about = Handler.format_post_message(about)

		return render_template('user_page.html', header=header, i_am=i_am, user=un, created_ago=created_ago, 
			last_activity_ago=last_activity_ago, about=about)


	def handle_update_user(self) :

		username, session_id = self.get_username_and_session_id()
		self.login_status = self.check_login_status(username, session_id)

		if self.login_status == -1 :
			return 'invalid user or not logged in', 400

		input_type = request.form['input_type']

		if input_type == 'update_about' :
			about = request.form['about']

			about_text,lc = Handler.clean_post_message(request.form['about'] )

			if len(about_text) > 2000 or lc > 20 :
				return 'text too long', 400

			#all good, now we actually update about_text

			cur = self.con.cursor()
			cur.execute("UPDATE users SET about=%s WHERE username=%s AND coalesce(about, '') != %s", 
				(about_text,username, about_text) )
			self.con.commit()

			return 'updated'

		return 'error input type', 400



	def logout(self) :
		goto = '/'

		if 'goto' in request.args :
			if len(request.args['goto']) > 0 :
				goto = Handler.html_escape(request.args['goto'] )

		username, session_id = self.get_username_and_session_id()

		if len(username) > 0 and len(session_id) > 0 :				
			cur = self.con.cursor()
			cur.execute("SELECT * FROM user_logout(%s,%s)", (username, session_id) )
			res = cur.fetchall()
			self.con.commit()

			row = res[0]
			if row[0] == 1 :
				session.clear()

		return redirect(goto)


	@staticmethod
	def check_username_validity(username) :		
		if len(username) > 16 :
			return False

		for c in username :
			o = ord(c)
			if ( o >= 48 and o <=57 ) or ( o >= 97 and o <= 122 ) or o == 95 or o == 45 :
				pass
			else :
				return False
		return True


	def handle_stream(self, new=False) :

		username, session_id = self.get_username_and_session_id()		

		self.login_status = self.check_login_status(username, session_id)
		
		cur = self.con.cursor()

		if new == False :
			cur.execute("SELECT * FROM get_stream(%s, %s, %s) ORDER BY bump_ts DESC", (self.login_status, username, session_id) )
		else :
			cur.execute("SELECT * FROM get_stream(%s, %s, %s) ORDER BY ts DESC", (self.login_status, username, session_id) )

		res = cur.fetchall()
		self.con.commit()  # because updation of last_activity_ts might have happened

		stream_list = []

		re_title_pattern = re.compile('^\[subject\](.*)\[\/subject\]$')

		for row in res :
			post_id, ts_utc, bump_ts_utc, post_count, un, text, thread_locked, thread_pinned, mod_post, blob_savename = row

			title = ''
			the_split = text.split('\n', 1)
			re_title_match = re_title_pattern.match(the_split[0])
			if re_title_match :
				title = re_title_match.group(1)

			href = '/thread/%s/' %(post_id)
			ago = Handler.getAgeFromDatetime(ts_utc)

			reply_count = post_count - 1
			reply_count_str = 'no replies'

			if reply_count > 1 :
				reply_count_str = '{} replies'.format(reply_count)
			elif reply_count == 1 :
				reply_count_str = '{} reply'.format(reply_count)


			thread_extra_status = ''

			if thread_locked == 1 :
				thread_extra_status += " | <span class='thread_locked' title='thread locked'>(locked)</span>"
			if thread_pinned == 1 :
				thread_extra_status += " | <span class='thread_pinned' title='sticky post'>(sticky)</span>"

			b = {'ts' : int(ts_utc), 'bump_ts' : int(bump_ts_utc), 'ago' : ago,
				'href':href, 'title':title, 'reply_count_str':reply_count_str, 'username': un,
				'thread_extra_status' : thread_extra_status }


			stream_list.append(b)


		#preparing header elements		
		header = self.prepare_header_elements(username, '/' )

		if new == False :
			page_title = '{}'.format(app.config['SITE_NAME'])
		else :
			page_title = '{} | Newest posts'.format(app.config['SITE_NAME'])
			

		return render_template('stream_page.html', header=header, page_title=page_title, stream_list=stream_list)

		
	def handle_about(self) :		
		username, session_id = self.get_username_and_session_id()
		
		self.login_status = self.check_login_status(username, session_id)

		#preparing header elements
		header = self.prepare_header_elements(username, '/about/' )

		return render_template( 'about_page.html', header=header )





	def get_username_and_session_id(self) :
		session_id = ''
		username = ''

		if 'session_id' in session and session['session_id'] is not None : 
			session_id = session['session_id']
		if 'username' in session and session['username'] is not None :
			username = session['username']

		return (username, session_id)

		

		
	
	def handle_post(self, thread_id) :
		user_id = Handler.user_id()

		username, session_id = self.get_username_and_session_id()
		
		self.login_status = self.check_login_status(username, session_id)

		cur = self.con.cursor()
		cur.execute("SELECT * FROM threads WHERE post_id=%s AND delete_status=0", (thread_id,) )
		res = cur.fetchall()

		if not res :
			return "<span style='font-family:monospace'>404 not found</span>", 404

		#preparing board_info vars
		threads_table_len = 10

		thread_row = res[0]		
		post_count = thread_row[4]
		posters_count = thread_row[5]
		thread_locked = thread_row[8]
		thread_pinned = thread_row[9]		

		#preparing posts stuff
		cur.execute("SELECT * FROM get_post(%s)", (thread_id,) )
		res = cur.fetchall()

		you_list = []
		you = False
		innards = []

		op_row = res[0]
		op = Handler.get_post_obj(op_row)

		#setting actual page title here		
		page_title = u'{} - {}'.format(app.config['SITE_NAME'], op['title'] )
		
		op['thread_locked'] = thread_locked
		op['thread_pinned'] = thread_pinned

		if self.login_status != -1 and op['username'] == username :
			you_list.append( op['post_id'] )
			you = True

		innards.append( self.get_post_html(op, you) )

		for row in res[1:] :
			you = False  # make sure to disable it for each item by default
			p = Handler.get_post_obj(row)
			if self.login_status != -1 and p['username'] == username :
				you_list.append( p['post_id'] )
				you = True				

			innards.append( self.get_post_html(p, you) )


		page_info =  {		
		'thread_id' : thread_id,
		'reply_count' : post_count-1,
		'posters_count' : posters_count,		
		'page_title' : page_title,
		'thread_locked' : thread_locked,
		'thread_pinned' : thread_pinned
		}

		#preparing header elements
		header = self.prepare_header_elements(username, '/thread/{}/'.format(thread_id) )

		return render_template( 'post_page.html', header=header,
			page_info=page_info, innards=innards, you_list=you_list.__str__() )





	def handle_banned(self) :
		username, session_id = self.get_username_and_session_id()
		
		self.login_status = self.check_login_status(username, session_id)

		cur = self.con.cursor()
		cur.execute("SELECT * FROM user_banned(%s, 1, 3, 't');" , (user_id,) )
		res = cur.fetchall()
		row = res[0]

		msg = 'You are not banned.'
		banned = ''

		if row[0] == 2 :
			msg = 'You are banned for spamming/flooding. Please check again later to see your ban status.'
			banned = 'banned'
		if row[0] == 3 :
			msg = 'You are banned for posting inappropriate content. Please check again later to see your ban status.'
			banned = 'banned'	

		return render_template('banned.html', msg=msg, banned=banned )


	def handle_start_thread(self) :
		user_id = Handler.user_id()

		username, session_id = self.get_username_and_session_id()

		self.login_status = self.check_login_status(username, session_id)

		if request.method == 'GET' :
			#preparing header elements
			header = self.prepare_header_elements(username, '/start_thread/' )

			if self.login_status == -1 :
				error_status = 'You must be logged in to start a new thread'
				return render_template('start_thread_page.html', header=header, error_status=error_status)			

			return render_template('start_thread_page.html', header=header )

		if request.method == 'POST' :
			if self.login_status == -1 :
				return 'please login to start a thread', 400

			subject = Handler.single_linify(request.form['subject']).strip()
			text, text_line_count = Handler.clean_post_message(request.form['text'])

			blob_name = blob_type = blob_info = None
			image_exists = False
			blob_handler = None

			if len(subject) > 140 or len(text) > 2000 or text_line_count > 40 :
				return 'content too long', 400   # TODO can hard ban him here for 1 entire day

			if len(subject) == 0 :
				return 'subject cannot be empty', 400

			if len(text) == 0 and (request.files or request.files['image']) == False :
				return 'empty content', 400

			#attaching subject with text field			
			text = u'[subject]{}[/subject]\n{}'.format(subject, text)

			if request.files and request.files['image'] :
				image_exists = True
				blob_handler = BlobHandler(request.files['image'])
				img_verify_result = blob_handler.verify(app.config['UPLOAD_FOLDER'])		
				if img_verify_result != 1 :
					return img_verify_result[0], 400
				blob_name = blob_handler.savename_utc
				blob_type = blob_handler.save_type
				blob_info_fmt = u'{{"blob_filename" : "{}", "blob_filesize" : "{}", "blob_dimension" : "{}"}}'

				blob_handler.filename = blob_handler.filename.replace('"', '\\"')
				blob_info = blob_info_fmt.format( blob_handler.filename, blob_handler.filesize, 'x'.join( str(v) for v in blob_handler.dimension) )


			cur = self.con.cursor()
			cur.execute("SELECT * FROM start_thread(%s, %s, %s, %s, %s, %s, %s);" , 
				(username, user_id, session_id, text, blob_name, blob_type, blob_info) )

			res = cur.fetchall()
			row = res[0]

			#note : these two commands should be in this order
			if row[0] > 0 and blob_handler is not None :  # save if all good from db
				blob_handler.save()

			self.con.commit()  #commit the statement ( even if status < 0 because ban might have happened )

			if row[0] <= 0 :				
				return row[1], 400

			post_id = row[0]
			redirect_url = '/thread/%s/' %(post_id)

			#return 'post created : %s' %(post_id)
			returnable = {'post_id' : post_id, 'redirect_url' : redirect_url}
			return jsonify(returnable)


	def handle_add_post(self) :
		user_id = Handler.user_id()

		username, session_id = self.get_username_and_session_id()

		if len(username) == 0 or len(session_id) == 0 :
			return 'not logged in', 400

		thread_id = request.form['thread_id']		
		text, text_line_count = Handler.clean_post_message(request.form['text'])
		bump = 1 if request.form['bump'] == 'true' else 0

		blob_name = blob_type = blob_info = None

		image_exists = False
		blob_handler = None		

		try :
			thread_id = int( thread_id )
		except ValueError :
			return 'Major server malfunction. Overheat detected.', 400

		if len(text) > 2000 or text_line_count > 40:
			return 'bad request' , 400   # TODO can hard ban him here for 1 entire day

		
		if request.files and request.files['image'] :
			image_exists = True
			blob_handler = BlobHandler(request.files['image'])
			img_verify_result = blob_handler.verify(app.config['UPLOAD_FOLDER'])		
			if img_verify_result != 1 :
				return img_verify_result[0], 400
			blob_name = blob_handler.savename_utc
			blob_type = blob_handler.save_type
			blob_info_fmt = u'{{"blob_filename" : "{}", "blob_filesize" : "{}", "blob_dimension" : "{}"}}'

			blob_handler.filename = blob_handler.filename.replace('"', '\\"')
			blob_info = blob_info_fmt.format( blob_handler.filename, blob_handler.filesize, 'x'.join( str(v) for v in blob_handler.dimension) )

		if len(text) == 0 and image_exists == False :
			return 'empty content', 400  # bannable again

		#saving
		cur = self.con.cursor()

		cur.execute("SELECT * FROM start_post(%s, %s, %s, %s, %s,  %s, %s, %s, %s )",
			(thread_id, username, user_id, session_id, text, blob_name, blob_type, blob_info, bump) )

		res = cur.fetchall()
		row = res[0]

		if image_exists == True and row[0] > 0 : #if image uploaded and all good from db
			blob_handler.save()
		self.con.commit()

		if row[0] <= 0 :			
			return row[1], 400

		post_id = row[0]

		return 'post created : %s' %(post_id)

	def handle_update_post(self) :
		thread_id = request.form['thread_id']
		last_id = request.form['last_id']
		user_id = Handler.user_id()

		username, session_id = self.get_username_and_session_id()
		
		self.login_status = self.check_login_status(username, session_id)
		
		try :
			thread_id = int( thread_id )
			last_id = int( last_id )
		except ValueError :
			return 'Major server malfunction. Overheat detected.', 400

		#db work. check if thread exists and is not deleted

		cur = self.con.cursor()
		cur.execute("SELECT delete_status, posters_count, post_count FROM threads WHERE post_id=%s", (thread_id,) )
		threads_res = cur.fetchall()

		if not threads_res :
			return 'error', 404  # thread_id not valid
		threads_row = threads_res[0]

		thread_status = threads_row[0]
		thread_posters_count = threads_row[1]
		thread_reply_count = threads_row[2] - 1

		if thread_status != 0 :
			return 'thread was pruned or deleted', 404

		cur.execute( "SELECT * FROM get_update(%s,%s)", (thread_id,last_id) )
		res = cur.fetchall()

		you_list = []
		you = False
		posts = []

		f = 0  # first row to consider
		if res[0][0] == last_id :
			f = 1
		for row in res[f:] :
			p = Handler.get_post_obj(row)
			if self.login_status != -1 and p['username'] == username :
				you_list.append( p['post_id'] )
				you = True
			posts.append( self.get_post_html(p, you, True) )

		to_return = {'sv_utc' : int(time.time()), 'you_list' : you_list, 'posts' : posts, 'posters_count' : thread_posters_count, 'reply_count' : thread_reply_count}

		return jsonify(to_return)




	def handle_report_post( self ) :
		user_id = Handler.user_id()

		username, session_id = self.get_username_and_session_id()

		if len(username) == 0 or len(session_id) == 0 :
			return 'not logged in', 400


		thread_id = request.form['thread_id']
		post_id = request.form['post_id']
		reason = request.form['reason'].strip()		

		try :
			thread_id = int( thread_id )
			post_id = int( post_id )
		except ValueError :
			return 'Major server malfunction. Overheat detected.', 400


		if reason != 'spam' and reason != 'illegal' :
			return '%s is not a valid reason' %reason, 400

		reason = 1 if reason == 'spam' else 2		

		#all good. saving
		cur = self.con.cursor()		
		cur.execute("SELECT * FROM report_post(%s, %s, %s, %s, %s );" , (username, session_id, thread_id, post_id, reason) )
		self.con.commit()

		res = cur.fetchall()
		row = res[0]

		if row[0] <= 0 :
			return row[1], 400

		if row[1] == 'delete' :
			return 'deleted post No.%s' %post_id
		else :		
			return 'report submitted for post No.%s' %post_id


	def handle_mod_logs( self ) :		
		
		page_to_show = 1
		log_id_to_show = 1

		MAX_POSTS = 100


		if 'page' in request.args :
			if Handler.representsInt(request.args['page']) :
				page_to_show = int(request.args['page'])
				if page_to_show > 100 :
					page_to_show = 100
				if page_to_show < 1 :
					page_to_show = 1

		if 'log_id' in request.args :
			if Handler.representsInt(request.args['log_id']) :
				log_id_to_show = int(request.args['log_id'])
				if log_id_to_show > 1000000 :
					log_id_to_show = 1000000
				if log_id_to_show < 1 :
					log_id_to_show = 1


		cur = self.con.cursor()

		if 'page' in request.args or 'log_id' not in request.args :

			offset = (page_to_show-1)*MAX_POSTS

			query_str = 'SELECT * FROM moderator_log ORDER BY ts DESC LIMIT {} OFFSET %s'.format(MAX_POSTS)

			query = cur.execute(query_str, (offset,) )
			res = cur.fetchall()

			logs = []

			for log in res :
				idee, modname, ts, action, info = log

				logs.append( Handler.format_mod_log(log) )


			#navigation prepare			
			if page_to_show == 100 or len(logs) < MAX_POSTS :
				navigation_after_str = ''
			else :
				navigation_after_str = "<a href='/mod_logs?page={}'>page{}&gt;&gt;</a>".format(page_to_show+1, page_to_show+1)

			if page_to_show == 1 :
				navigation_before_str = ''
			else :
				navigation_before_str = "<a href='/mod_logs?page={}'>&lt;&lt;page{}</a>".format(page_to_show-1, page_to_show-1)

			middle_separation = '|'		
			if len(navigation_after_str) == 0 or len(navigation_before_str) == 0 :
				middle_separation = ''

			navigation = '{} {} {}'.format(navigation_before_str, middle_separation, navigation_after_str)

			return render_template('mod_logs.html', logs=logs, navigation=navigation)
			



		if 'log_id' in request.args :
			cur.execute('SELECT * FROM moderator_log WHERE id=%s', (log_id_to_show,) )

			res = cur.fetchall()

			if not res :
				return "<span style='font-family:monospace'>404 not found</span>", 404

			log = Handler.format_mod_log(res[0])

			return render_template('mod_logs.html', log=log, log_id_mode=True)

		
		return 'Critical failure detected. Server shutting down because of this query. Unauthorized access.', 404


	#mod methods below

	def handle_mod_lounge(self) :

		username, session_id = self.get_username_and_session_id()
		
		mod_status = self.check_login_status_and_mod_status(username, session_id)

		if mod_status == -1 :
			return 'not moderator', 400
		
		return render_template('mod_lounge.html', mod_username=username)


	def handle_mod_report_list(self) :
		username, session_id = self.get_username_and_session_id()

		mod_status = self.check_login_status_and_mod_status(username, session_id)

		if mod_status == -1 :
			return 'not moderator', 400


		cur = self.con.cursor()	
		cur.execute("SELECT report_src.post_id, posts.thread_id, report_src.reason FROM report_src INNER JOIN posts ON posts.id=report_src.post_id WHERE posts.delete_status=0 AND report_src.ts > now()-interval'90 days' AND report_src.consumed='f' ORDER BY report_src.post_id")
		res = cur.fetchall()
	
		obj = {}

		for row in res :
			post_id, thread_id, reason = row

			post_id_str = '%d' %post_id

			if post_id == thread_id :                 
				post_display_str = '/%d' %(post_id)
			else :
				post_display_str = '/%d#%d' %(thread_id,post_id)

			post_url = '/thread/{}#p{}'.format(thread_id,post_id)

			idx = 0
			if reason == 2 :
				idx = 1;

			if post_id_str not in obj :
				obj[post_id_str] = {'report_tpl' : [0,0], 'display_str' : post_display_str, 'post_url' : post_url }

			obj[post_id_str]['report_tpl'][idx] += 1

		lst = obj.items()
		lst.sort( key=lambda item : int(item[0]), reverse=True )

		lines = []
		for row in lst :
			post_id, post_obj = row
			report_tpl = post_obj['report_tpl']
			str_fmt = u"<tr> <td class='post_num'><a href='{}' target='_blank'>{}</a></td> <td>{} | {}</td></tr>"
			lines.append( str_fmt.format(post_obj['post_url'], post_obj['display_str'], report_tpl[0], report_tpl[1]) )

		reports = '\n'.join(lines)
		return render_template('mod_report_list.html', reports=reports)


	def handle_mod_recent_posts(self) :
		username, session_id = self.get_username_and_session_id()

		mod_status = self.check_login_status_and_mod_status(username, session_id)

		if mod_status == -1 :
			return 'not moderator', 400


		#all good, get and render page...

		MAX_POSTS = 100

		page = 1
		if 'page' in request.args :
			try :
				page = int(request.args['page'])
				if page < 1 :
					page = 1
				if page > 100 :
					page = 100
			except ValueError :
				pass

		offset = (page-1)*MAX_POSTS		

		cur = self.con.cursor()
		cur.execute('SELECT * FROM posts_utc ORDER BY utc DESC LIMIT %s OFFSET %s', (MAX_POSTS, offset) )
		res = cur.fetchall()

		posts = []

		for row in res :
			post_obj = Handler.get_post_obj(row)
			post_html = self.get_post_html(post_obj, False, False, True)
			posts.append( post_html )


		''' navigation logic
		if not MAX_POSTS results returned, dont show next
		if page is 100, dont show next
		if page is 1, dont show prev
		'''
		
		if page == 100 or len(posts) < MAX_POSTS :
			navigation_after_str = ''
		else :
			navigation_after_str = "<a href='/mod_recent_posts?page={}'>page{}&gt;&gt;</a>".format(page+1, page+1)

		if page == 1 :
			navigation_before_str = ''
		else :
			navigation_before_str = "<a href='/mod_recent_posts?page={}'>&lt;&lt;page{}</a>".format(page-1, page-1)

		middle_separation = '|'		
		if len(navigation_after_str) == 0 or len(navigation_before_str) == 0 :
			middle_separation = ''

		navigation = '{} {} {}'.format(navigation_before_str, middle_separation, navigation_after_str)		

		return render_template('mod_recent_posts.html', posts=posts, navigation=navigation)  


	def handle_mod_update_post(self) :
		username, session_id = self.get_username_and_session_id()

		mod_status = self.check_login_status_and_mod_status(username, session_id)

		if mod_status == -1 :
			return 'not moderator', 400
		
		#if session is valid

		if request.method == 'GET' :
			return render_template('mod_update_post.html', mod_username=username )		
		
		#when request.method is POST and session is valid : 
		cur = self.con.cursor()

		if 'load_post' in request.form :
			post_id = int(request.form['post_id']) 
			
			cur.execute('SELECT * FROM posts_utc WHERE id=%s', (post_id,) )
			res = cur.fetchall()
			if not res :
				return 'post not found', 404


			post_row = res[0]
			post_obj = Handler.get_post_obj(post_row)

			#fetch the thread
			cur.execute('SELECT * FROM threads WHERE post_id=%s', (post_obj['thread_id'],) )
			res = cur.fetchall()
			
			thread_row = res[0]

			if post_obj['is_op'] == 1:
				post_obj['thread_locked'] = thread_row[8]
				post_obj['thread_pinned'] = thread_row[9]

			post_html = self.get_post_html(post_obj, False, False, True)

			returnable = {'post_id': post_obj['post_id'], 'thread_id' : post_obj['thread_id'], 
						'delete_status' : post_obj['delete_status'], 'html' : post_html }
			if 'thread_locked' in post_obj :
				returnable['lock'] = post_obj['thread_locked']
			if 'thread_pinned' in post_obj :
				returnable['pin'] = post_obj['thread_pinned']

			return jsonify(returnable)

		if 'delete_post' in request.form :

			try :
				post_id = int(request.form['post_id'])

				delete_reason = request.form['reason']
				duration = int(request.form['duration'])

				delete_subsequent = int(request.form['delete_subsequent'])
				unbump = int(request.form['unbump'])
				delete_permanently = int(request.form['delete_permanently'])

				delete_reason_text = '\\n'.join(request.form['delete_reason_text'].splitlines() )
				delete_reason_text = delete_reason_text.replace('"', '\\"')  #because it is going inside json
			except ValueError :
				return 'major server malfunction detected!', 400  #exaggeration 

			if delete_reason != 'spam' and delete_reason != 'illegal' :
				return 'delete reason is improper', 400

			if len(delete_reason_text) < 4 or len(delete_reason_text) > 400 :
				return 'delete reason text is wrong', 400
			if duration > 400 :
				return "can't ban the user for so long", 400


			duration_text = '{}h'.format(duration)

			
			cur.execute('SELECT * FROM moderator_delete_and_ban_post(%s,%s,%s,%s,%s,%s,%s,%s,%s)', 
				(username, session_id, post_id, delete_reason, duration_text, delete_subsequent,unbump,delete_permanently, delete_reason_text) )
			res = cur.fetchall() 
			self.con.commit()

			row = res[0]

			if row[0] == -1 :
				return row[1], 400
			else :
				returnable = { 'post_id' : post_id, 'duration' : duration }
				return jsonify(returnable)

		elif 'undelete_post' in request.form :
			try :
				post_id = int(request.form['post_id'])
				undelete_subsequent = int(request.form['undelete_subsequent'])
				unban = int(request.form['unban'])
			except ValueError :
				return 'major server malfunction detected!', 400

			cur.execute('SELECT * FROM moderator_undelete_post(%s, %s, %s, %s, %s)',
				(username, session_id, post_id, undelete_subsequent, unban) )
			res = cur.fetchall()
			self.con.commit()

			row = res[0]

			if row[0] == -1 :
				return row[1], 400
			else :
				returnable = {'post_id' : post_id}
				return jsonify(returnable)

		elif 'update_thread' in request.form :
			try :
				thread_id = int(request.form['thread_id'])
				pin = int(request.form['pin'])
				lock = int(request.form['lock'])

			except ValueError :
				return 'major server malfunction detected!', 400

			cur.execute('SELECT * FROM moderator_update_thread(%s,%s,%s,%s,%s)',
				(username, session_id, thread_id, lock, pin) )
			res = cur.fetchall()
			self.con.commit()

			row = res[0]

			if row[0] == -1 :
				return row[1], 400
			else :
				returnable = {'thread_id' : thread_id}
				return jsonify(returnable)



	#other stuff below

	def check_login_status(self, username, session_id) :
		if len(username) == 0 or len(session_id) == 0 :
			return -1


		cur = self.con.cursor()
		cur.execute("SELECT * FROM check_login_status(%s, %s)", (username, session_id) )
		res = cur.fetchall()

		return res[0][0]


	def check_login_status_and_mod_status(self, username, session_id) :
		if len(username) == 0 or len(session_id) == 0 :
			return -1

		cur = self.con.cursor()
		cur.execute("SELECT * FROM check_login_status_and_mod_status(%s,%s)", (username, session_id) )
		res = cur.fetchall()

		return res[0][0]


	@staticmethod
	def representsInt(s):
		try: 
			int(s)
			return True
		except ValueError:
			return False

	
	def get_post_html( self, post_obj, you, get_inside_only=False, get_for_mod=False ) :

		op_title_fmt = u"<span class='title'>{}</span><br>"

		post_info_fmt = u"{}" \
				"<div class='post_info'>"\
				"{} <a class='username' href='/user/{}/'>{}</a> | " \
				"<span class='time' data-utc='{}'>{} ago</span> | " \
				"{}"\
				"<span><a href='#p{}'>No.</a><a class='post_num'>{}</a></span> " \
				"{}<br>" \
				"<span class='qbl' id='qbl{}'>replies: </span>" \
				"</div>"

		if get_for_mod == True :
			post_info_fmt = u"{}" \
				"<div class='post_info'>"\
				"{} <a class='username' href='/user?id={}'>{}</a> | " \
				"<span class='time'>{} ago</span> | " \
				"<span><a href='/thread/{}/#p{}'>&gt;&gt;/{}/#{}</a></span> " \
				" {}" \
				"</div>"

		file_stuff_fmt = u"<div class='file_info'>" \
						"File: <a href='/static/images/{}' target='_blank'>{}</a>" \
						" ({}, {})" \
						"</div>" \
						"<a class='file_thumb' href='/static/images/{}' target='_blank'>" \
						"<img src='/static/images/{}' alt='{}'/>" \
						"</a>" 


		
		#post_div_fmt = u"<div class='post_container'> <div class='post {}' id='p{}'>{}</div> </div>"
		post_div_container_fmt = u"<div class='post_container'>{}</div>"
		post_div_inside_fmt = u"<div class='post {}' id='p{}'>{}</div>"

		post_msg_fmt = u"<blockquote class='post_message'>{}</blockquote>"
		post_msg_deleted_fmt = u"<blockquote class='post_message deleted'>{}</blockquote>"

		## building actual html here
		
		post_deleted = post_obj['deleted']
		mod_post = post_obj['mod_post']
		is_op = post_obj['is_op']
		title = post_obj['title'] if is_op else ''

		blob_savename = blob_savename_s = blobname = None
		if 'blob_savename' in post_obj : 
			blob_savename = post_obj['blob_savename']
			blob_savename_s = post_obj['blob_savename_s']
			blobname = post_obj['blob_filename']
			blob_size = post_obj['blob_filesize']
			blob_dim = post_obj['blob_dimension']		
		
		username = Handler.wbrify_line(post_obj['username'])
		text = post_obj['text']
		ago = post_obj['ago']
		utc  = post_obj['utc']
		post_id = post_obj['post_id']
		thread_id = post_obj['thread_id']

		post_extra_info = '' #used by get_for_mod case only

		if post_deleted :
			if get_for_mod == False :
				if post_obj['delete_status'] == 4 :
					post_msg = post_msg_deleted_fmt.format('[post deleted by submitter]')
				else :
					post_msg = post_msg_deleted_fmt.format('[post deleted]')

			else :
				hhh = 'by submitter'
				if post_obj['delete_status'] == 3 :
					hhh = 'by mod'
				elif post_obj['delete_status'] == 10 :
					hhh = 'by mod - hard'
				post_extra_info = "<span class='deleted_post'>[post deleted {}]</span>".format(hhh)
				post_msg = post_msg_fmt.format(post_obj['text'])

		else :
			post_msg = post_msg_fmt.format(post_obj['text'])
		

		title_span = op_title_fmt.format(title) if is_op else ''
		username_prefix = 'by '	if is_op else ''

		thread_extra_status = ''
		if is_op :
			if 'thread_locked' in post_obj and post_obj['thread_locked'] == 1 :
				thread_extra_status += " | <span class='thread_locked' title='thread locked'>(locked)</span>"
			if 'thread_pinned' in post_obj and post_obj['thread_pinned'] == 1 :
				thread_extra_status += " | <span class='thread_pinned' title='sticky post'>(sticky)</span>"		
		

		if get_for_mod == False :

			file_info = '' if ( post_deleted or blob_savename is None ) else file_stuff_fmt.format(
				blob_savename, blobname, blob_size, blob_dim, blob_savename, blob_savename_s, blob_size	)

			#handling report link
			if self.login_status == 1 :
				report_inner_text = 'delete' if you else 'report'
				report_txt = "<a class='report'>{}</a> | ".format(report_inner_text)
			else :
				report_txt = ''  #don't show it if he isn't logged in
			post_info = post_info_fmt.format( title_span, username_prefix, username, username, utc, ago, report_txt, post_id, post_id, thread_extra_status, post_id )
		else :
			file_info = '' if ( blob_savename is None ) else file_stuff_fmt.format(
				blob_savename, blobname, blob_size, blob_dim, blob_savename, blob_savename_s, blob_size	)
			post_info = post_info_fmt.format( title_span, username_prefix, username, username, ago, thread_id, post_id, thread_id, post_id, post_extra_info )

		op_post_class = "op_post" if is_op else ''

		inn = [post_info, file_info, post_msg]

		post_div_inside = post_div_inside_fmt.format(op_post_class, post_id, ''.join( inn ))

		if get_inside_only == True :
			return post_div_inside
		else :
			return post_div_container_fmt.format( post_div_inside )



	@staticmethod
	def get_post_obj( row ) :
		post_obj = {}
		post_obj['post_id'] = row[0]		
		post_obj['thread_id'] = row[1]
		post_obj['username'] = row[2]
		post_obj['user_id'] = row[3]



		utc = int(row[4])
		post_obj['utc'] = utc
		post_obj['ago'] = Handler.getAgeFromDatetime(utc)		

		post_obj['is_op'] = row[1] == row[0]

		text_raw = row[5]
		re_title_pattern = re.compile('^\[subject\](.*)\[\/subject\]$')

		
		if post_obj['is_op'] :
			the_split = row[5].split('\n', 1)
			first_line = the_split[0]			
			re_title_match = re_title_pattern.match(first_line)
			if re_title_match :
				post_obj['title'] = Handler.wbrify_line(re_title_match.group(1))
				if len(the_split) > 1 :
					text_raw = the_split[1]
				else :
					text_raw = ''
			else :
				post_obj['title'] = ''

		post_obj['text_raw'] = text_raw
		post_obj['text'] = Handler.format_post_message( text_raw )

		post_obj['delete_status'] = row[9]
		post_obj['deleted'] = row[9] > 0
		post_obj['mod_post'] = row[10] > 0

		if row[6]:  #if blob_savename field is not null			
			post_obj['blob_savename'] = "%s.%s"  %(row[6], row[7])
			post_obj['blob_savename_s'] = "%s_s.%s"  %(row[6], 'jpg')

			blob_info = row[8]			
			blob_filename = blob_info['blob_filename']
			post_obj['blob_filesize'] = blob_info['blob_filesize']
			post_obj['blob_dimension'] = blob_info['blob_dimension']

			blob_filename_trimmed = (blob_filename[:30] + '(...)') if len(blob_filename)>35 else blob_filename
			blob_filename_formatted = Handler.html_escape( u'{}.{}'.format(blob_filename_trimmed, row[7]) )
			post_obj['blob_filename'] = blob_filename_formatted

		return post_obj

	@staticmethod
	def clean_post_message(text):
		text = text.strip()

		lines = []
		for line in text.splitlines():
			#lines.append(line.strip())
			lines.append(line)
		line_count = len(lines)
		return '\n'.join(lines), line_count
		return text

	@staticmethod
	def html_escape(str) :
		html_escape_table = {
		 "&": "&amp;",
		 '"': "&#34;",
		 "'": "&#39;",
		 ">": "&gt;",
		 "<": "&lt;",
		 }
		return "".join(html_escape_table.get(c,c) for c in str)  #escape html entities


	# @staticmethod
	# def html_decode(s):
	#     """
	#     https://stackoverflow.com/questions/275174/how-do-i-perform-html-decoding-encoding-using-python-django
	#     Returns the ASCII decoded version of the given HTML string. This does
	#     NOT remove normal HTML tags like <p>.
	#     """
	#     htmlCodes = (
	#             ("'", '&#39;'),
	#             ('"', '&quot;'),
	#             ('>', '&gt;'),
	#             ('<', '&lt;'),
	#             ('&', '&amp;')
	#         )
	#     for code in htmlCodes:
	#         s = s.replace(code[1], code[0])
	#     return s

 	
	@staticmethod
	def format_post_message(text):

		quote_pattern = re.compile(r'>{2,5}(\d{3,12})')

		url_pattern = re.compile(r"https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}(?:\/[-a-zA-Z0-9@:%_\/.+~#?&=]*)?", re.IGNORECASE)

		text = text.strip()

		lines = []

		for line in text.splitlines():
			words = line.split()

			greentext_line = False

			for i in range(len(words)) :
				wo = words[i]  #word original
				wm = None #word modified			

				if wo.startswith('http') :
					url_match = url_pattern.match(wo)
					if url_match :
						url_str = url_match.string[url_match.start(0):url_match.end(0)]
						leftovers = Handler.wbrify_htmlify( url_match.string[url_match.end(0):] )

						if url_str[-1] == '.' :
							url_str = url_str[:-1]
							leftovers = '.' + leftovers

						wm = u"<a href='{}' target='_blank'>{}</a>{}".format(Handler.html_escape(url_str), Handler.wbrify_htmlify(url_str), leftovers )
						

				elif wo.startswith('>') :
					if wo.startswith('>>') :
						quote_match = quote_pattern.match(wo)
						if quote_match :
							quote_gt_str = Handler.html_escape(quote_match.string[quote_match.start(0):quote_match.start(1)] )
							quote_numb_str = quote_match.string[quote_match.start(1):quote_match.end(1)]
							leftovers = '<wbr>' + Handler.wbrify_htmlify( quote_match.string[quote_match.end(1):] )

							wm = u'<a class="quote_no" href="#p{}">{}{}</a>{}'.format(quote_numb_str, quote_gt_str, quote_numb_str, leftovers)


						if wm == None and i == 0 :
							greentext_line = True

					elif i == 0 :
						greentext_line = True
				
				
				if wm is None :
					wm = Handler.wbrify_htmlify(wo)

				words[i] = wm

			new_line = ' '.join(words)

			if greentext_line == True :
				new_line = u'<span class=\'quote_txt\'>{}</span>'.format(new_line)
				
			lines.append(new_line)

		return '<br>'.join(lines)



	#@staticmethod
	#def wbrify(str) :
	#	return '<wbr>'.join( [ str[0+x:35+x] for x in range(0, len(str), 35) ] )

	@staticmethod
	def format_mod_log(log) :
		idee, mod_username, ts, action, info = log

		duration = Handler.getAgeFromDatetime(ts)

		mod_log_href = '/mod_logs/?log_id={}'.format(idee)
		action_line_fmt = u"action : <span class='action'>{{}}</span> | {} ago | <a href='{}' target='_blank'>(link)</a>"\
						.format(duration, mod_log_href)

		mod_line = u"<span>mod : {} </span>".format(mod_username)


		lines = []

		if action == 'login' or action == 'logout' :
			lines.append(action_line_fmt.format(action) )
			lines.append('<br>')
			lines.append(mod_line)

		elif action == 'start_post' :
			lines.append(action_line_fmt.format('start post'))
			lines.append('<br>')
			lines.append(mod_line)
			lines.append('<br><br>')
			lines.append(Handler.get_post_formatted_line_from_mod_log(info, True) )

		elif action == 'delete_post' :
			action_str = 'delete post'
			if info['delete_permanently'] == 1 :
				action_str += ' (hard)'
			lines.append(action_line_fmt.format(action_str) )
			lines.append('<br>')
			lines.append(mod_line)
			lines.append('<br><br>')
			lines.append(Handler.get_post_formatted_line_from_mod_log(info, False) )
			lines.append('<br>')

			reason = 'spamming / flooding'
			if info['delete_reason'] == 'illegal' :
				reason = 'illegal / improper content'

			reason_text = Handler.wbrify_line(info['delete_reason_text'] )

			lines.append('<span>reason : {}</span><br>'.format(reason) )
			lines.append(u'<span>reason text : {}</span><br>'.format(reason_text) )

			extra_actions_list = []
			if info['delete_subsequent'] == 1 :
				extra_actions_list.append('subsequent posts by poster deleted')
			if info['unbump'] == 1 :
				extra_actions_list.append('thread unbumped')
			if info['ban_duration'] != '0h' :
				extra_actions_list.append("poster was banned for '{}'".format(info['ban_duration'] ) )
			
			if len(extra_actions_list) > 0 :
				extra_actions = '<br><span>extra actions : {}</span>'.format(' and '.join(extra_actions_list) )
				lines.append(extra_actions)

			

		elif action == 'undelete_post' :
			lines.append(action_line_fmt.format('undelete post') )
			lines.append('<br>')
			lines.append(mod_line)
			lines.append('<br><br>')
			lines.append(Handler.get_post_formatted_line_from_mod_log(info, True) )

			extra_actions_list = []
			if info['unban'] == 1:
				extra_actions_list.append('poster was unbanned')
			if info['undelete_subsequent'] == 1 :
				extra_actions_list.append('subsequent posts were undeleted')

			if len(extra_actions_list) > 0 :
				extra_actions = '<br><br><span>extra actions : {}</span>'.format(' and '.join(extra_actions_list) )
				lines.append(extra_actions)


		elif action == 'update_thread' :
			lines.append(action_line_fmt.format('update thread') )
			lines.append('<br>')
			lines.append(mod_line)
			lines.append('<br><br>')
			lines.append(Handler.get_post_formatted_line_from_mod_log(info, True) )

			extra_actions_list = []
			if 'pin' in info :
				if info['pin'] == 1 :
					extra_actions_list.append('pinned')
				elif info['pin'] == 0 :
					extra_actions_list.append('unpinned')
			if 'lock' in info :
				if info['lock'] == 1 :
					extra_actions_list.append('locked')
				elif info['lock'] == 0 :
					extra_actions_list.append('unlocked')

			if len(extra_actions_list) > 0 :
				extra_actions = '<br><br><span>thread was {}</span>'.format(' and '.join(extra_actions_list) )
				lines.append(extra_actions)

		return u' '.join(lines)

	@staticmethod
	def get_post_formatted_line_from_mod_log(info, hrefify=True) :		

		post_element = ''
		thread_element = ''

		href_post = True	

		if 'post_id' in info :
			if info['thread_id'] == info['post_id'] :		
				href_post = False
		else :
			href_post = False
		

		if hrefify == True :
			if href_post == False :	
				thread_element = "<a href='/thread/{}/' target='_blank'>thread : {}</a>"\
						.format( info['thread_id'], info['thread_id'] )
			else :
				post_element = "<a href='/thread/{}/#p{}' target='_blank'>post : {}</a> | "\
						.format( info['thread_id'], info['post_id'], info['post_id'] )


		if href_post == True and len(post_element) == 0 :
			post_element = "post : {} | ".format(info['post_id'] )

		if len(thread_element) == 0 :
			thread_element = "thread : {}".format(info['thread_id'] )

		

		return '<span>{}{}</span>'.format(post_element, thread_element)

	
	def prepare_header_elements(self, username, context='/' ) :

		login_goto = context
		logout_goto = context		

		home_element = "<a href='/' class='home'>{}</a>".format(app.config['SITE_NAME'])
		newer_element = "<a href='/new/'>new</a>"
		about_element = "<a href='/about/'>about</a>"

		headerleft_elements_list = [newer_element, about_element]		

		if self.login_status != -1 and context.startswith('/start_thread/') == False :
			headerleft_elements_list.append("<a href='/start_thread/'>start&nbsp;thread</a>")

		#setting gotos
		if context.startswith('/start_thread/') :
			logout_goto = '/'
		

		headerright_elements_list = []		

		if self.login_status != -1 :
			headerright_elements_list.append("<a href='/user/{}/'>{}</a>".format(username,username) )
			headerright_elements_list.append("<a href='/logout?goto={}'>logout</a>".format(logout_goto) )
		else :
			headerright_elements_list.append("<a href='/login/?goto={}'>login</a>".format(login_goto) )

		headerleft_elements = ' | '.join(headerleft_elements_list)
		headerright_elements = ' | '.join(headerright_elements_list)


		header = {
		'login_status' : self.login_status,
		'site_name' : app.config['SITE_NAME'],
		'home_element' : home_element,
		'headerleft_elements' : headerleft_elements,
		'headerright_elements' : headerright_elements
		}

		return header


	@staticmethod
	def getAgeFromDatetime(taim) :
		if type(taim) == datetime.datetime :			
			delta = datetime.datetime.utcnow() - taim
			s = int(delta.total_seconds())

		else :
			delta = time.time() - taim
			s = int(delta)

		if(s < 0) :
			return '0 second'
		if(s == 1) :
			return '1 second'
		if(s < 60) :
			return str(s) + ' seconds'
		if(s < 60*60) :
			minutes = int(s/60)
			r = '{} minute'.format(minutes)
			if minutes > 1 :
				r += 's'
			return r
		if(s < 24*60*60) :
			hours = int(s/(60*60))
			r = '{} hour'.format(hours)

			if hours > 1 :
				r += 's'

			return r

		days = int(s/(24*60*60))
		r = '{} day'.format(days)

		if days > 1 :
			r += 's'

		return r

	@staticmethod
	def wbrify_htmlify(str) :		
		return '<wbr>'.join( [ Handler.html_escape( str[0+x:35+x] ) for x in range(0, len(str), 35) ] )


	@staticmethod
	def wbrify_line(txt) :
		lines = []
		for line in txt.splitlines():
			words = line.split()
			for i in range(len(words)) :				
				if len(words[i]) > 35 :
					words[i] = Handler.wbrify_htmlify(words[i])

			lines.append(' '.join(words))
		return ' '.join(lines)

	@staticmethod
	def single_linify(txt) :
		lines = txt.splitlines()
		return ' '.join(lines)


	@staticmethod
	def user_id(): 
		strr = app.config['IP_HASH_STR'].format(request.remote_addr)
		sha256 = hashlib.sha256()
		sha256.update(strr)
		return base64.b64encode(sha256.digest())[:10]



		
			
