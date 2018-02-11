function init() {	
	
	Thread.login_status = login_status
	Thread.you_list = you_list
	Thread.thread_id = thread_id
	Thread.status = 0
	Thread.THBD = 'Thread has been pruned or deleted'	

	Thread.initiate()		
	
	processPostsBulk()	
}

// big guy
Thread = {}
Thread.initiate = function(){
	var that = Thread
	that.inner_width = Popup.getInnerWidth(); that.inner_height = Popup.getInnerHeight();
	// init popups
	that.popup_generic = {id : null, e:document.getElementById('popup_generic')}
	that.popup_report_box = { id:null, del:null, e:document.getElementById('popup_report_box') }
	that.popup_reply_box = { id:null, e:document.getElementById('popup_reply_box') }


	window.addEventListener("orientationchange", Thread.onOrientationChange, false);

	var fc_popup_generic = function() { Thread.closePopup(Thread.popup_generic, null, true) }
	document.body.addEventListener('click', fc_popup_generic, false)
	//document.body.addEventListener('touchstart', fc_popup_generic, false) //for safari
	
	if (Thread.login_status === 1) {		
		var report_popup = that.popup_report_box.e;
		var close_report = report_popup.querySelector('.close')
		
		var fc_report_popup_call = function() { Thread.closePopup(Thread.popup_report_box,null,true ) }
		close_report.addEventListener('click', fc_report_popup_call, false)

		var report_submit_button = document.getElementById('report_button_send')
		var submit_report_call = function(evnt) {  evnt.preventDefault(); Calls.onReportSubmit() }
		report_submit_button.addEventListener('click', submit_report_call, false )	
	}


	//reply
	var reply_popup = that.popup_reply_box.e;
	var close_reply = reply_popup.querySelector('.close')
	var snap_reply = reply_popup.querySelector('.snap')


	var fc_reply_popup_call = function() { 	Thread.closePopup(Thread.popup_reply_box,null,true ) }
	close_reply.addEventListener('click', fc_reply_popup_call, false)
	snap_reply.addEventListener('click', Popup.popup_reply)


	var reply_submit_button = document.getElementById('reply_button_send')
	if (Thread.login_status === 1) {		
		var submit_reply_call = function(evnt) { evnt.preventDefault(); Calls.onReplySubmit() }
		reply_submit_button.addEventListener('click', submit_reply_call, false)
	}

	//attach update event
	var update_top = document.getElementById('update_thread_top')
	var update_bottom = document.getElementById('update_thread_bottom')
	var onupdatecall = function(evnt) { evnt.preventDefault(); Calls.threadUpdate() }
	update_top.addEventListener('click', onupdatecall, false)
	update_bottom.addEventListener('click', onupdatecall, false)

	//attach to post_replies
	var submit_reply_element = document.getElementById('submit_reply')
	var submit_reply_call = function(evnt) {evnt.preventDefault(); Calls.onReplyPopupShow(null) }
	submit_reply_element.addEventListener('click', submit_reply_call, false )


	//set name if it is stored
	var stored_name = window.localStorage.getItem('ich_name')
	if(stored_name != null) {
		document.getElementById('reply_input_name').value = stored_name
	}
}

Thread.closePopup = function(p_obj, id, force) {	
	if(force === true || (p_obj != null && p_obj.id === id) ) {
		p_obj.id = null; 		
		p_obj.e.className = 'popup_hidden'
	}
}

Thread.onOrientationChange = function() {
	var that = Thread
	var new_width = Popup.getInnerWidth(), new_height = Popup.getInnerHeight()
	if( new_width !== that.inner_width || new_height !== that.inner_height ) {
		that.inner_width = new_width; that.inner_height = new_height;	
		that.closePopup(that.popup_generic, null, true)
		that.closePopup(that.popup_report_box, null, true)
	}
}

