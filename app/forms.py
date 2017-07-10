from datetime import datetime

from flask_wtf import FlaskForm, RecaptchaField
from wtforms import StringField, PasswordField, BooleanField, SelectField, TextAreaField
from wtforms.validators import InputRequired, Length, EqualTo, Email, DataRequired, Regexp, Optional
from wtforms_components import DateField, TimeField
from app.models import Task


class LoginForm(FlaskForm):
    email = StringField('Email', [InputRequired('Please enter a username.')])
    password = PasswordField('Password', [InputRequired('Please enter a password.')])
    remember = BooleanField('Remember Me')


class RegistrationForm(FlaskForm):
    # username = StringField('Username', [
    #     InputRequired(u'Please enter a username.'),
    #     Length(min=3, max=16, message=u'Your username must be between 3 and 16 characters long.'),
    #     Regexp(r'^\w+$', message=u'Your username may only contain letters, numbers, and underscores.'),
    #     Regexp(r'^[0-9A-Za-z]', message=u'Your username must begin with a letter or number.')
    # ])
    email = StringField('Email', [
        Email('Please enter a valid email address.')
    ])
    password = PasswordField('Password', [
        DataRequired('Please enter a password.'),
        Length(min=8, message='Your password must contain at least 8 characters.'),
        EqualTo('confirm', 'Your passwords must match.')
    ])
    confirm = PasswordField('Confirm Password', [
        InputRequired('Please repeat your password.')
    ])
    agree = BooleanField('', validators=[
        DataRequired('Please agree to the ToS.')
    ])
    # recaptcha = RecaptchaField()


class ClassForm(FlaskForm):
    name = StringField('Name', [InputRequired()])
    description = TextAreaField('Description', [
        Optional(),
        Length(max=1000)
    ])


class TaskForm(FlaskForm):
    name = StringField('Name', [InputRequired()])
    description = TextAreaField('Description', [
        Optional(),
        Length(max=1000)
    ])
    date = DateField('Date', [Optional()], default=datetime.today())
    time = TimeField('Time', [Optional()])
    category = SelectField('Category', [Optional()], choices=sorted((x, x.capitalize()) for x in Task.categories))


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', [InputRequired('Please enter your current password.')])
    new_password = PasswordField('New Password', [
        DataRequired('Please enter a password.'),
        Length(min=8, message='Your new password must contain at least 8 characters.'),
        EqualTo('confirm', 'Please double check your new password.')
    ])
    confirm = PasswordField('Confirm New Password', [
        InputRequired('Please repeat your new password.')
    ])


class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', [
        Email('Please enter a valid email address.')
    ])


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField('New Password', [
        DataRequired('Please enter a password.'),
        Length(min=8, message='Your password must contain at least 8 characters.'),
        EqualTo('confirm', 'Your passwords must match.')
    ])
    confirm = PasswordField('Confirm New Password', [
        InputRequired('Please repeat your password.')
    ])


class ChangeEmailForm(FlaskForm):
    password = PasswordField('Password', [
        DataRequired('Please enter a password.'),
        Length(min=8, message='Your password must contain at least 8 characters.'),
        EqualTo('confirm', 'Your passwords must match.')
    ])
    email = StringField('New Email', [
        Email('Please enter a valid email address.')
    ])
