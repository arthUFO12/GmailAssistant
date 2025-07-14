import os
import json

from datetime import date
from pydantic import BaseModel
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


os.environ['GOOGLE_API_KEY'] = json.load(open('ArthurCreds/gemini.json'))['key']

@tool
def get_user_availability(day: int, month: int, year: int):
    """Call this to get the user's availability on a certain date"""
    return f"On {day}/{month}/{year} the user has a soccer game from 4-6pm."

@tool
def schedule_event(event_description: str, day: int, month: int, year: int, hour: int):
    """Call this to schedule an event for the user. The hour ranges from 0-23."""
    return f"Scheduled an event for \"{event_description}\" on {day}/{month}/{year} at {hour}:00 military time."

class GiveUserInfo(BaseModel):
    """Send the user useful information. Purpose is to send the user information or to be sent or confirm a task was completed.
    The information should not contain questions."""
    info: str

class PromptUser(BaseModel):
    """Prompt the user with a question. Purpose is to ask the user for pertinent information and tasks for the assistant to perform.
Ensure you only ask the user to perform actions that are in your tools."""
    prompt: str


tools = [get_user_availability, schedule_event]
tool_node = ToolNode(tools)

model = ChatGoogleGenerativeAI(model='gemini-1.5-pro')
model = model.bind_tools(tools + [PromptUser, GiveUserInfo])

def talk_to_user(state):
    last_message = state["messages"][-1]
    
    tool_responses = []
    if (call := check_for_tool(last_message, "GiveUserInfo")):
        tool_responses.append(give_user_info(call))

    if (call := check_for_tool(last_message, "PromptUser")):
        tool_responses.append(prompt_user(call))

    return {"messages": state["messages"] + tool_responses}
        
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

def prompt_user(call: dict) -> ToolMessage:
    tool_call_id = call["id"]
    ask = PromptUser.model_validate(call["args"])
    # highlight-next-line
    response = input(ask.prompt + '\n')
    resp = f'The user replied \"{response}\"'
    tool_message = ToolMessage(tool_call_id=tool_call_id, content=resp)

    return tool_message



workflow = StateGraph(MessagesState)

# Define the three nodes we will cycle between
workflow.add_node("agent", call_model)
workflow.add_node("action", tool_node)
workflow.add_node("talk_to_user", talk_to_user)

workflow.add_edge(START, "agent")

workflow.add_conditional_edges(
    # First, we define the start node. We use `agent`.
    # This means these are the edges taken after the `agent` node is called.
    "agent",
    # Next, we pass in the function that will determine which node is called next.
    should_continue,
    path_map=["action", "talk_to_user", END]
)

workflow.add_edge("action", "agent")
workflow.add_edge("talk_to_user", "agent")

memory = MemorySaver()

app = workflow.compile(checkpointer=memory)
with open("output.png", "wb") as f:
    f.write(Image(app.get_graph().draw_mermaid_png()).data)

config = {"configurable": {"thread_id": "1"}}



for event in app.stream(
    {
        "messages": [
            {"role" : "system", "content":"You are a helpful AI assistant helping manage a user's inbox. " \
             "The human prompting you is the chief manager of the inbox and not the user. " },
            {"role" : "human", "content": """The user's inbox just received an email from their co-worker asking to get lunch around 1pm on 28/7/2025.  
Using your tools, either let the user know this information and, if appropriate, ask them if they'd like you to use any of the tools that could be useful in this context. 
Complete their request and stop if there is no logical next step"""}
        ]
    },
    config,
    stream_mode="values",
):
    last = event["messages"][-1]
    if isinstance(last, AIMessage) and not last.tool_calls:
        for i in event["messages"]:
            i.pretty_print()