function processPostsBulk() {
	post_list = document.getElementsByClassName('post')
	for(var i=0; i<post_list.length; i++) {
		var post_element = post_list[i]
		processPost(post_element)
	}
}

// functions store for interactive functions
var Calls = {}

Calls.togglePostHide = function(p){
	p.classList.toggle('hidden')	
}

Calls.onReportPopupShow = function(post_e, report_button) {	

	var post_id = post_e.id.substring(1)

	if(Thread.popup_report_box.id !== post_id )
	{
		//close popup if it already on
		Thread.closePopup(Thread.popup_report_box, post_id, false)

		var popup_header = document.getElementById('report_popup_header')
		var status_text = document.getElementById('report_status_text')
		var submit_button = document.getElementById('report_button_send')
		var reason_tr = document.getElementById('report_form_reason_tr')

		//cleaning the popup box 

		status_text.innerHTML = ''
		status_text.className = 'hided'
		submit_button.disabled = false

		if(report_button.innerHTML === 'delete' ) {
			popup_header.innerHTML = 'delete post No.' + post_id + ' ?'
			submit_button.innerHTML = 'delete'
			reason_tr.className = 'hided'
			Thread.popup_report_box.del = true
		} else {
			popup_header.innerHTML = 'report post No.' + post_id
			submit_button.innerHTML = 'submit'
			reason_tr.className = ''
			Thread.popup_report_box.del = null
		}

		Thread.popup_report_box.id = post_id
		Popup.popup_relative(Thread.popup_report_box, report_button )
	}
}

Calls.onReplyPopupShow = function(post_n) {	
	
	// if it is not already open
	var e = Thread.popup_reply_box.e;
	if(e.className !== 'popup_active')
	{		
		//cleaning the popup
		document.getElementById('reply_input_comment').value=''; 
		var reply_submit_button = document.getElementById('reply_button_send')
		if (Thread.login_status === 1) {
			reply_submit_button.disabled = false;
		} else {
			reply_submit_button.disabled = true;
		}

		
		reply_submit_button.innerHTML = 'submit'
		var reply_status = document.getElementById('reply_status_text')
		reply_status.innerHTML = ''
		reply_status.className = 'hided'

		var reply_input_file = document.getElementById('reply_input_file')
		try {
			reply_input_file.value = null;
		} catch (ex) {}
		if (reply_input_file.value) {
			reply_input_file.parentNode.replaceChild(reply_input_file.cloneNode(true), reply_input_file)
		}		
	}

	Popup.popup_reply()

	if(post_n == null) {
		post_n = ''
	} else {
		post_n = '>>' + post_n + '\n';
	}	
	insertAtCursor(document.getElementById('reply_input_comment'), post_n)	
}


Calls.onReportSubmit = function(){
	var submit_button = document.getElementById('report_button_send')
	var report_status = document.getElementById('report_status_text')

	var id = Thread.popup_report_box.id
	var del = Thread.popup_report_box.del

	var form_element = document.forms.report_form
	var form_data = new FormData()

	var reason = form_element.elements.reason.value
	

	if (del === true){
		reason = 'spam'
	}

	if(reason == null || reason.length == 0 ) {
		report_status.className = 'bad'
		report_status.innerHTML = 'please select reason'
		return
	}

	form_data.append('reason', reason)
	form_data.append('thread_id', Thread.thread_id)
	form_data.append('post_id', id)

	//all ok.. now we send
	submit_button.disabled = true
	var on_ok = function(d){
		if(Thread.popup_report_box.id === id)  // if not changed
		{
			report_status.className = 'good'
			report_status.innerHTML = d
		}

	}

	var on_fail = function(status, response_text) {
		if(Thread.popup_report_box.id === id)  // if not changed
		{
			report_status.className = 'bad'
			if(status == 500 || status == 400) {
				report_status.innerHTML = 'Error : ' + response_text
			} else {
				report_status.innerHTML = 'Error : ' + status
			}
			if(status != 400) {
				submit_button.disabled = false;
			}
		}		
	}

	send_form(form_data, '/report_post/', on_ok, null, on_fail)
}

