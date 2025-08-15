from pydantic import BaseModel, Field
from datetime import datetime, date, timezone, timedelta


from typing import Union
import json
class Email:
    def __init__(self, sender: str, recipients: list[str], date: date, subject: str, msg_id: str, label_ids: list[str], text=None):
        self.sender = sender
        self.recipients = recipients
        self.date = date
        self.subject = subject
        self.msg_id = msg_id
        self.label_ids = label_ids
        self.text = text
    
    def __str__(self):
        return json.dumps({"sender": self.sender, 
                    "sentOn": self.date.strftime("%d/%m/%Y"), 
                    "subject": self.subject, 
                    "text": self.text})
            
    
    def maker(**kwargs) -> str:
        return str(kwargs)
    def __repr__(self):
        return str(self)


class Attendee(BaseModel):
    displayName: str = Field(None, description= "The name of the attendee.")
    email: str = Field(..., description= "The email address of the attendee.")
    responseStatus: str = Field(None, description= "The response status of the attendee. Can be 'accepted', 'needsAction', or 'declined'")


class TimeAttribute(BaseModel):
    dateTime: Union[datetime, date] = Field(..., description= "The datetime specified in ISO 8601 format or date specified in YYYY-MM-DD. Use dates only for all-day events.")
    timeZone: str = Field(None, description= "The timezone the event is occurring in.")

    class Config:
        json_encoders = {
            datetime: lambda v: v.astimezone(eastern).isoformat()
        }

class RemindersAttributeMethod(BaseModel):
    method: str = Field(..., description= "The method of reminding the user. Can either be 'popup' or 'email'.")
    minutes: int = Field(..., description= "The number of minutes before the event that this reminder will be sent.")

class RemindersAttribute(BaseModel):
    useDefault: bool = Field(..., description= "A bool indicating whether the user's default reminders settings will be used. The default is a popup 10 minutes before the event.")
    overrides: list[RemindersAttributeMethod] = Field(None, description= "A list of methods to override the user's default settings. Must be provided if use_default is false.")

class CreateEvent(BaseModel):
    """Use this tool create an event in the user's primary calendar. 
Notes: The summary, start, and end are required fields. Use any fields that are provided to you."""
    start: TimeAttribute = Field(..., description= "The start date or datetime of the event.")
    end: TimeAttribute = Field(..., description= "The end date or datetime of the event. End dates are exclusive.")
    summary: str = Field(..., description= "A fitting name for the event.")
    description: str = Field(None, description= "A description of the event that may include information important for the user to remember.")
    attendees: list[Attendee] = Field(None, description= "The list of attendees that will be at this event.")
    location: str = Field(None, description= "The location of this event.")
    reminders: RemindersAttribute = Field(None, description= "Reminders settings for this event.")
    recurrence: list[str] = Field(None, description= "A list with one entry that contains a string with the recurrence rules of the event specified in the iCalendar RFC 5545 format.")


class LinkAttribute(BaseModel):
    type: str = Field(..., description= "The type of link, e.g. 'email', 'document', 'website'.")
    description: str = Field(None, description= "Label for the link")
    link: str = Field(..., description= "URL for the link.")

class CreateTask(BaseModel):
    """Use this tool create a tool in the user's primary tasklist. 
Notes: The title is a required field. Use any fields that are provided to you."""
    due: datetime = Field(None, description= "The RFC 3339 timestamp of when the task is due.")
    title: str = Field(..., description= "A fitting title for the task.")
    notes: str = Field(None, description= "Notes or description for the task.")
    status: str = Field(None, description= "Indicates the status of the task. Either 'needsAction' or 'completed'.")
    parent: str = Field(None, description= "ID of the parent task if this is a subtask.")
    links: list[LinkAttribute] = Field(None, description= "A list of links that could be important for completing the task.")

    class Config:
        json_encoders = {
            datetime: lambda v: v.astimezone(eastern).isoformat()
        }