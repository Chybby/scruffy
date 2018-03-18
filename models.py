from __future__ import print_function

import logging

from google.appengine.ext import ndb


class User(ndb.Model):
    name = ndb.StringProperty(required=True)

    @property
    def fbid(self):
        return self.key.id()

    @classmethod
    def get(cls, fbid):
        return ndb.Key(cls, fbid).get()

    @classmethod
    def create(cls, fbid, name):
        user = User(id=fbid, name=name)
        k = user.put()
        return user


class Roster(ndb.Model):
    queue = ndb.KeyProperty(kind=User, repeated=True)
    num_passed = ndb.IntegerProperty(default=0)
    should_send_reminder = ndb.BooleanProperty(default=False)
    bins_done = ndb.BooleanProperty(default=True)

    SUCCESS = 0
    NOT_YOUR_TURN = 1
    EVERYONE_PASSED = 2

    NORMAL_NOTIFICATION = 3
    NAUGHTY_NOTIFICATION = 4

    _ROSTER_KEY = 'roster'

    @classmethod
    @ndb.transactional
    def register_new_user(cls, user):
        roster = cls._get_roster()
        roster.queue.append(user.key)
        roster.put()

    @classmethod
    @ndb.transactional
    def set_done(cls, user):
        roster = cls._get_roster()

        if roster.queue[0] != user.key:
            return cls.NOT_YOUR_TURN

        if roster.bins_done:
            return cls.NOT_YOUR_TURN

        roster.queue.pop(0)
        roster.queue.append(user.key)
        roster.bins_done = True
        roster.num_passed = 0
        roster.should_send_reminder = False
        roster.put()

        return cls.SUCCESS

    @classmethod
    @ndb.transactional
    def set_passed(cls, user):
        roster = cls._get_roster()

        if roster.queue[0] != user.key:
            return cls.NOT_YOUR_TURN

        if roster.bins_done:
            return cls.NOT_YOUR_TURN

        roster.should_send_reminder = False

        if roster.num_passed == len(roster.queue) - 1:
            roster.queue.pop(0)
            roster.queue.append(user.key)
            roster.num_passed = 0
            roster.bins_done = True
            roster.put()
            return cls.EVERYONE_PASSED

        roster.queue[0] = roster.queue[roster.num_passed + 1]
        roster.queue[roster.num_passed + 1] = user.key
        roster.num_passed += 1
        roster.put()
        return cls.SUCCESS

    @classmethod
    @ndb.transactional
    def set_remind(cls, user):
        roster = cls._get_roster()

        if roster.queue[0] != user.key:
            return cls.NOT_YOUR_TURN

        if roster.bins_done:
            return cls.NOT_YOUR_TURN

        roster.should_send_reminder = True
        roster.put()
        return cls.SUCCESS

    @classmethod
    @ndb.transactional
    def send_reminder(cls):
        roster = cls._get_roster()

        if not roster.should_send_reminder:
            return None

        roster = cls._get_roster()
        user_key = roster.queue[0]
        roster.should_send_reminder = False
        roster.put()
        return user_key

    @classmethod
    @ndb.transactional
    def send_notification(cls):
        roster = cls._get_roster()

        user_key = roster.queue[0]
        if roster.bins_done:
            roster.bins_done = False
            roster.put()
            return cls.NORMAL_NOTIFICATION, user_key
        else:
            return cls.NAUGHTY_NOTIFICATION, user_key

    @classmethod
    def get_next(cls):
        return cls._get_roster().queue[0].get()

    @classmethod
    def get_queue(cls):
        return ndb.get_multi(cls._get_roster().queue)

    @classmethod
    def get_passers(cls):
        roster = cls._get_roster()
        return ndb.get_multi(roster.queue[1:roster.num_passed + 1])

    @classmethod
    def get_bins_done(cls):
        return cls._get_roster().bins_done

    @classmethod
    def get_should_send_reminder(cls):
        return cls._get_roster().should_send_reminder

    @classmethod
    def _get_roster(cls):
        return cls.get_or_insert(cls._ROSTER_KEY)