Calls.onReplySubmit = function() {
	var submit_button = document.getElementById('reply_button_send')
	var reply_status = document.getElementById('reply_status_text')

	var form_element = document.forms.reply_form
	var form_data = new FormData()

	var eee = form_element.elements
	
	var text_e = eee.text
	var image = eee.image.files[0]
	var bump = eee.bump.checked

	// cleaning form values	
	var text = text_e.value = text_e.value.trim()	

	if(text.length > 2000 || text.split(/\r\n|\r|\n/).length > 40 ) {
		reply_status.className = 'bad'
		reply_status.innerHTML = 'comment too long'
		return
	}
	
	if(text.length == 0 && image == null ) {
		reply_status.className = 'bad'
		reply_status.innerHTML = 'empty content'
		return
	}

	// adding to form
	form_data.append('text', text)
	form_data.append('image', image)
	form_data.append('bump', bump)
	form_data.append('thread_id', Thread.thread_id)

	//preparing to send
	var _id = Thread.popup_reply_box.id = Math.random()

	submit_button.disabled = true
	var on_ok = function(d){
		if(Thread.popup_reply_box.id === _id ) // if not closed and reopened
		{
			reply_status.className = 'good'
			reply_status.innerHTML = 'post successful'
			
			var timeout_call = function(){
				Thread.closePopup(Thread.popup_reply_box, _id, false)
				Calls.threadUpdate()
			}
			setTimeout(timeout_call, 1500)
		}
	}

	var on_progress = function(d) {
		if(Thread.popup_reply_box.id === _id )
		{
			if (d.lengthComputable) {
				var percentComplete = Math.round((d.loaded / d.total)*100);
				if(percentComplete > 0) {
					submit_button.innerHTML = percentComplete + '%';
				}
			}
		}		
	}

	var on_fail = function(status, response_text) {
		if(Thread.popup_reply_box.id === _id )
		{
			reply_status.className = 'bad'
			if(status == 500 || status == 400) {
				var x = response_text
				if(x === 'banned') {
					x = "you have been banned.<br>Check <a href='/banned/'>banned</a> for details"
				}
				reply_status.innerHTML = 'error : ' + x
			} 
			else if(status == 413) {
				reply_status.innerHTML = 'error : image size too large'
			}
			else {
				reply_status.innerHTML = 'error : ' + status
			}
			submit_button.disabled = false
			submit_button.innerHTML = 'submit'
		}		
	}

	send_form(form_data, '/start_post/', on_ok, on_progress, on_fail)
}



