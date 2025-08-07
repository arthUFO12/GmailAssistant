import os
import json

from datetime import date, datetime
from pydantic import BaseModel, Field, validate_call
from typing import TypedDict


import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import ChatMessage, ToolMessage, SystemMessage, HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

from data_schemas import CreateEvent, CreateTask, Email
import calendar_tools

os.environ['GOOGLE_API_KEY'] = json.load(open('ArthurCreds/gemini.json'))['key']


def make_email_prompt(inject: str):
    return f"""You are a helpful AI assistant responsible for managing a user's Gmail inbox and Google Calendar.
Your goal is to help the user efficiently respond to emails and manage events by using ONLY the tools provided to you. 
You should think step by step and decide when to use tools to take action. Ensure you reason in every response.
Respond in this format:

Thought: [Your reasoning]
Action: [The structured tool call JSON objects]

Task:
The user has received an email. Here is a structured breakdown of the contents.

{inject}

1. Let the user know about the information contained in the email in 1 to 2 sentences.
2. Ask the user whether they’d like you to use any of the relevant tools available to you.
3. Complete any tasks that the user requests from you.

Info:
- The date is {calendar_tools.today.isoformat()}.
- The timezone is {calendar_tools.time_zone.zone}.

Rules:
- Datetimes will be given to you in ISO8601 format, but give these dates to the user in [month name] [day] format with the time specified in AM or PM.
- You MUST check user availability before scheduling events AND tasks. If there are conflicts, ask the user what you should do. Ensure the user wants to schedule the event.
- You may ONLY use the `PromptUser`, `GiveUserInfo`, and `ConfirmRequestCompletion` tools to speak to the user.
- You may ONLY use `PromptUser`, `GiveUserInfo`, and `ConfirmRequestCompletion` in one response, all other tools must be called in different responses.
- After `ConfirmRequestCompletion` is called, send a `STOP` response."""


def make_conversation_prompt():
    return f"""You are a helpful AI assistant responsible for managing a user's Gmail inbox and Google Calendar.
Your goal is to help the user efficiently respond to emails and manage events by using ONLY the tools provided to you. 
You should think step by step and decide when to use tools to take action. Ensure you reason in every response.
Respond in this format:

Thought: [Your reasoning]
Action: [The structured tool call JSON objects]

Task:
The user has opened a chat conversation with you.

1. Ask the user what they would like you to do.
2. Complete their request if it can be performed using any of your tools. If not, inform the user and STOP.
3. Ask the user if they need anything else, and if not, STOP.

Info:
- The date is {calendar_tools.today.isoformat()}.
- The timezone is {calendar_tools.time_zone.zone}.

Rules:
- Give dates to the user in [month name] [day] format.
- You MUST check user availability before scheduling events AND tasks. If there are conflicts, ask the user what you should do. Ensure the user wants to schedule the event.
- You may ONLY use the `PromptUser`, `GiveUserInfo`, and `ConfirmRequestCompletion` tools to speak to the user.
- You may ONLY use `PromptUser`, `GiveUserInfo`, and `ConfirmRequestCompletion` in one response, all other tools must be called in different responses.
- After `ConfirmRequestCompletion` is called, send a `STOP` response."""



@tool
@validate_call
def search_user_availability(
        start: datetime = Field(..., description="Start of date of the search range in ISO 8601 format."), 
        end: datetime = Field(..., description="End of date of the search range in ISO 8601 format.")
    ):
    """Use this to check the user's availability.
Instructions: Enter the start and end times to search. You will receive a list of event objects back.\n Event object important fields:\n 1. summary - name of the event.\n 2. start - start time and timezone of the event.\n 3. end - end time and timezone of the event."""
    return calendar_tools.get_events_in_range(start,end) + calendar_tools.get_tasks_in_range(start,end)

@tool
@validate_call
def change_event_time(
        event_id: str = Field(..., description="ID of the event provided by the Google."),
        start: datetime = Field(..., description="The new start time of the event in ISO 8601 format."),
        end: datetime = Field(..., description="The new end time of the event in ISO 8601 format.")
    ):
    """Use this to reschedule an event.
Instructions: Enter the Google Services API provided ID. If you don't have it, first search for the event using search_user_availability and obtain the ID from the tool."""
    return calendar_tools.reschedule_event(event_id, start, end)

