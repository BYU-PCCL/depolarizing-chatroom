from flask import Flask, render_template, request, jsonify, redirect, session
from flask.helpers import url_for
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from functools import wraps
from os import getcwd, path, remove, environ
from datetime import datetime as dt
import random
import eventlet
from dotenv import load_dotenv
from flask_migrate import Migrate

#eventlet.monkey_patch()
load_dotenv(path.join(path.dirname(__file__), '.env'))

# for now, have waiting room queue be a dictionary of lists (for code names)
THRESHOLD = 2
MSG_LIMIT = 5
TEST = False

# app
app = Flask(__name__)
app.secret_key = environ.get("SECRET_KEY") # v secure
app.config['SESSION_TYPE'] = 'filesystem'

app.jinja_env.globals.update(zip=zip) # add zip to jinja
app.jinja_env.globals.update(int=int)

# session
Session(app)

# socket
socketio = SocketIO(app)

# POSTGRES
if TEST:
    # POSTGRES
    host = environ.get("LOCAL_HOST")
    username = environ.get("LOCAL_UNAME")
    address = environ.get("LOCAL_ADDR")
    password = environ.get("LOCAL_PW")
    dbname = environ.get("LOCAL_DBNAME")
    app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{username}:{password}@{host}/{dbname}"
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = environ.get("DB_URI")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
app.config['SESSION_PERMANENT'] = True

migrate = Migrate(app, db)

# create database
class Chatrooms(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codeid = db.Column(db.Integer, db.ForeignKey('codes.id'))
    prompt = db.Column(db.String(320))
    # relationship (one-to-many with users, one-to-many with messages, many-to-one with codes)
    users = db.relationship('Users', back_populates='chatroom')
    messages = db.relationship('Messages', back_populates='chatroom')
    code = db.relationship('Codes', back_populates='chatrooms')

    def __repr__(self):
        return f"{self.code}:{self.prompt}, {self.users}"

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chatroomid = db.Column(db.Integer, db.ForeignKey('chatrooms.id'))
    codeid = db.Column(db.Integer, db.ForeignKey('codes.id'))
    email = db.Column(db.String(320), nullable=False, unique=True)
    curq = db.Column(db.Integer, default=1)
    uname = db.Column(db.String(320))
    color = db.Column(db.String(7))
    msg_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="code")
    #waiting = db.Column(db.DateTime)
    # relationship (many-to-one with chatrooms, one-to-many with messages, many-to-one with codes, one-to-many with responses)
    chatroom = db.relationship('Chatrooms', back_populates='users')
    messages = db.relationship('Messages', back_populates='user')
    code = db.relationship('Codes', back_populates='users')
    responses = db.relationship('Responses', back_populates='user')

    def __repr__(self):
        return f"{self.uname}:{self.code}"

class Messages(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chatroomid = db.Column(db.Integer, db.ForeignKey('chatrooms.id'))
    senderid = db.Column(db.Integer, db.ForeignKey('users.id'))
    msg = db.Column(db.Text, nullable=False)
    sendtime = db.Column(db.DateTime, nullable=False)
    bot = db.Column(db.Boolean, default=False)
    # relationship (many-to-one with chatroom, many-to-one with user)
    chatroom = db.relationship('Chatrooms', back_populates='messages')
    user = db.relationship('Users', back_populates='messages')

    def __repr__(self):
        return f"{self.user}@{self.chatroom}: {self.msg}"

class Responses(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    userid = db.Column(db.Integer, db.ForeignKey('users.id'))
    codeid = db.Column(db.Integer, db.ForeignKey('codes.id'))
    questionid = db.Column(db.Integer, db.ForeignKey('questions.id'))
    _response = db.Column(db.Text) # potential list delineated by pipes |
    # relationship (many-to-one with Codes, many-to-one with Users, many-to-one with Questions)
    code = db.relationship('Codes', back_populates='responses')
    user = db.relationship('Users', back_populates='responses')
    question = db.relationship('Questions', back_populates='responses')

    @property
    def response(self):
        return [x for x in self._response.split("|")]

    @response.setter
    def response(self, vals):
        self._response = "|".join(vals)

    def __repr__(self):
        return f"{self.user}@{self.question}: {self.response}"

class Questions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codeid = db.Column(db.Integer, db.ForeignKey('codes.id'))
    question = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), nullable=False)
    number = db.Column(db.Integer, nullable=False) # question number
    start = db.Column(db.Float)
    step = db.Column(db.Float)
    _options = db.Column(db.Text) # pipe | delineated options
    _range = db.Column(db.Text) # pipe | delineated min and max (for grid)
    _questions = db.Column(db.Text) # pipe | delineated questions (for grid, each row)

    # relationship (many-to-one with Codes, one-to-many with Responses)
    responses = db.relationship('Responses', back_populates='question')
    code = db.relationship('Codes', back_populates='questions')

    @property
    def options(self):
        return [x for x in self._options.split("|")]

    @options.setter
    def options(self, vals):
        self._options = "|".join(vals)

    @property
    def range(self):
        return [float(x) for x in self._range.split("|")]

    @range.setter
    def range(self, vals):
        self._range = "|".join(list(map(str,vals)))

    @property
    def questions(self):
        return [x for x in self._questions.split("|")]

    @questions.setter
    def questions(self, vals):
        self._questions = "|".join(vals)

    def __repr__(self):
        return self.question

