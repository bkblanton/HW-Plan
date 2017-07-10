from datetime import datetime, date, time, timedelta
from collections import defaultdict
import flask_pymongo.wrappers
from flask import current_app, abort
from flask_login import current_user


class MongoDocument:
    @staticmethod
    def get_collection() -> flask_pymongo.wrappers.Collection:
        pass

    def __init__(self, _id):
        self._id = _id
        self._cache = dict()

    def __eq__(self, other):
        return self.get_id() == other.get_id()

    def get_document(self, override_cache=False) -> dict:
        if override_cache or ('document' not in self._cache):
            self._cache['document'] = self.get_collection().find_one({'_id': self.get_id()})
        return self._cache['document']

    def update_cache(self):
        self.get_document(override_cache=True)

    def delete(self):
        return self.get_collection().delete_one({'_id': self.get_id()})

    def exists(self):
        return self.get_id() is not None and self.get_document() is not None

    def get_id(self):
        return self._id

    def _replace_document(self, document):
        self.get_collection().replace_one(
            {'_id': self.get_id()},
            document
        )

    def mongo_get(self, key, default=None, override_cache=False):
        if not self.exists():
            return default
        return self.get_document(override_cache=override_cache).get(key, default)

    def mongo_set(self, key, value):
        self.get_collection().update_one(
            {'_id': self.get_id()},
            {
                '$set': {
                    key: value
                }
            }
        )
        self.update_cache()

    def mongo_push(self, key, value, ignore_duplicates=True):
        if ignore_duplicates:
            lst = self.mongo_get(key)
            for elem in lst:
                if elem == value:
                    return
        self.get_collection().update_one(
            {'_id': self.get_id()},
            {
                '$push': {
                    key: value
                }
            }
        )
        self.update_cache()

    def to_struct(self):
        class Struct:
            def __init__(self, **entries):
                self.__dict__.update(entries)

        return Struct(**self.get_document())


class ValidationMixin:
    def flask_validate(self, edit=False):
        if not self.exists():
            abort(404)
        if not self.user_can_view(current_user):
            abort(403)
        if edit and not self.user_can_edit(current_user):
            abort(403)