@tool
@validate_call
def cancel_event(
        event_id: str = Field(..., description="ID of the event provided by Google.")
    ):
    """Use this tool to delete an event.
Instructions:  Enter the Google Service API provided ID. If you don't have it, first search for the event using search_user_availability and obtain the ID from the tool."""
    return calendar_tools.remove_event(event_id)

@tool
@validate_call
def change_task_time(
        task_id: str = Field(..., description="ID of the task provided by Google."),
        due: datetime = Field(..., description="The new due time of the event in ISO 8601 format.")
    ):
    """Use this tool to change the time of a task.
Instructions: Enter the Google Services API provided ID of the task you want to reschedule along with the new due time. If you don't have it, first search for the task using search_user_availability and obtain the ID from the tool."""
    return calendar_tools.reschedule_task(task_id, due)

@tool
@validate_call
def cancel_task(
        task_id: str = Field(..., description="ID of the task provided by Google.")
    ):
    """Use this tool to delete a task.
Instructions: Enter Google Services API provided ID for the task you want to cancel. If you don't have it, first search for the task using search_user_availability and obtain the ID from the tool."""
    return calendar_tools.remove_task(task_id)

class ConfirmRequestCompletion(BaseModel):
    """Use this to send the user a message indicating their request was completed. 
Instructions: After completing all of the user's requests, send a confirmation message to them using this tool. DO NOT ask follow-up questions."""
    message: str

class GiveUserInfo(BaseModel):
    """Use this to send the user useful information. 
Instructions: Enter a string containing the information you want to give to the user. This string should not contain questions. If you want to give the user information and then a follow-up question, call GiveUserInfo and then PromptUser in succession."""
    info: str

class PromptUser(BaseModel):
    """Use this to receive user input. 
Instructions: Enter a question to receive input from the user."""
    prompt: str


tools = [change_event_time, cancel_event, change_task_time, cancel_task, search_user_availability]
tool_node = ToolNode(tools)

summarizer = ChatGoogleGenerativeAI(model='gemini-1.5-pro')
model = summarizer.bind_tools(tools + [PromptUser, GiveUserInfo, CreateEvent, CreateTask, ConfirmRequestCompletion])

def talk_to_user(state):
    last_message = state["messages"][-1]
    
    tool_responses = []
    if (call := check_for_tool(last_message, "GiveUserInfo")):
        tool_responses.append(give_user_info(call))

    if (call := check_for_tool(last_message, "PromptUser")):
        tool_responses.append(prompt_user(call))

    if (call := check_for_tool(last_message, "ConfirmRequestCompletion")):
        tool_responses.append(confirm_request_completion(call))
    

    return {"messages": state["messages"] + tool_responses}

def summarize(email) -> str: 
    prompt = f"""You are an email inbox summarizer. Your task is to supply the inbox manager with structured summary of the most pertinent information contained in incoming emails.
The response should contain the following fields:

- "type": Can be "event", "task", or "null".
    ~ "event" is used if the email contains obligations that have a definitive start or end time, e.g. a meeting, trip, or doctor's appointment.
    ~ "task" is used if the email contains obligations that have a time they must be performed by, e.g. getting groceries or completing a homework assignment.
    ~ "null" is used if the email contains information doesn't fit into either of the previous categories. If the summary type is null, do not enter any other fields.
- "description": A general overview that captures the content of the obligation.
- "time": A string specifying the date and time of the obligation. Dates should be in ISO8601 format. 
- "notes": Any extra details that might be useful for the inbox manager to know.

Incoming email:
{email}

Produce a structured summary of the email containing the above fields. Respond in JSON.
"""
    response = summarizer.invoke(prompt)
    
    return response.content


def check_for_tool(message: BaseMessage, tool_name: str) -> dict:
    for i in message.tool_calls:
        if i["name"] == tool_name:
            return i
        
    return None