Calls.threadUpdate = function() {
	var update_top = document.getElementById('update_thread_top')
	var update_bottom = document.getElementById('update_thread_bottom')

	if(update_top.innerHTML !== 'updating') {
		Calls.setThreadStatusText('', 'good') // clear it 
		if(Thread.status !== 0 ) {
			Calls.setThreadStatusText(Thread.THBD, 'bad')
		}
		else {
			update_top.innerHTML = update_bottom.innerHTML = 'updating'

			//collecting stuff			
			var last_post_id = Calls.getLastPostId()

			var form_data = new FormData()
			form_data.append('thread_id', Thread.thread_id)
			form_data.append('last_id', last_post_id)

			var on_ok = function(d) {
				update_top.innerHTML = update_bottom.innerHTML = 'update'			
				
				//make sure last_post_id is same before proceeding to ad
				var last_post_id_latest = Calls.getLastPostId()
				if(last_post_id === last_post_id_latest) {
					
					var json = JSON.parse(d)
					var infobox_txt = 'replies : ' + json.reply_count + ' | posters : ' + json.posters_count

					//setting infobox_txt in dom
					var infobox_txt_lst = document.getElementsByClassName('infobox_txt')
					for(var i=0; i<infobox_txt_lst.length; i++) {
						var e = infobox_txt_lst[i]
						e.innerHTML = infobox_txt
					}

					//update thread yous					
					for(var i=0; i<json.you_list.length; i++) {
						Thread.you_list.push(json.you_list[i])
					}

					//update thread's ago time till now
					var sv_utc = json.sv_utc;
					var all_times = document.getElementsByClassName('time')
					for(var i=0; i<all_times.length; i++) {
						var time_span = all_times[i]
						var new_duration = sv_utc - parseInt(time_span.dataset.utc)

						var new_ago = getAgeFromDuration(new_duration)
						time_span.innerHTML = new_ago
					}

					//add new posts
					var posts_div = document.getElementById('posts')
					for(var i=0; i<json.posts.length; i++) {
						var post_html = json.posts[i]
						var post_container = document.createElement('div')
						post_container.className = 'post_container'
						post_container.innerHTML = post_html
						posts_div.appendChild(post_container)

						
						var post_element = post_container.children[0]
						processPost(post_element)
					}
				}
			}

			var on_fail = function(status, response_text) {				
				if(status == 404) {
					Thread.status = 1
					Calls.setThreadStatusText(Thread.THBD, 'bad')					
				} else if (response_text.length > 0 ) {
					Calls.setThreadStatusText(response_text, 'bad')
				}
				else {
					Calls.setThreadStatusText('failed to update thread', 'bad')
				}
				update_top.innerHTML = update_bottom.innerHTML = 'update'
			}

			send_form(form_data, '/update_post/', on_ok, null, on_fail)
		}
	}
}

Calls.getLastPostId = function() {
	var last_post_container = document.getElementById('posts').lastElementChild
	var last_post_div = last_post_container.getElementsByClassName('post')[0]
	var last_post_id = parseInt( last_post_div.id.substring(1) )
	return last_post_id
}

Calls.setThreadStatusText = function(txt, className) {
	var thread_status_txt_lst = document.getElementsByClassName('thread_status_txt')
	for(var i=0; i<thread_status_txt_lst.length; i++) {
		var t = thread_status_txt_lst[i]
		t.innerHTML = txt
		t.classList.remove('bad'); t.classList.remove('good')
		t.classList.add(className)
	}
}

Calls.modifyIdFn =function(node) {
	if (node.nodeType === Node.ELEMENT_NODE && node.id && node.id.length > 0) { 
		node.id = 'clone_' + node.id
	}
	if (node.tagName && node.tagName.toLowerCase() === 'button') {
		node.style.display = 'none'
	}
}

Calls.getCloneQuotePost = function(to_clone) {
	var clone = to_clone.cloneNode(true)
	walkTheDOM(clone, Calls.modifyIdFn)	
	if (clone.classList.contains('hidden') === true) {
		clone.style.opacity = '1' // otherwise causes too much transparency
		var post_hidden_element = document.createElement('blockquote')
		post_hidden_element.innerHTML = '[post hidden]'
		post_hidden_element.style.color = '#933'
		clone.appendChild(post_hidden_element)
	}

	var f = clone.querySelector('.file_thumb')
	if(f) {		
		var f_children = f.children
		if (f.style.float === 'none') {
			f_children[0].className = ''
			f.style.float = 'left'
			if ( f_children.length === 2 ) {
				f_children[1].className = 'hidden'
			}
		}
	}
	
	return clone
}

