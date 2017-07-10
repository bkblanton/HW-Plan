import sendgrid
from flask import Flask, current_app
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_pymongo import PyMongo
from itsdangerous import URLSafeTimedSerializer

from app.models import User
from app.pages import pages


def setup_db():
    db = current_app.mongo.db
    db.users.create_index([('email', 'text')])
    db.classes.create_index([('owner_id', 1)])
    db.tasks.create_index([('owner_id', 1)])
    db.tasks.create_index([('class_id', 1)])
    db.counters.replace_one({'_id': 'user_id'}, {'seq': 0}, upsert=True)


def send_email(subject, to_email, content):
    sg = current_app.sg
    data = {
        "personalizations": [
            {
                "to": [
                    {
                        "email": to_email
                    }
                ],
                "subject": subject
            }
        ],
        "from": {
            "email": current_app.config['SENDGRID_DEFAULT_FROM']
        },
        "content": [
            {
                "type": "text/html",
                "value": content
            }
        ]
    }
    return sg.client.mail.send.post(request_body=data)


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # Config
    app.config.from_object('config')
    app.config.from_pyfile('application.cfg', silent=True)

    # Extension setup
    app.bcrypt = Bcrypt(app)# -*- coding: utf-8 -*-
    app.login_manager = LoginManager(app)
    app.login_manager.user_loader(lambda user_id: User(user_id, is_authenticated=True))
    app.login_manager.login_view = 'pages.login'
    app.login_manager.needs_refresh_message = 'Please log in again to continue.'
    app.mongo = PyMongo(app)
    app.sg = sendgrid.SendGridAPIClient(apikey=app.config['SENDGRID_API_KEY'])
    app.ts = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    # Blueprints
    app.register_blueprint(pages)

    # with app.app_context():
    #     setup_db()

    return app