class User(MongoDocument, ValidationMixin):
    def __init__(self, _id: int, is_authenticated=False):
        self.is_authenticated = is_authenticated
        super().__init__(_id)

    @staticmethod
    def get_collection():
        return current_app.mongo.db.users

    @classmethod
    def from_email(cls, email):
        """Create an unauthenticated user from a username."""
        # document = current_app.mongo.db.users.find_one({'username': re.compile(email, re.IGNORECASE)})
        # document = cls.get_collection().find_one(  # More complicated, but faster
        #     {
        #         '$text': {
        #             '$search': email.lower(),
        #             '$caseSensitive': False
        #         },
        #     }
        # )
        document = current_app.mongo.db.users.find_one({'email': email.lower()})
        if document is not None:
            return cls(document['_id'])
        return User(None)

    @classmethod
    def from_login(cls, email, password):
        """Create and authenticate a user with a username and password."""
        user = cls.from_email(email)
        if user is not None:
            user.authenticate(password)
        return user

    @staticmethod
    def hash_password(password):
        return current_app.bcrypt.generate_password_hash(password)

    @classmethod
    def create(cls, email, password):
        """Add a new user to the database."""
        user_id = current_app.mongo.db.counters.find_one_and_update({'_id': 'user_id'}, {'$inc': {'seq': 1}})['seq']
        password_hash = cls.hash_password()
        result = cls.get_collection().insert_one({'_id': user_id,
                                                  'email': email.lower(),
                                                  'password': password_hash,
                                                  'registered_on': datetime.utcnow(),
                                                  'class_ids': [],
                                                  'display_name': email.split('@', maxsplit=1)[0],
                                                  'verified': False
                                                  })
        return cls(result.inserted_id)

    @property
    def is_active(self):
        return self.is_authenticated and not self.is_anonymous and self.verified  # TODO: check user is verified

    @property
    def is_anonymous(self):
        return self.get_id() is None

    def get_document(self, override_cache=False) -> dict:
        if self.is_anonymous:
            return None
        return super().get_document(override_cache=override_cache)

    def authenticate(self, password):
        """Authenticate the user by checking if the password hashes match."""
        if not self.exists():
            return
        self.is_authenticated = current_app.bcrypt.check_password_hash(
            self.mongo_get('password'),
            password)
        return self.is_authenticated

    @property
    def email(self):
        return self.mongo_get('email')

    def set_password(self, password):
        password_hash = self.hash_password(password)
        self.mongo_set('password', password_hash)

    def get_classes(self, archived=True, unarchived=True):
        if not self.exists():
            return
        query_dict = {
            '_id': {
                '$in': list(self.mongo_get('class_ids'))
            }
        }
        if not (archived and unarchived): query_dict['archived'] = archived
        query = Class.get_collection().find(query_dict)
        for class_document in query:
            yield Class(class_document.get('_id'))

    def get_tasks(self, limit=None, order=1, time_range: (datetime, datetime) = None, archived=True, unarchived=True):
        tasks = (task
                 for cls in self.get_classes(archived=archived)
                 for task in cls.get_tasks(order=0, time_range=time_range, archived=archived, unarchived=unarchived))
        if limit:
            tasks = (task for task, _ in zip(tasks, range(limit)))
        if order:
            tasks = sorted(tasks, key=lambda task: task.date, reverse=(order < 1))
        for task in tasks:
            yield task

    def create_class(self, name, *args, **kwargs):
        return Class.create(name, self, *args, **kwargs)

    def join_class(self, cls):
        if cls.user_can_view(self):
            self.mongo_push('class_ids', cls.get_id())
            return True
        return False

    def leave_class(self, class_to_leave):
        classes = self.mongo_get('class_ids')
        for i, class_id in enumerate(classes):
            if class_id == class_to_leave.get_id():
                classes.pop(i)
                self.mongo_set('class_ids', classes)
                return True
        return False

    def leave_invisible_classes(self):
        for cls in self.get_classes(archived=True):
            if not cls.user_can_view(self):
                self.leave_class(cls)

    @property
    def verified(self):
        return self.mongo_get('verified', default=False)

    @verified.setter
    def verified(self, value):
        self.mongo_set('verified', value)

    @property
    def name(self):
        return self.mongo_get('display_name')

    @name.setter
    def name(self, name):
        self.mongo_set('name', name)


class Class(MongoDocument, ValidationMixin):
    @staticmethod
    def get_collection():
        return current_app.mongo.db.classes

    @classmethod
    def create(cls, name, owner: User, description=None, category=None):
        result = cls.get_collection().insert_one({
            'name': name,
            'owner_id': owner.get_id(),
            'description': description.strip() if description else None,
            'archived': False,
            'date_created': datetime.utcnow(),
            'member_ids': [],
        })
        created_class = cls(result.inserted_id)
        owner.join_class(created_class)
        return created_class

    def create_task(self, _name, *args, **kwargs):
        return Task.create(_name, self, *args, **kwargs)

    def add_student(self, student: User):
        self.mongo_push('member_ids', student.get_id(), ignore_duplicates=True)
        # print(self.mongo_get('member_ids'))

    @property
    def owner(self):
        return User(self.mongo_get('owner_id'))

    @owner.setter
    def owner(self, value: User):
        self.mongo_set('owner_id', value.get_id())

    @property
    def name(self):
        return self.mongo_get('name')

    @name.setter
    def name(self, name):
        self.mongo_set('name', name.strip())

    @property
    def description(self):
        return self.mongo_get('description')

    @description.setter
    def description(self, description):
        self.mongo_set('description', description.strip())

    @property
    def archived(self):
        return self.mongo_get('archived')

    def set_archived(self, archived, archive_tasks=True):
        if archived and archive_tasks:
            for task in self.get_tasks(archived=False):
                task.set_archived(True)
        self.mongo_set('archived', archived)

    def get_tasks(self, limit=None, order=1, time_range: (datetime, datetime) = None, archived=True, unarchived=True):
        query_dict = {
            'class_id': self.get_id()
        }
        if not (archived and unarchived):
            query_dict['archived'] = archived
        if time_range is not None:
            query_dict['date'] = {
                '$gte': time_range[0],
                '$lt': time_range[1]
            }
        query = Task.get_collection().find(query_dict)
        if order:
            query = query.sort('date', order)
        if limit:
            query = query.limit(limit)
        for task_document in query:
            yield Task(task_document.get('_id'))

    def delete(self):
        for task in self.get_tasks():
            task.delete()
        for student in self.get_members():
            student.leave_class(self)
        super().delete()

    def user_can_edit(self, user: User = None):
        if not self.exists():
            return False
        if user is None:
            user = current_user
        return self.exists() and user == self.owner

    def get_members(self):
        if not self.exists():
            return
        yield self.owner
        for student_id in self.mongo_get('member_ids', default=[]):
            yield User(student_id)

    def user_can_view(self, user: User = None):
        if not self.exists():
            return False
        if user is None:
            user = current_user
        for member in self.get_members():
            if user == member:
                return True
        return False