Calls.attachQuotePopup = function(e, to_clone, id ) {
	var _id = (id === undefined) ? to_clone.id : id

	var popupFn = function(evnt) {
		var popup_was_shown = false	
		if(Thread.popup_generic.id !== _id) {		
			var rect = to_clone.getBoundingClientRect()
			if(rect.top > 0 && rect.bottom < Popup.getInnerHeight() ) {
				to_clone.classList.add('selected')
			}
			else {
				Thread.popup_generic.id = _id // set new id				
				//empty it first
				var popup_e = Thread.popup_generic.e
				while (popup_e.firstChild) {
					popup_e.removeChild(popup_e.firstChild)
				}
				
				Thread.popup_generic.e.appendChild(Calls.getCloneQuotePost(to_clone))
				Popup.popup_relative(Thread.popup_generic, e )

				Thread.quote_popup_shown_for = e
				popup_was_shown = true
			}
		}

		//logic for touch devices only
		if(evnt.type === 'click' ) {
			//suppressing click
			evnt.preventDefault()
			evnt.stopPropagation()

			if(popup_was_shown === false && Thread.quote_popup_shown_for === e)	{
				//manual jump done here
				Thread.quote_popup_shown_for = null
				Thread.closePopup(Thread.popup_generic, _id, false)

				window.location.href = e.href
			}

		}

	}

	var closePopupFn = function(evnt){
		Thread.quote_popup_shown_for = null  // in case it was set (touch device only)
		Thread.closePopup(Thread.popup_generic, _id, false )		
		//empty it first so that others get it clean. not really required
		var popup_e = Thread.popup_generic.e
		while (popup_e.firstChild) {
			popup_e.removeChild(popup_e.firstChild)
		}
		to_clone.classList.remove('selected') // just in case it was set
	}

	if ('ontouchstart' in e) {		
		e.addEventListener('click', popupFn, false)
		e.addEventListener('mouseout', closePopupFn, false)
	}
	else {
		e.addEventListener('mouseenter', popupFn, false)	
		e.addEventListener('mouseout', closePopupFn, false)	
	}	
	
}

Calls.onFileThumbClick = function(f) {
	var children = f.children
	var href = f.href

	var timeout_call_count = 250
	var big_guy	= null
	

	var timeout_call = function() {
		if (big_guy.naturalWidth) {
			children[0].className = 'hidden'
			children[1].className = 'expanded_img'	
			f.style.float = 'none'
		}
		else {
			timeout_call_count *= 2
			if(timeout_call_count < 10000) { // 10 sec
				setTimeout(timeout_call, timeout_call_count)
			} else {
				//remove node so one can retry again
				if (big_guy) {					
					f.removeChild(big_guy)									
				}				
			}
		}
	}

	var big_guy_added_to_dom = false
	if (children.length == 2) {
		big_guy_added_to_dom = true
		big_guy = children[1]
	}
	


	if ( big_guy_added_to_dom === false ) {		
		big_guy = document.createElement('img')
		big_guy.className = 'hidden'
		big_guy.src = href
		f.appendChild(big_guy)	

		big_guy_added_to_dom = true
		setTimeout(timeout_call, timeout_call_count)
	}

	else {
	
		if(f.style.float == 'left' && children[1].naturalWidth ) {
			children[0].className = 'hidden'
			children[1].className = 'expanded_img'
			f.style.float = 'none'
		} else if (f.style.float == 'none' ) {
			children[0].className = ''
			children[1].className = 'hidden'
			f.style.float = 'left'
		}	
		
	}
}


function processPost(p) {
	var post_id = p.id		
	
	if (Thread.login_status === 1) {  // might be not be present if not logged in
		var report_button = p.querySelector('.post_info .report')
		var report_button_call = function() { Calls.onReportPopupShow(p,report_button) }
		report_button.onclick = report_button_call			
	}

	
	handleQuoteAndYous(p)	

	attachReplyListeners(p)

	attachImageEnlargers(p)
}

