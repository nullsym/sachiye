#!/usr/bin/env python

#TODO: Use CSRF tokens on forms to prevent cross site request forgery(CSRF)
# Flask
from flask import Flask, render_template, request, redirect
# DB
from flask import g
import sqlite3, os

################
# Init the app #
################
app = Flask(__name__)

###############
# Global vars #
###############
DB_name = "/opt/sachiye/data.db"
# Disable whitespace and newline weirdness
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True


##############
# DB & Admin #
#   STUFF    #
##############
#TODO: Separate all DB&Admin code into its own file
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required
from flask_login import login_user, logout_user
from flask_login import UserMixin, current_user
from flask import url_for
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////opt/sachiye/wotd.db'
db = SQLAlchemy(app)
# Flask-Login works via the LoginManager class.
# Thus, we need to start things off by telling LoginManager about our Flask app.
login_manager = LoginManager(app)
login_manager.init_app(app)

# By default Flask-Login uses flask.sessions for authentication.
# Meaning we must set a secret key for our application.
app.secret_key = b'Wowee_secret_key_for_debugging\n\xec]/'
# Create a new secret with the command:
# python -c 'import os; print(os.urandom(16))'
# app.secret_key = new key here

# Rate limit password logins
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
limiter = Limiter(app, key_func=get_remote_address)


class User(UserMixin, db.Model):
    """An admin user capable of editing Words of the Day"""

    __tablename__ = 'users'
    username = db.Column(db.String(80), nullable=False, primary_key=True)
    password = db.Column(db.String(120))

    def __repr__(self):
        return '<user %r>' % (self.username)
    def set_password(self, password):
        self.password = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password, password)
    def get_id(self):
        return self.username

# We need to tell Flask-Login how to load a user from a Flask
# request and from its session. Therefore, we need to define:
# (1) user object (2) a user_loader callback

# Given a user ID, return the associated user object
# It should take unicode ID of a user and returns the corresponding user object
# Should return None if the ID is not valid
@login_manager.user_loader
def user_loader(email):
    # Returns true if the user does not exist, otherwise
    # it returns the user object
    return User.query.get(email)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def login():
    if request.method == 'GET':
        if not current_user.is_anonymous:
            return 'You are already logged in'
        return render_template('login.html')


    elif request.method == 'POST':
        email = request.form['username']
        passwd = request.form['password']
        user = User.query.filter_by(username=email).first()

        if user is not None and user.check_password(passwd):
            login_user(user, remember=True)
            return redirect('/admin/0')

    return 'Bad login'


# HTML that will allow logged users to edit the words of the day
@app.route('/admin/<int:page>', methods=['GET', 'POST'])
@login_required
def admin(page):
    if request.method == 'POST':
        wotd_id = request.form['id']
        date = request.form['date']
        wotd = request.form['wotd']
        wotd_def = request.form['def']

        print("+++++++ HERE BOI ++++++++++")
        print(request.form)
        # (1) Open the DB
        g.db = connect_db()
        
        if request.form.get('add'):
            print("Adding entry")
            g.db.execute("INSERT INTO WOTD VALUES (?, ?, ?)", (date, wotd, wotd_def))
        
        elif request.form.get('del'):
            print("Deleting entry")
            g.db.execute("DELETE FROM WOTD WHERE wotd = ?", (wotd,))
            g.db.commit()
        
        elif request.form.get('update'):
            print("Updating entry")
            #TODO: Fix this uglyness. The delete logic is BROKEN.
            g.db.execute("DELETE FROM WOTD WHERE date = ?", (wotd_id,))
            g.db.execute("INSERT INTO WOTD VALUES (?, ?, ?)", (date, wotd, wotd_def))

        # (2) Save the changes into the DB
        g.db.commit()

    # Avoid error: int too large to convert to SQLite INTEGER
    if page.bit_length() > 32:
        return error("Integer too long")
    delta = 15;
    floor = page * delta;
    # (1) Open the DB
    g.db = connect_db()
    # (2) Fetch data from the DB
    data = g.db.execute("SELECT * FROM WOTD ORDER BY date DESC LIMIT ?, ?", (floor, delta)).fetchall()
    # (3) Pass the data to the template
    return render_template('admin.html', wotd = data, artlen = len(data), page = page, delta = delta)

@app.route('/user')
@login_required
def user():
    return render_template('user.html')

#############
# DB helper #
# functions #
#############
def connect_db():
    """Connects to the specified database"""
    if os.path.exists(DB_name):
        db = sqlite3.connect(DB_name)
        return db
    else:
        return error()

@app.teardown_appcontext
def close_connection(exception):
    """Closes the database at the end of the request"""
    if hasattr(g, 'db'):
        g.db.close()

#############
#   WOTD    #
# Functions #
#############
@app.route('/')
def index():
    return redirect('/page/0')

@app.route('/page/<int:page>')
@limiter.limit("50 per hour", exempt_when=lambda: current_user.is_authenticated)
def wotd_page(page):
    # Avoid error: int too large to convert to SQLite INTEGER
    if page.bit_length() > 32:
        return error("Integer too long")
    delta = 8;
    floor = page * delta;
    # (1) Open the DB
    g.db = connect_db()
    # (2) Fetch data from the DB
    data = g.db.execute("SELECT * FROM WOTD ORDER BY date DESC LIMIT ?, ?", (floor, delta)).fetchall()
    # (3) Pass the data to the template
    return render_template('index.html', wotd = data, artlen = len(data), page = page, delta = delta)

@app.route('/rand')
def wotd_rand():
    # (1) Open the DB
    g.db = connect_db()
    # (2) Fetch data from the DB
    data = g.db.execute("SELECT * FROM WOTD ORDER BY RANDOM() LIMIT 1").fetchall()
    # (3) Pass the data to the template
    return render_template('rand.html', wotd = data)


@app.route('/error')
def error(msg=None):
    return render_template('error.html', error = msg)

########
# Main #
########
if __name__ == '__main__':
    app.run(debug=True)