def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    # If there is no function call, then we finish
    

    if not last_message.tool_calls:
        return END
    # If tool call is asking Human, we return that node
    # You could also add logic here to let some system know that there's something that requires Human input
    # For example, send a slack message, etc
    elif check_for_tool(last_message, "PromptUser"):
        return "talk_to_user"
    elif check_for_tool(last_message, "GiveUserInfo"):
        return "talk_to_user"
    elif check_for_tool(last_message, "ConfirmRequestCompletion"):
        return "talk_to_user"
    elif check_for_tool(last_message, "CreateEvent"):
        return "create_event"
    elif check_for_tool(last_message, "CreateTask"):
        return "create_task"
    # Otherwise if there is, we continue
    else:
        return "action"

def call_model(state):
    messages = state["messages"]

    
    response = model.invoke(messages)
    # We return a list, because this will get added to the existing list
    
    return {"messages": messages + [response]}

def give_user_info(call: dict) -> ToolMessage:
    tool_call_id = call["id"]
    info = GiveUserInfo.model_validate(call["args"])
    print(info.info)
    # highlight-next-line
    tool_message = ToolMessage(tool_call_id=tool_call_id, content="User received provided information.")

    return tool_message

def confirm_request_completion(call: dict) -> ToolMessage:
    tool_call_id = call["id"]
    message = ConfirmRequestCompletion.model_validate(call["args"])
    print(message.message)
    # highlight-next-line
    tool_message = ToolMessage(tool_call_id=tool_call_id, content="User received request completion confirmation.")

    return tool_message

def prompt_user(call: dict) -> ToolMessage:
    tool_call_id = call["id"]
    ask = PromptUser.model_validate(call["args"])
    # highlight-next-line
    response = input(ask.prompt + '\n')
    resp = f'The user replied \"{response}\"'
    tool_message = ToolMessage(tool_call_id=tool_call_id, content=resp)

    return tool_message

def create_event(state):
    call = state["messages"][-1].tool_calls[0]
    tool_call_id = call["id"]
    event = CreateEvent.model_validate(call["args"])
    response = calendar_tools.add_event(event)
    tool_message = ToolMessage(tool_call_id=tool_call_id, content=response)

    return {"messages": state["messages"] + [tool_message]}

def create_task(state):
    call = state["messages"][-1].tool_calls[0]
    tool_call_id = call["id"]
    task = CreateTask.model_validate(call["args"])
    response = calendar_tools.add_task(task)
    tool_message = ToolMessage(tool_call_id=tool_call_id, content=response)

    return {"messages": state["messages"] + [tool_message]}


workflow = StateGraph(MessagesState)

# Define the three nodes we will cycle between
workflow.add_node("agent", call_model)
workflow.add_node("action", tool_node)
workflow.add_node("talk_to_user", talk_to_user)
workflow.add_node("create_event", create_event)
workflow.add_node("create_task", create_task)

workflow.add_edge(START, "agent")

workflow.add_conditional_edges(
    # First, we define the start node. We use `agent`.
    # This means these are the edges taken after the `agent` node is called.
    "agent",
    # Next, we pass in the function that will determine which node is called next.
    should_continue,
    path_map=["action", "talk_to_user", "create_event", "create_task", "agent", END]
)

workflow.add_edge("action", "agent")
workflow.add_edge("talk_to_user", "agent")
workflow.add_edge("create_event", "agent")
workflow.add_edge("create_task", "agent")



app = workflow.compile()


config = {"configurable": {"thread_id": "1"}}

def start_agent(email):
    for event in app.stream(
        {
            "messages": [
                SystemMessage(content=make_email_prompt(summarize(email))),
                {
                    "role" : "human", 
                    "content": "Help the user with the new message."
                }
            ]
        },
        config,
        stream_mode="values"
    ):
        last = event["messages"][-1]
        if isinstance(last, AIMessage) and not last.tool_calls:
            for i in event["messages"]:
                i.pretty_print()


def start_conversation_agent():
    for event in app.stream(
        {
            "messages": [
                SystemMessage(content=make_conversation_prompt()),
                {
                    "role" : "human", 
                    "content": "Begin the conversation with the user."
                }
            ]
        },
        config,
        stream_mode="values"
    ):
        last = event["messages"][-1]
        if isinstance(last, AIMessage) and not last.tool_calls:
            for i in event["messages"]:
                i.pretty_print()