function handleQuoteAndYous(p) {
	var post_n = p.id.substring(1)
	var qn_list = p.querySelectorAll('.post_message .quote_no')
	for(var i=0; i < qn_list.length; i++) {
		var qn = qn_list[i]

		var qn_regexp = /(?:&gt;){2,5}(\d{3,12})/g;
		var qn_match = qn_regexp.exec(qn.innerHTML)
		var n = 0
		if (qn_match) {
			n = parseInt(qn_match[1])
		}
		
		var q_dst = document.getElementById('p' + n);
		if(q_dst) {
			if(n === Thread.thread_id) {
				qn.innerHTML += ' (OP)'
			}
			else if ( Thread.you_list.indexOf(n) >= 0) {
				qn.innerHTML += ' (You)'
			}

			//add to qb and also attach listeners to both src and dst
			qb_id = 'qb' + post_n + '-' + n
			if(!document.getElementById(qb_id)) {
				qbl_id = 'qbl' + n				
				qbl = document.getElementById(qbl_id)
				if(qbl.style.display !== 'inline') {
					qbl.style.display = 'inline'
				}

				var qb = document.createElement('a');
				qb.id = qb_id;
				qb.href = '#p' + post_n;
				qb.className = 'quote_no'
				qb.innerHTML = '&gt;&gt;' + post_n + ' ';
				Calls.attachQuotePopup(qb, p, qb_id)

				qbl.appendChild(qb);
			}
			
			Calls.attachQuotePopup(qn, q_dst)
		}
		else {
			qn.classList.add('dashed')
		}
	}
}

function attachReplyListeners(p) {
	var post_n = null 

	if (Thread.login_status === 1) {
		var post_n = p.id.substring(1)	
	}	
	var post_num = p.querySelector('.post_num')
	
	var on_post_num_click_call = function() {
		Calls.onReplyPopupShow(post_n)
	}

	post_num.addEventListener('click', on_post_num_click_call, false)	

}

function attachImageEnlargers(p) {
	var f = p.querySelector('.file_thumb')
	if(f) {
		var on_click_call = function(evnt) {
			evnt.preventDefault()
			Calls.onFileThumbClick(f)
		}
		f.addEventListener('click', on_click_call, false)
	}
}


// popup functions
var Popup = {}
Popup.popup_relative = function(p, re, y_delta) {	
	var popup = p.e;	
	popup.className = 'popup_active'	

	if(y_delta == null) {
		y_delta = 0
	}

	var rect = re.getBoundingClientRect()
	var popup_style = popup.style
	popup_style.left = popup_style.right = popup_style.top = popup_style.bottom = null

	//70% check
	if(rect.right > 0.7*Popup.getInnerWidth() ) {		
		popup.style.right = (Popup.getInnerWidth() - ( Popup.getPageXOffset() + rect.right ) ) + 'px'
	}
	else {
		popup.style.left = (Popup.getPageXOffset() + rect.left) + 'px'
	}
	/*if(up === true) {		
		popup.style.bottom = ( Popup.getInnerHeight() - (Popup.getPageYOffset() + rect.top) ) + 'px' 
	}*/	
	popup.style.top = ( Popup.getPageYOffset() + rect.bottom + y_delta ) + 'px'
	
}

Popup.popup_reply = function() {
	var popup = Thread.popup_reply_box.e;
	popup.className = 'popup_active'
	popup.style.top = ( Popup.getPageYOffset() + 5 ) + 'px'
	popup.style.right = '5px'
}


/*Popup.getTotalHeight = function() {
	var D = document;
	return Math.max( D.body.scrollHeight, D.documentElement.scrollHeight, D.body.clientHeight, D.documentElement.clientHeight )
}

Popup.getTotalWidth = function() {
	var D = document;
	return Math.max( D.body.scrollWidth, D.documentElement.scrollWidth, D.body.clientWidth, D.documentElement.clientWidth )
}
*/

Popup.getInnerWidth = function() {	
	return (document.documentElement || document.body).clientWidth
	//return (window.innerWidth !== undefined) ? window.innerWidth : document.documentElement.clientWidth
}

Popup.getInnerHeight = function() {
	return (document.documentElement || document.body).clientHeight
	//return (window.innerHeight !== undefined) ? window.innerHeight : document.documentElement.clientHeight	
}

