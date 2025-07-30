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
from langgraph.types import Command, interrupt
from langgraph.checkpoint.memory import MemorySaver
from IPython.display import Image, display



from data_schemas import CreateEvent, CreateTask, Email
import calendar_tools

os.environ['GOOGLE_API_KEY'] = json.load(open('ArthurCreds/gemini.json'))['key']


def make_system_prompt(inject: str):
    return f"""You are a helpful AI assistant responsible for managing a user's Gmail inbox and Google Calendar.\n
                Your goal is to help the user efficiently respond to emails and manage events by using ONLY the tools provided to you. 
                You MUST call tools instead of making assumptions, especially when the information you need is available via a tool. 
                If a new email arrives that could involve checking calendar availability, scheduling a meeting, or replying to the sender, 
                ALWAYS use the appropriate tool before speaking to the user.\n
                All tool outputs are direct responses from official Google Services APIs. Dates will be given in DD/MM/YYYY format. The user's time zone is \"America/New_York\".\n
                Task:
                - {inject}
                - Let the user know about the information contained in the email.
                - Ask the user whether they’d like you to use any of the relevant tools available to you.
                Scheduling Options:
                - You can schedule one of two calendar items:
                  1. An event. Used for obligations that have a definitive start or end time, e.g. a meeting, trip, or doctor's appointment.
                  2. A task. Used for obligations that have a time they must be performed by or due time, e.g. getting groceries, sending an email response, or completing a homework assignment.
                Goal: Schedule the appropriate calendar item unless the user tells you not to.
                Rules:
                - Give the user dates in \"(month name) (day)\" format.
                - Ask the user questions and perform actions until conflicts between events and tasks are resolved.
                - Ensure you ask the user answers whether they want to schedule the event.
                - Only perform tasks the user or system explicitly tells you to.
                - You MUST check user availability before scheduling events AND tasks. If there are conflicts, ask the user what you should do.
                - You may ONLY use PromptUser, GiveUserInfo, and ConfirmRequestCompletion to speak to the user.
                - You may ONLY use `PromptUser`, `GiveUserInfo`, and `ConfirmRequestCompletion` in one response, all other tools must be called in different responses.
                - After ConfirmRequestCompletion is called, send a `STOP` response."""

system_prompt = None

@tool
@validate_call
def search_user_availability(
        start: datetime = Field(..., description="Start of date of the search range in ISO 8601 format."), 
        end: datetime = Field(..., description="End of date of the search range in ISO 8601 format.")
    ):
    """Call this to check the user's availability between a certain range of times.\n Event object important fields:\n 1. summary - name of the event.\n 2. start - start time and timezone of the event.\n 3. end - end time and timezone of the event."""
    return calendar_tools.get_events_in_range(start,end) + calendar_tools.get_tasks_in_range(start,end)

@tool
@validate_call
def change_event_time(
        event_id: str = Field(..., description="ID of the event provided by the Google."),
        start: datetime = Field(..., description="The new start time of the event in ISO 8601 format."),
        end: datetime = Field(..., description="The new end time of the event in ISO 8601 format.")
    ):
    """Call this to change the time of an event you have the Google Services API provided ID for. If you don't have it, first search for the event using search_user_availability and obtain the ID from the tool."""
    return calendar_tools.reschedule_event(event_id, start, end)

@tool
@validate_call
def cancel_event(
        event_id: str = Field(..., description="ID of the event provided by Google.")
    ):
    """Call this tool to delete an event you have the Google Services API provided ID for. If you don't have it, first search for the event using search_user_availability and obtain the ID from the tool."""
    return calendar_tools.remove_event(event_id)

@tool
@validate_call
def change_task_time(
        task_id: str = Field(..., decription="ID of the task provided by Google."),
        due: datetime = Field(..., description="The new due time of the event in ISO 8601 format.")
    ):
    """Call this to change the time of a task you have the Google Services API provided ID for. If you don't have it, first search for the task using search_user_availability and obtain the ID from the tool."""
    return calendar_tools.reschedule_task(task_id, due)

@tool
@validate_call
def cancel_task(
        task_id: str = Field(..., description="ID of the task provided by Google.")
    ):
    """Call this tool to delete a task you have the Google Services API provided ID for. If you don't have it, first search for the task using search_user_availability and obtain the ID from the tool."""
    return calendar_tools.remove_task(task_id)

class ConfirmRequestCompletion(BaseModel):
    """Send the user a message indicating their request was completed. Purpose is to confirm a user requested task was completed. DO NOT ask follow-up questions. After using this tool, stop."""
    message: str
class GiveUserInfo(BaseModel):
    """Send the user useful information. The information should not contain questions. If you want to give the user a follow-up question, it is common to first call GiveUserInfo and then PromptUser in succession."""
    info: str

class PromptUser(BaseModel):
    """Prompt the user with a question. Purpose is to ask the user for pertinent information and tasks for the assistant to perform.
Ensure you only ask the user to perform actions that are in your tools."""
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

def summarize(email): 
    global system_prompt
    prompt = f"""You are an email inbox summarizer. Your task is to supply the inbox manager with summaries of the most important details in incoming emails so they can extract the most pertinent information.
Incoming email:
{email}
Summarize this email in 1 to 2 sentences. Include important information such as dates of tasks and events and descriptions of those tasks and events. Write all dates in DD/MM/YYYY format.
Format the response as if you are speaking to the inbox manager. Start with, "The user's inbox received an email..."
"""
    response = summarizer.invoke(prompt)
    system_prompt = make_system_prompt(response.content)

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

    i = -1
    while isinstance(messages[i], ToolMessage):
        i -= 1
    messages.insert(i + 1, SystemMessage(content=system_prompt))
    
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
    summarize(email)
    for event in app.stream(
        {
            "messages": [
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