class Codes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, unique=True)
    expiry = db.Column(db.DateTime, nullable=False)
    # relationship (one-to-many with chatrooms, one-to-many with user, one-to-many with responses, one-to-many with questions)
    chatrooms = db.relationship('Chatrooms', back_populates='code')
    users = db.relationship('Users', back_populates='code')
    responses = db.relationship('Responses', back_populates='code')
    questions = db.relationship('Questions', back_populates='code', order_by=Questions.number.desc)

    def __repr__(self):
        return self.code

def add_to_db(data):
    'just cuz I forget to commit frequently'
    db.session.add(data)
    db.session.commit()
    return True

def random_color():
    return '#' + str(hex(random.randint(0,16777215)))[2:]

@app.context_processor
def utility_processor():
    def comp_ids(id1, id2):
        print(id1, id2)
        print(int(id1) == int(id2))
        return int(id1) == int(id2)
    return dict(comp_ids=comp_ids)

"""
Survey builder
"""
# extra security for admin items
def is_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin", False):
            return redirect('/admin_login')
        return f(*args, **kwargs)
    return decorated

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        return render_template("admin_login.html")
    else:
        if request.form["uname"] == environ.get("ADMIN_UNAME") and request.form["pw"] == environ.get("ADMIN_PW"):
            session["admin"] = True
            # to admin portal
            return redirect("/admin")
        else:
            return render_template("admin_login.html", incorrect=True)

@app.route("/survey_builder", methods=["GET", "POST"])
@is_admin
def survey_builder():
    if request.method == "GET":
        return render_template("survey_builder.html", code=None)
    else:
        # starting survey
        if "code" in request.form and "expiry" in request.form:
            code = request.form["code"]
            # look up code in db
            c = Codes.query.filter_by(code=code).first()
            # if doesn't exist, add new code and survey, otherwise, resume
            if c == None:
                add_code(code, request.form["expiry"])
                qnum = 1
                # start thread listening on code
                #t = threading.Thread(target=waitlist_listener, args=(code,))
                #t.setDaemon(True)
                #t.start()
                #TODO if have waitlist, add stuff
                #eventlet.spawn(waitlist_listener, code)
                print("thread started")
            else:
                qnum = len(c.questions) + 1
            print("rendering question")
            return render_template("survey_builder.html", code=code, qnum=qnum)
        # or adding new question
        else:
            # parse response
            code = request.form["code"]
            qnum = int(request.form["qnum"])
            code, qnum = parse_question_add(code, qnum, request.form)
            return render_template("survey_builder.html", code=code, qnum=qnum)

def parse_question_add(code, n, form):
    # set question
    qtype = form["type"]
    q = Questions(question=form["question"], type=qtype, number=n)

    # get code
    c = Codes.query.filter_by(code=code).first()
    q.codeid = c.id

    # parse type
    if qtype == "radio" or qtype == "multiple":
        # options are options in list
        q.options = form.getlist("option")
    elif qtype == "grid":
        # each row of the grid
        q.questions = form.getlist("row")
        # options are the columns of the grid (least likely, average, most likely, etc)
        q.options = form.getlist("option")
    else: # else slider
        # start is where the slider should start
        q.start = float(form["start"])
        # range is min/max of slider
        q.range = [float(form["min_val"]), float(form["max_val"])]
        # step is slider incrmenet
        q.step = form["step"]

    # add question to database
    add_to_db(q)

    return code, n+1