Popup.getPageYOffset = function() {
	return (window.pageYOffset !== undefined) ? window.pageYOffset : (document.documentElement || document.body.parentNode || document.body).scrollTop
}

Popup.getPageXOffset = function() {
	return (window.pageXOffset !== undefined) ? window.pageXOffset : (document.documentElement || document.body.parentNode || document.body).scrollLeft
}

function getAgeFromTimestamp(ts) {
	var date = new Date()
	var now = parseInt(date.getTime()/1000)

	var d = now - ts
	return getAgeFromDuration(d)
}

function getAgeFromDuration(duration) {
	var tmp = 0
	if(duration < 0) {
		return '0 second ago'
	}
	if(duration < 60 ) {
		return duration + ' seconds ago'
	}
	if(duration < 60*60) {		
		tmp = parseInt(duration/60)
		return tmp + ' minute' + (tmp>1?'s':'') + ' ago'
	}
	if(duration < 24*60*60) {		
		tmp = parseInt( duration/(60*60) )		
		return tmp + ' hour' + (tmp>1?'s':'') + ' ago'
	}
	tmp = parseInt( duration/(24*60*60) )
	return tmp + ' day' + (tmp>1?'s':'') + ' ago'
}

function walkTheDOM(node, func) {
    func(node);
    node = node.firstChild;
    while (node) {
        walkTheDOM(node, func);
        node = node.nextSibling;
    }
}

function insertAtCursor(myField, myValue) {    
	//IE support
	if (document.selection) {    
		myField.focus()    
		sel = document.selection.createRange()
		sel.text = myValue
	}
	//MOZILLA and others
	else if (myField.selectionStart || myField.selectionStart == '0') {		
		var startPos = myField.selectionStart
		var endPos = myField.selectionEnd
		myField.value = myField.value.substring(0, startPos) + myValue + myField.value.substring(endPos, myField.value.length)
		myField.selectionStart = myField.selectionEnd = startPos + myValue.length
	} else {
		myField.value += myValue
	}
	myField.focus()	
  	if(myField.selectionStart == myField.value.length) {
  		myField.scrollTop = myField.scrollHeight
  	}
}

document.addEventListener("DOMContentLoaded", init);

// util functions
function send_form(form_data, endpoint, on_ok, on_progress, on_fail) {
	var xhr = new XMLHttpRequest();
	if(on_progress != null) { xhr.upload.addEventListener('progress', on_progress) }
	
	xhr.open('POST', endpoint );
	xhr.onreadystatechange = function() {
		if(xhr.readyState === 4 ) {
			if(xhr.status == 200 ) {
				on_ok(xhr.responseText);
			}
			else {				
				console.log('failed with status : ' + xhr.status + ' and readyState : ' + xhr.readyState);
				on_fail(xhr.status, xhr.responseText)
			}
		}
	}

	xhr.send(form_data);
}


// trim polyfill
if (!String.prototype.trim) {
  String.prototype.trim = function () {
    return this.replace(/^[\s\uFEFF\xA0]+|[\s\uFEFF\xA0]+$/g, '');
  };
}

function board_select_set_callbacks(default_select) {
	var select = document.getElementById('board_select')	

	if(default_select) {
		select.value = default_select
	}

	select.onchange = function(){
		var v = select.value
		window.location = '/boards/' + select.value + '/' ; // redirect
	}
}

function theme_select_set_callbacks() {
	var select = document.getElementById('theme_select')
	var stored_theme = window.localStorage.getItem('ich_theme')
	if(stored_theme != null) {
		select.value = stored_theme
		document.getElementById('theme_stylesheet').href = '/static/style_' + stored_theme + '.css'
	}

	select.onchange = function(){
		window.localStorage.setItem('ich_theme', select.value)
		document.getElementById('theme_stylesheet').href = '/static/style_' + select.value + '.css'
	}
}
