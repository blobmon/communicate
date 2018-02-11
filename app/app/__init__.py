#!/usr/bin/env python
# coding: utf-8 -*- 

from flask import Flask


app = Flask(__name__)

app.config.from_pyfile('appconfig.cfg')  # this file should contain UPLOAD_FOLDER, MAX_CONTENT_LENGTH, IP_HASH_STR (and maybe more variables in future) set

#all imports go here
from flask import request, render_template, redirect, url_for
from handler import Handler

#from handler_mod import Handler_mod


#uncomment these lines when you decide to use uwsgi to deploy the app. These lines
#are for running cleaner cron-task to delete older posts. tweak it as needed.
# import uwsgi
# import cleaner_crontask

# #the cleaner cron setup
# def cleaner_cron(signum) :
#     cleaner_crontask.run()

# uwsgi.register_signal(108, "", cleaner_cron)
# uwsgi.add_cron(108,0,-1,-1,-1,-1)

#uncomment these lines to test cleaner cron-task when running without uwsgi
# @app.route('/dummy/')
# def dummy():
# 	import cleaner_crontask
# 	cleaner_crontask.run()
# 	return 'ok'

@app.route('/')
def stream():
	handler = Handler()
	return handler.handle_stream(False)

@app.route('/new/')
def stream_new():
	handler = Handler()
	return handler.handle_stream(True)

@app.route('/login/', methods=['GET', 'POST'] )
def login():
	handler = Handler()
	return handler.login()

@app.route('/user/<username>/', methods=['GET', 'POST'] )
def user(username):
	handler = Handler()
	return handler.handle_userpage(username)

@app.route('/logout')
def logout():
	handler = Handler()
	return handler.logout()

@app.route('/about/')
def about():
	handler = Handler()
	return handler.handle_about()

@app.route('/banned/')
def banned():
	return 'banned page todo'

@app.route('/start_thread/', methods=['GET', 'POST'])
def start_thread():
	handler = Handler()
	return handler.handle_start_thread()

@app.route('/thread/<int:thread_id>/')
def post(thread_id):
	handler = Handler()
	return handler.handle_post(thread_id)

@app.route('/start_post/', methods=['POST'])
def add_post():	
	handler = Handler()
	return handler.handle_add_post()

@app.route('/update_user/', methods=['POST'])
def update_user():
	handler = Handler()
	return handler.handle_update_user()


@app.route('/report_post/', methods=['POST'])
def report_post():
	handler = Handler()
	return handler.handle_report_post()

@app.route('/update_post/', methods=['POST'])
def update_post():
	handler = Handler()
	return handler.handle_update_post()


#common methods
@app.route('/mod_logs/', methods=['GET'])
def mod_logs() :
	handler = Handler()
	return handler.handle_mod_logs()

#mod methods
@app.route('/mod_lounge/', methods=['GET'])
def mod_lounge() :
	handler = Handler()
	return handler.handle_mod_lounge()

@app.route('/mod_report_list/', methods=['GET'])
def mod_report_list() :
	handler = Handler()
	return handler.handle_mod_report_list()

@app.route('/mod_recent_posts/', methods=['GET'])
def mod_recent_posts() :
	handler = Handler()
	return handler.handle_mod_recent_posts()

@app.route('/mod_update_post/', methods=['GET', 'POST'])
def mod_update_post() :
	handler = Handler()
	return handler.handle_mod_update_post()

##################################
@app.errorhandler(404)
def page_not_found(e):
    return '404 not found', 404

@app.errorhandler(400)
def bad_req(e):
    return 'bad request', 400

@app.errorhandler(500)
def internal_sv_err(e):
    return 'server error', 500

