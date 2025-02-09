import ics
import json
import os
from enum import Enum, auto
from custom_errs import *
from datetime import date, datetime, timedelta, time
from urllib.request import urlopen
from enum import Enum
from sys import platform

'''
Details:
    2019-09-25

Module details:
    Application backend logic; ics curriculum URL parsing
    class with methods and properties to return relevant
    data for a curriculum.

Synposis:
    Supply a discord chatbot with intelligence and features.
    The goal is to subscribe to the class curriculum and then
    share the current classroom for the day or week in the chat
    with a chatbot. 
'''

class Event:
    def __init__(self, *args, **kwargs):
        self.body = None
        self.location = None
        self.date = None
        self.curriculum_event = False
        self.weekdays = []
        self.time = time()
        self.alarm = timedelta()

        for key in kwargs:
            setattr(self, key, kwargs[key])

    def __repr__(self):
        what = self.body
        where = self.location
        
        if self.date:
            when = f'{self.date} - {self.time.strftime("%H:%M")}'
        else:
            when = self.time.strftime("%H:%M")
        
        return f'Vad: {what}\nNär: {when}\nVar: {where}\n'

    @property
    def curriculum_event(self):
        return self._curriculum_event

    @curriculum_event.setter
    def curriculum_event(self, value):
        self._curriculum_event = value    

    @property
    def body(self):
        if self._body:
            return self._body
        return '-'

    @body.setter
    def body(self, value):
        self._body = value

    @property
    def location(self):
        if self._location:
            return self._location
        return '-'

    @location.setter
    def location(self, value):
        self._location = value

    @property
    def weekdays(self):
        if self._weekdays:
            return self._weekdays
        return []
    
    @weekdays.setter
    def weekdays(self, value):
        if isinstance(value, list):
            self._weekdays = value
        else:
            raise AttributeError(f'Expected {list}, got {type(value)}')

    @property
    def time(self):
        return self._time
        
    @time.setter
    def time(self, value):
        if isinstance(value, time):
            self._time = value
        else:
            raise AttributeError(f'Expected {time}, got {type(value)}')

    @property
    def date(self):
        return self._date

    @date.setter
    def date(self, value):
        if isinstance(value, date) or isinstance(value, type(None)):
            self._date = value
        else:
            raise AttributeError(f'Expected {date} or {None}, got {type(value)}')

    @property
    def alarm(self):
        return self._alarm

    @alarm.setter
    def alarm(self, value):
        if isinstance(value, timedelta):
            try:
                combined = datetime.combine(datetime.today(), self.time)
                self._alarm = (combined - value).time()
            except Exception as e:
                raise EventReminderTimeAdjustError(e)
        else:
            raise AttributeError(f'Expected {timedelta}, got {type(value)}')

    def to_json(self):
        return json.dumps(
            self, default = lambda: self.__dict__,
            sort_keys = True, ensure_ascii = False, 
            indent = 4)

class Weekdays(Enum):
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7

class Schedule:
    '''
    Parse an .ics url and fetch the data for this calendar.
    The data will be used to return classroom for the day,
    the day after and similar requests in a simple format 
    with properties.
    '''
    def __init__(self, url = str):
        self._url = url
        self._curriculum_events = []
        self._activities = []
        self.set_calendar()
        self.truncate_event_name()
        
    def adjust_event_hours(self, hourdelta = int):
        '''
        Adjust the hour in a calendar event by (n) hours.
        Create a time() property for both the event begin and 
        event end, with corrected hour stamps according to hourdelta
        parameter. The instance attribute will be accessible through
        self.begin.time and self.end.time.
        '''
        for event in self.curriculum:
            try:
                year = self.current_time.year
                month = self.current_time.month
                day = self.current_time.day
                
                begin_hour, begin_minute = event.begin.hour, event.begin.minute
                end_hour, end_minute = event.end.hour, event.end.minute

                begin_time = datetime(year, month, day, begin_hour, begin_minute)
                end_time = datetime(year, month, day, end_hour, end_minute)
                
                begin_time += timedelta(hours = hourdelta)
                end_time += timedelta(hours = hourdelta)

                event.begin.adjusted_time = time(begin_time.hour, begin_time.minute)
                event.end.adjusted_time = time(end_time.hour, end_time.minute)

            except ValueError as e:
                msg = f'Could not adjust {event} with {hourdelta} hrs: {e}'
                raise TimezoneAdjustmentError(msg)
        return True

    def set_calendar(self):
        '''
        Get data from the timeedit servers containing the
        curriculum for class IoT19 2 weeks ahead. This callable
        will refresh the .ics Calendar object.
        '''
        try:
            calendar = ics.Calendar(urlopen(self._url).read().decode())
        except ValueError:
            msg = 'Could not parse calendar url, verify server status and access.'
            raise InvalidCalendarUrl(msg)
        self._calendar = calendar

    def truncate_event_name(self):
        '''
        Truncate sensitive name data in events, containing the
        name of the teacher holding the class. This will reduce
        the privacy issue of storing names in log files.
        '''

        for event in self.curriculum:
            event.name = f"{event.name.split(',')[0]},{event.name.split(',')[-1]}"

    @property
    def today(self):
        return datetime.now().date()

    @property
    def weekday(self):
        for day in Weekdays:
            if self.today.isoweekday() == day.value:
                return day

    @property
    def current_time(self):
        return datetime.now()

    @property
    def curriculum(self):
        _curriculum = list(self._calendar.events)
        _curriculum.sort()
        return _curriculum

    @property
    def todays_events(self):
        return [i for i in self.curriculum if i.begin.date() == self.today]
    
    @property
    def todays_lessons(self):
        '''
        Iterate through the lessons of today, return these in a friendly
        string with properties such as start and end time with locations.
        '''
        output = []

        if len(self.todays_events):
            for event in self.todays_events:
                name = event.name.split(',')[-1].strip()
                event_start = event.begin.adjusted_time.strftime('%H:%M')
                event_end = event.end.adjusted_time.strftime('%H:%M')
                output.append(f'{name}, {event_start} - {event_end} i {event.location}')
            return output
        return None

    @property
    def next_lesson(self):
        '''
        Evaluate what lesson is the next on curriculum. Iterate
        through the list of lessons for today. Compare the current
        time with each lesson start time, return the upcoming one.
        Adjust for calendar timezone with 2hrs. If no lesson is found
        for today, iterate over the entire sorted curriculum and return
        the first lesson that lies in the future.
        '''
        lesson = None

        if self.todays_events:
            for event in self.todays_events:
                if self.current_time.hour < event.begin.adjusted_time.hour:
                    lesson = event
                    break
        if not lesson:
            for event in self.curriculum:
                if event.begin.date() > self.today:
                    lesson = event
                    break
        return lesson

    @property
    def next_lesson_classroom(self):
        return self.next_lesson.location

    @property
    def next_lesson_name(self):
        return self.next_lesson.name
    
    @property
    def next_lesson_time(self):
        return f'{self.next_lesson.begin.adjusted_time.strftime("%H:%M")}'

    @property
    def next_lesson_date(self):
        return f'{self.next_lesson.begin.date()}'