"""
Database management
"""
def initialize_test(nusers=8, ncodes=2, nchats=2):
    """
    nusers: int, number of users to test with
    ncodes: int, number of codes (will be divided evenly amongst users)
    nchats: int, number of chats (per code)
    WARNING: wipes test database
    """
    assert nusers // (nchats * ncodes) == nusers / (nchats * ncodes),\
        "Chats or codes do not evenly distribute amongst users."

    # reset test database
    if path.exists("chatrooms_test.sqlite3"):
        remove("chatrooms_test.sqlite3")
        db.create_all()

    # populate database with nusers users
    users = []
    for nu in range(nusers):
        u = Users(email=f"{nu}@email.com", uname=f"user{nu}", color=random_color())
        users.append(u)
        add_to_db(u)

    # populate database with ncodes codes and, for each code, nchats chatrooms
    codes = []
    chats = []
    for nco in range(ncodes):
        codes.append(add_code(f"code_{nco}", "2021-09-01"))
        # add chats
        for nch in range(nchats):
            chats.append(add_chatroom(f"Chatroom {nch}"))

    # assign codes and chats to users
    for u, co, ch in zip(users, codes * (nusers//ncodes), chats * (nusers//(ncodes * nchats))):
        u.codeid = co.id
        u.chatroomid = ch.id

    # commit changes
    db.session.commit()

def add_code(code, expiry, fmt="%Y-%m-%d"):
    """
    code: str
    expiry: datetime (default format YYYY-MM-DD)

    returns Codes
    """
    c = Codes(code=code, expiry=dt.strptime(expiry, fmt))
    add_to_db(c)

    return c

def add_chatroom(prompt):
    """
    Prompt to talk about in chatroom

    returns Chatrooms
    """
    c = Chatrooms(prompt=prompt)
    add_to_db(c)
    return c

"""
Login logic
"""
def requires_acc(f):
	@wraps(f)
	def decorated(*args, **kwargs):
		if "user" not in session:
			return redirect('/login')
		return f(*args, **kwargs)
	return decorated

def process_login(email):
    """
    If database contains User, log them in
    """
    q = Users.query.filter_by(email=email).first()
    print(q)
    if q != None:
        # add user to session
        session["user"] = {"email": email, "uname":q.uname}
        return True

    return False

def process_signup(email, uname):
    """
    If database has email or username, return false
    otherwise, add user to Users
    """
    # if contains email or uname
    if Users.query.filter_by(email=email).first() or Users.query.filter_by(uname=uname).first():
        return False

    # add user to database
    add_to_db(Users(email=email, uname=uname, color=random_color()))

    # add user to session
    session["user"] = {"email": email, "uname": uname}

    return True


@app.route('/login', methods=["GET", "POST"])
def login():
    print("logging in")
    if request.method == "GET":
        return render_template("login.html")
    else:
        # TODO if change login logic (e.g. password) will need to change
        # if logging in, check if email is real
        if len(request.form) == 1:
            # if processing login fails, redirect to login (1 field -- email)
            if not process_login(request.form["email"]):
                return jsonify({"msg":"Email not found"}), 400, {'ContentType':'application/json'}
        # otherwise, signing up (2 fields -- email and uname)
        elif len(request.form) == 2:
            # if processing signup fails, redirect to login
            if not process_signup(request.form["email"], request.form["uname"]):
                return jsonify({"msg":"Email or username already taken."}), 400, {'ContentType':'application/json'}

        return jsonify({"redirect":"/"}), 200, {'ContentType':'application/json'}

"""
Survey Logic
"""
def validate_code(code):
    'if code in database and time before expiry, return True'
    # get code
    c = Codes.query.filter_by(code=code).first()
    # if not None, make sure is not expired
    if c != None:
        if c.expiry > dt.now():
            return c

    return False


def store_response(form, u, qtype, qnum):
    r = Responses()
    r.userid = u.id
    r.questionid = u.code.questions[qnum - 1].id # get question id from user's associated code
    r.codeid = u.code.id
    if qtype == "grid":
        # join each response with semicolon to list
        res = []
        for k, v in form.items():
            res.append(f"{k};{v}")
        r.response = res
    else:
        print("response ", list(form.values()))
        if qtype == "multiple":
            vals = list(form.values())[0]
        else:
            vals = list(form.values())
        r.response = vals

    # radio will only have one response
    db.session.add(r)
    db.session.commit()
    print(r)
    return True

@app.route('/', methods=['GET'])
@requires_acc
def home():
    u = Users.query.filter_by(email=session["user"]["email"]).first()
    # redirect user wherever they need to go
    if user.status == "survey":
        return get_question(u.code.code, u.curq)
    elif user.status == "chatroom":
        redirect(f'/chatroom/{user.chatroomid}')

    return render_template('index.html', popup='popup.html')

@app.route('/ajax_form', methods=['POST'])
def home_form():
    # get user
    u = Users.query.filter_by(email=session["user"]["email"]).first()
    # if code in form, validate and begin survey
    if "code" in request.form:
        code = request.form["code"]
        # get code response
        c = validate_code(code)
        if c:
            # assign user the code
            u.code = c
            u.status = "survey"
            db.session.commit()
            # store cookie
            session["user"]["code"] = code

            # start survey
            return get_question(code, 1)
        else:
            return jsonify({"msg":"Invalid code"}), 400, {'ContentType':'application/json'}
    # otherwise, if qtype is in the form, it's a question
    elif "qtype" in request.form:
        form = request.form.to_dict()
        qtype = form.pop("qtype")
        # if form type is multiple
        if qtype == "multiple":
            qname = list(form.keys())[0]
            print(request.form.getlist(qname))
            form[qname] = request.form.getlist(qname)
        store_response(form, u, qtype, u.curq)

        # update user
        u.curq += 1
        db.session.commit()
        return get_question(u.code.code, u.curq)

    return jsonify({"message":"Invalid submission - no form data"}), 401, {'ContentType':'application/json'}

def get_question(code, qnum):
    """
    code: str, survey code
    qnum: int, # question user is on (1 is first)
        * if qnum is out of range, return chatroom
    """
    # get question
    c = Codes.query.filter_by(code=code).first()
    q = Questions.query.filter_by(number=qnum, codeid=c.id).first()

    # if no question, redirect to chatroom
    if q == None:
        # get user
        u = Users.query.filter_by(email=session["user"]["email"]).first()
        # make chatroom for user
        # TODO this will move to waiting room listener if we revert to that, that's why users is one-to-many
        cr = Chatrooms(codeid=c.id, users=[u], prompt="Talk with GPT-3")
        add_to_db(cr)
        # update user
        u.status = "chatroom"
        u.chatroomid = cr.id
        db.session.commit()

        return jsonify({"redirect":f"/chatroom/{cr.id}"}), 200, {'ContentType':'application/json'}
        #return jsonify({"redirect":f"/waiting_room/{uid}"}), 200, {'ContentType':'application/json'}

    # otherwise, determine if is last question
    if len(c.questions) == qnum:
        submit = "Finish!"
    else:
        submit = "Next Question:"

    # parse question
    qd = q.__dict__
    qt = q.type
    if qt == "slider":
        qd["min_val"] = q.range[0]
        qd["max_val"] = q.range[1]
    elif qt == "grid":
        # distribute questions
        qs = q.questions
        qd["questions"] = qs
        qd["rows"] = list(range(len(qs)))
        # distribute options
        opts = q.options
        qd["opts"] = opts
        qd["labels"] = (opts[0], opts[-1])
    else:
        qd["opts"] = q.options

    return jsonify({"question":q.question, "type":qt, "submit":submit,
            "rendered_form": render_template("question.html",**qd)}),\
                200, {'ContentType':'application/json'}

"""
CHATROOM
"""
@app.route('/chatroom/<cid>', methods=['GET'])
@requires_acc
@is_admin
def chatroom(cid):
    # get user information from db
    user = Users.query.filter_by(email=session["user"]["email"]).first()
    if user.chatroomid != int(cid):
        return jsonify({"message":"Invalid chatroom"}), 401, {'ContentType':'application/json'}
    # get all previously sent messages in the chatroom
    msgs = Messages.query.filter_by(chatroomid=cid).all()
    prompt = Chatrooms.query.filter_by(id=cid).first().prompt
    return render_template('chatroom_bot.html', uname = user.uname, color = user.color, uid=user.id, cid=cid, msgs=msgs, prompt=prompt)

@app.route('/eliza', methods=['GET'])
def eliza():
    prompt = "Discuss with ELIZA"
    return render_template('eliza.html', uname = "TEST", color = "red", prompt=prompt)


"""
Waiting Room (with waiting room sockets)
"""
"""
# NO NEED FOR WAITING ROOM IF PEOPLE NOT CHATTING W EACH OTHER
# unique waiting room for each user
@app.route("/waiting_room/<uid>")
@requires_acc
def waiting_room(uid):
    # get user information from db
    u = Users.query.filter_by(email=session["user"]["email"]).first()

    # if cookie doesn't match user, we got a problem
    if u.id != int(uid):
        return jsonify({"message":"Invalid chatroom"}), 401, {'ContentType':'application/json'}

    # get number of people in that
    nq = Users.query.filter(Users.codeid==u.code.id, Users.waiting!=None).count()

    return render_template("waiting_room.html", uid=uid, threshold=THRESHOLD, num_queue=nq)

@socketio.on('join_waiting_room')
def handle_waiting_room(json, methods=['GET', 'POST']):
    # get current user
    uid = json["uid"]
    u = Users.query.filter_by(id = int(uid)).first()

    # add user to queue if not already in a chatroom
    u.waiting = dt.now()
    db.session.commit()

    json["num_queue"] = Users.query.filter(Users.codeid==u.code.id, Users.waiting!=None).count()

    socketio.emit('joined_waiting_room', json, callback=messageReceived)

def waitlist_listener(code):
    while True:
        # if number of users in queue exceeds threshold, redirect threshold # users to same chatroom
        c = Codes.query.filter_by(code=code).first()
        waiters = Users.query.filter(Users.code==c, Users.waiting!=None).all()
        if len(waiters) >= THRESHOLD:
            print("people waiting:")
            print(waiters)
            us = waiters[:THRESHOLD]
            # create chatroom
            chatroom = Chatrooms(codeid=c.id, prompt="This is a sample prompt for now.")
            db.session.add(chatroom)
            db.session.commit()
            # redirect each user
            for u in us:
                # add relationships
                chatroom.users.append(u)
                u.chatroomid = chatroom.id
                u.waiting = None

                print(f"Redirecting {u.id} to /chatroom/{chatroom.id}")
                socketio.emit(f"waiting_room_redirect_{u.id}", {'redirect':f'/chatroom/{chatroom.id}'})
            db.session.commit()
"""

"""
Chatroom sockets
"""
def messageReceived(methods=['GET', 'POST']):
    print('message was received!!!')

@socketio.on('join_chatroom')
def handle_join_chat(json, methods=['GET', 'POST']):
    socketio.emit('joined_chatroom', json, callback=messageReceived)

@socketio.on('post')
def handle_msg_sent(json, methods=['GET', 'POST']):
    # store message in database

    msg = json["body"]
    # get chatroom
    chatroom = Chatrooms.query.filter_by(id=json["cid"]).first()

    # get user
    user = Users.query.filter_by(id=json["uid"]).first()
    user.msg_count += 1 # increment user message count

    # store message
    add_to_db(Messages(chatroomid=chatroom.id, senderid=user.id, msg=msg, sendtime=dt.now()))


    """
    this is where you'd pass the message into gpt-3

    something like:
    response = gpt3.run(msg)
    # add the message to the json
    json["response"] = response

    and then in chatroom.html, simply add that response to the chatbox (div.chatrwapper)
    """
    json["response"] = "GPT response"
    print("gpt response")

    # store GPT response in DB
    """
    Store message sent by GPT as bot response in DB (bot=True)
    """
    add_to_db(Messages(chatroomid=chatroom.id, senderid=user.id, msg=json["response"], sendtime=dt.now(), bot=True))
    print("gpt message added")

    """
    Check if user has exceeded chat limit, if so redirect to survey
    TODO what should the limit be?
    """
    if user.msg_count > MSG_LIMIT:
        set_user_status(user, "postsurvey")
        redirect('/postsurvey')

    # send response to that chatroom
    socketio.emit(f'response_{json["cid"]}', json, callback=messageReceived)

"""
Admin panel
"""
@app.route("/admin")
@is_admin
def admin():
    tables = {"users":Users, "chatrooms":Chatrooms, "codes":Codes}
    for name, table in tables.items():
        tables[name] = table.query.limit(3).all()
    return render_template("data.html", data=tables)

if __name__ == '__main__':
    #initialize_test()

    # run app
    socketio.run(app, debug=TEST, port=8000)
