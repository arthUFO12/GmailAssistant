import os.path
import base64
import re
import threading
import time
import json

from pathlib import Path
from typing import Union, Callable
from datetime import date, datetime
from urllib.parse import urlparse
from dateutil import parser
from pydantic import BaseModel

import pytz
import iso8601

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from data_schemas import CreateTask, CreateEvent

calendar = None
tasks = None
default_tasklist = None
time_zone = None


SCOPES = ["https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/tasks"]


def init_tasks(creds):
    global tasks, default_tasklist
    tasks = build('tasks', 'v1', credentials=creds)
    tasklists = tasks.tasklists().list().execute().get('items', [])
    if tasklists: default_tasklist = tasklists[0]['id']

def init_calendar(creds):
    global calendar, time_zone
    calendar = build('calendar', 'v3', credentials=creds)
    tz = calendar.calendarList().get(calendarId='primary').execute()
    time_zone = pytz.timezone(tz['timeZone'])


def add_task(t: CreateTask) -> str:
    global tasks

    try:
        task_result = tasks.tasks().insert(
            tasklist=default_tasklist,
            body=t.model_dump(mode='json', exclude_none=True)
        ).execute()
    except HttpError as error:
        return f'An error occurred creating the task: {error}'

    return f'Task created with ID:\"{task_result['id']}\"'

def reschedule_task(task_id: str, due: datetime) -> str:
    global tasks
    try:
        task_result = tasks.tasks().patch(
            tasklist=default_tasklist,
            task=task_id,
            body={
                "due": time_zone.localize(due).isoformat() if is_naive(due) else due.isoformat()
            }
        ).execute()
    except HttpError as error:
        return f'An error occurred rescheduling the task: {error}'

    return f'Task with ID \"{task_id}\" updated to be due at \"{due.isoformat()}\".'


def remove_task(task_id: str) -> str:
    global tasks
    
    try:
        tasks.tasks().delete(
            taskslist=default_tasklist,
            task=task_id
        ).execute()
    except HttpError as error:
        return f'An error occurred removing the task: {error}'

    return f'Task with ID \"{task_id}\" deleted.'


def add_event(e: CreateEvent) -> str:
    global calendar

    try:
        event_result = calendar.events().insert(
            calendarId="primary",
            body=e.model_dump(mode='json', exclude_none=True)
        ).execute()
    except HttpError as error:
        return f'An error occurred creating the event: {error}'

    return f'Event created with ID:\"{event_result['id']}\".'

def reschedule_event(event_id: str, start: datetime, end: datetime) -> str:
    global calendar

    try:
        calendar.events().patch(
            calendarId="primary",
            eventId=event_id,
            body={
                "start": {
                    "dateTime": time_zone.localize(start).isoformat() if is_naive(start) else start.isoformat()
                },
                "end": {
                    "dateTime": time_zone.localize(end).isoformat() if is_naive(end) else end.isoformat()
                }
            }
        ).execute()
    except HttpError as error:
        return f'An error occurred rescheduling the event: {error}'

    return f'Event with ID \"{event_id}\" updated to start at \"{start.isoformat()}\" and end at \"{end.isoformat()}\".'

def remove_event(event_id: str):
    global calendar
    
    try:
        calendar.events().delete(
            calendarId='primary',
            eventId=event_id
        ).execute()
    except HttpError as error:
        return f'An error occurred removing the event: {error}'

    return f'Event with ID \"{event_id}\" deleted.'



def is_naive(dt: datetime):
    return dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None

def get_events_in_range(start: datetime, end: datetime) -> str:
    global calendar

    try:
        events_result = calendar.events().list(
            calendarId='primary', timeMin=time_zone.localize(start).isoformat() if is_naive(start) else start.isoformat(),
            timeMax=time_zone.localize(end).isoformat() if is_naive(end) else end.isoformat(),
            maxResults=20, singleEvents=True,
            orderBy='startTime'
        ).execute()
    except HttpError as error:
        return f'An error occurred retrieving events: {error}'

    events = events_result.get('items', [])

    event_list = []
    for e in events:
        data = {
            "id": e['id'],
            "start": e['start'],
            "end": e['end'],
            "summary": e['summary'],
            "description": e['description'][:30] if 'description' in e else None,
            "location": e.get('location', None),
            "recurrence": e.get('recurrence', None),
            "reminders": e.get('reminders', None),
            "attendees": e.get('attendees', None)
        }

        if data['attendees'] and len(data['attendees']) > 5:
            del data['attendees']

        cleaned_data = {k: v for k, v in data.items() if v is not None}
        event_list.append(cleaned_data)

    return "JSON list of events in this range:\n" + json.dumps(event_list, indent=2) + "\n"


def get_tasks_in_range(start: datetime, end: datetime) -> str:
    global tasks

    try:
        results = tasks.tasklists().list(maxResults=10).execute()
    except HttpError as error:
        return f'An error occurred retrieving tasks: {error}'
    tasklists = results.get('items', [])

    tasks_in_range = []
    for tasklist in tasklists:
        try:
            tasks_results = tasks.tasks().list(
                tasklist=tasklist['id'],
                showCompleted=False,
                showDeleted=False,
                maxResults=10
            ).execute()
        except HttpError as error:
            return f'An error occurred retrieving tasks: {error}'

        items = tasks_results.get('items', [])
        
        for task in items:
            time = datetime.fromisoformat(task['due']).replace(tzinfo=None)
            
            time = time_zone.localize(time)
            
            if start <= time <= end:
                tasks_in_range.append(task)

    return "JSON list of tasks in this range:\n" + json.dumps(tasks_in_range, indent=4) + "\n"

def get_creds(creds_dir: Union[Path, str], scopes: list[str]):
    creds = None

    creds_json = os.path.join(creds_dir, "credentials.json")
    token_json = os.path.join(creds_dir, "token.json")

    if os.path.exists(token_json):
        creds = Credentials.from_authorized_user_file(token_json, scopes)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                creds_json, scopes
            )

            creds = flow.run_local_server(port=0)

        with open(token_json, "w") as token:
            token.write(creds.to_json())

    return creds

creds = get_creds("ArthurCreds", SCOPES)
init_calendar(creds)
init_tasks(creds)