class Task(MongoDocument, ValidationMixin):
    categories = {'Homework', 'Exam', 'Quiz', 'Test', 'Project', 'Presentation', 'Classwork'}

    @staticmethod
    def get_collection():
        return current_app.mongo.db.tasks

    @classmethod
    def create(cls, name, class_: Class, date: datetime = None, category=None, description=None):
        result = cls.get_collection().insert_one({
            'name': name,
            'class_id': class_.get_id(),
            'archived': False,
            'description': description,
            'date': date,
            'category': category,
            'date_created': datetime.utcnow(),
        })
        return cls(result.inserted_id)

    def to_struct(self):
        obj = super().to_struct()
        dt = self.date
        if dt.time() != datetime.min.time():
            obj.__dict__.update({'time': self.date.time()})
        return obj

    @property
    def class_(self):
        return Class(self.mongo_get('class_id'))

    @property
    def owner(self):
        return self.class_.owner

    @property
    def name(self):
        return self.mongo_get('name')

    @name.setter
    def name(self, name):
        self.mongo_set('name', name)

    @property
    def description(self):
        return self.mongo_get('description')

    @description.setter
    def description(self, description):
        self.mongo_set('description', description)

    @property
    def date(self) -> datetime:
        return self.mongo_get('date')

    @date.setter
    def date(self, date):
        self.mongo_set('date', date)

    @property
    def category(self):
        return self.mongo_get('category')

    @category.setter
    def category(self, category):
        self.mongo_set('category', category)

    @property
    def archived(self):
        return self.mongo_get('archived')

    @property
    def class_id(self):
        return self.mongo_get('class_id')

    def set_archived(self, archived):
        self.mongo_set('archived', archived)

    def user_can_edit(self, user):
        return self.class_.user_can_edit(user)

    def user_can_view(self, user):
        return self.class_.user_can_view(user)


class UserCalendar:
    def __init__(self, user, year, month):
        self.year = year
        self.month = month
        self.user = user

        month_start = date(self.year, self.month, 1)
        cal_start = month_start - timedelta(days=(month_start.weekday() + 1) % 7)
        row_start = date(cal_start.year, cal_start.month, cal_start.day)
        calendar = []
        while row_start.month + (row_start.year - month_start.year) * 12 <= month_start.month:
            row = []
            day = date(row_start.year, row_start.month, row_start.day)
            for _ in range(7):
                row.append({'date': day, 'tasks': defaultdict(list)})
                day += timedelta(days=1)
            row_start = date(day.year, day.month, day.day)
            calendar.append(row)
        self.calendar = calendar

        tasks = list(user.get_tasks(order=0, archived=False, time_range=(
            datetime.combine(cal_start, datetime.min.time()),
            datetime.combine(calendar[-1][-1]['date'], datetime.min.time()) + timedelta(days=1)
        )))
        classes = {}
        for task in tasks:
            days = (task.date.date() - cal_start).days
            class_id = task.class_id
            if class_id not in classes:
                classes[class_id] = Class(class_id)
            cls = classes[class_id]
            calendar[days // 7][days % 7]['tasks'][(class_id, cls.name)].append(task)

    def rows(self):
        for row in self.calendar:
            yield row
