from datetime import datetime

from bson.objectid import ObjectId
from flask import Blueprint, redirect, url_for, render_template, jsonify, flash, current_app, abort
from flask_login import login_user, login_required, logout_user, current_user, fresh_login_required

import app
from app.forms import RegistrationForm, LoginForm, ClassForm, TaskForm, ChangePasswordForm, ForgotPasswordForm, \
    ResetPasswordForm
from app.models import User, Class, Task, UserCalendar

pages = Blueprint('pages', __name__)


@pages.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('pages.home'))
    else:
        return redirect(url_for('pages.login'))


@pages.route('/login', methods=('GET', 'POST'))
def login():
    if current_user.is_active:
        return redirect(url_for('pages.home'))
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        remember = form.remember.data
        user = User.from_login(email, password)
        if not user.is_active:
            if not user.verified:
                flash("Your email hasn't been verified yet.")
            else:
                flash("Incorrect email or password.")
            return redirect(url_for('pages.login'))
        else:
            login_user(user, remember=remember)
            return redirect(url_for('pages.home'))
    return render_template('login.html', form=form)


@pages.route('/register', methods=('GET', 'POST'))
def register():
    if current_user.is_active:
        return redirect(url_for('pages.home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        if User.from_email(email).exists():  # Username isn't taken
            flash("That email is already in use.")
        else:
            user = User.create(email, password)
            token = current_app.ts.dumps(user.email, salt='email-confirm-key')
            confirm_url = url_for('pages.confirm_email', token=token, _external=True)
            app.send_email('Please confirm your email address.', email, confirm_url)
            flash("Please check your inbox for a confirmation email. (It may take a couple minutes.)")
            return redirect(url_for('pages.login'))

    print('registration errors', form.errors)
    return render_template('register.html', form=form)


@pages.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = current_app.ts.loads(token, salt="email-confirm-key", max_age=86400)
    except:
        abort(404)

    user = User.from_email(email)
    if not user.exists():
        abort(404)
    user.verified = True
    flash('Email confirmed!')
    return redirect(url_for('pages.login'))


@pages.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('pages.index'))


@pages.route('/home')
@login_required
def home():
    return render_template('home.html')


@pages.route('/class/new', methods=('GET', 'POST'))
@login_required
def new_class():
    form = ClassForm()
    if form.validate_on_submit():
        name = form.name.data
        description = form.description.data
        created_class = Class.create(name, current_user, description=description)
        return redirect(url_for('pages.home'))
    return render_template('new_class.html', form=form)


@pages.route('/class/view/<string:class_id>')
@login_required
def view_class(class_id):
    cls = Class(ObjectId(class_id))
    cls.flask_validate()
    return render_template('view_class.html', cls=cls)


@pages.route('/class/edit/<string:class_id>', methods=('GET', 'POST'))
@login_required
def edit_class(class_id):
    cls = Class(ObjectId(class_id))
    cls.flask_validate(edit=True)
    form = ClassForm(obj=cls.to_struct())
    if form.validate_on_submit():
        cls.name = form.name.data
        cls.description = form.description.data
        return redirect(url_for('pages.view_class', class_id=str(cls.get_id())))
    return render_template('edit_class.html', form=form, cls=cls)


@pages.route('/class/archive/<string:class_id>', methods=('POST',))
@login_required
def archive_class(class_id):
    cls = Class(ObjectId(class_id))
    cls.flask_validate(edit=True)
    cls.set_archived(True)
    return jsonify(True)


@pages.route('/class/unarchive/<string:class_id>', methods=('POST',))
@login_required
def unarchive_class(class_id):
    cls = Class(ObjectId(class_id))
    cls.flask_validate(edit=True)
    cls.set_archived(False)
    return jsonify(True)


@pages.route('/class/delete/<string:class_id>', methods=('POST',))
@fresh_login_required
def delete_class(class_id):
    cls = Class(ObjectId(class_id))
    cls.flask_validate(edit=True)
    cls.delete()
    return redirect(url_for('pages.home'))


@pages.route('/leave-unviewable-classes', methods=('GET', 'POST'))
@login_required
def update_classes():
    current_user.leave_invisible_classes()
    return 'Done.'


@pages.route('/task/new/<string:class_id>', methods=('GET', 'POST'))
@login_required
def new_task(class_id):
    form = TaskForm()
    cls = Class(ObjectId(class_id))
    cls.flask_validate()
    if form.validate_on_submit():
        date = form.date.data
        time = form.time.data
        dt = datetime.combine(date, time or datetime.min.time()) if date else None
        created_task = Task.create(form.name.data, class_=cls, date=dt,
                                   description=form.description.data,
                                   category=form.category.data)
        return redirect(url_for('pages.view_class', class_id=class_id))
    return render_template('new_task.html', form=form)


@pages.route('/task/edit/<string:task_id>', methods=('GET', 'POST'))
@login_required
def edit_task(task_id):
    task = Task(ObjectId(task_id))
    task.flask_validate(edit=True)
    form = TaskForm(obj=task.to_struct())
    form.time.data = task.date.time()
    if form.validate_on_submit():
        date = form.date.data
        time = form.time.data
        dt = datetime.combine(date, time or datetime.min.time()) if date else None
        task.name = form.name.data
        task.description = form.description.data
        task.category = form.category.data
        task.date = dt
        return redirect(url_for('pages.view_class', class_id=str(task.class_.get_id())))
    return render_template('edit_task.html', form=form, task=task)


@pages.route('/task/archive/<string:task_id>', methods=('POST',))
@login_required
def archive_task(task_id):
    task = Task(ObjectId(task_id))
    task.flask_validate(edit=True)
    task.set_archived(True)
    return jsonify(True)


@pages.route('/task/unarchive/<string:task_id>', methods=('POST',))
@login_required
def unarchive_task(task_id):
    task = Task(ObjectId(task_id))
    task.flask_validate(edit=True)
    task.set_archived(False)
    return jsonify(True)


@pages.route('/task/delete/<string:task_id>', methods=('POST',))
@fresh_login_required
def delete_task(task_id):
    task = Task(ObjectId(task_id))
    task.flask_validate(edit=True)
    task.delete()
    return jsonify(True)


@pages.route('/archive')
@login_required
def archive():
    return render_template('archive.html')


@pages.route('/calendar/')
@pages.route('/calendar/<int:year>/<int:month>')
@login_required
def calendar(year=None, month=None):
    today = datetime.today().date()
    if year and month and (not (1900 <= year <= 9999) or not(1 <= month <= 12)):
        abort(404)
    cal = UserCalendar(current_user, year=year or today.year, month=month or today.month)
    # from pprint import PrettyPrinter
    # pp = PrettyPrinter()
    # pp.pprint(cal.calendar)
    return render_template('calendar.html', calendar=cal)


@pages.route('/account')
@login_required
def account():
    flash('More account options are coming soon.')
    return redirect(url_for('pages.change_password'))
    # return render_template('account.html')


@pages.route('/change-password', methods=('GET', 'POST'))
@fresh_login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        old_password = form.current_password.data
        user = User.from_login(current_user.email, old_password)
        if user.is_authenticated:
            new_password = form.new_password.data
            user.set_password(new_password)
            flash('Password successfully changed.')
        else:
            flash('Old password incorrect.')
    return render_template('change_password.html', form=form)


@pages.route('/forgot', methods=('GET', 'POST'))
def forgot_password():
    if not current_user.is_anonymous:
        logout_user()
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data
        user = User.from_email(email)
        if user.exists():
            token = current_app.ts.dumps(user.email, salt='recover-key')
            recover_url = url_for('pages.reset_password', token=token, _external=True)
            app.send_email('Password Reset', email, recover_url)
            print(recover_url)
        flash('Please check your inbox for your password reset link. (It may take a couple minutes.)')
    return render_template('forgot_password.html', form=form)


@pages.route('/reset/<token>', methods=('GET', 'POST'))
def reset_password(token):
    try:
        email = current_app.ts.loads(token, salt="recover-key", max_age=86400)
    except:
        abort(404)

    user = User.from_email(email)
    if not user.exists():
        abort(404)
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        flash('Your password has been reset.')
        return redirect(url_for('pages.login'))

    return render_template('reset_password.html', form=form)