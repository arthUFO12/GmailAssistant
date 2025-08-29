from enum import Enum
import os
import json

from datetime import date, datetime
from pydantic import BaseModel, Field, validate_call
from typing import Annotated, List, TypedDict
from data_schemas import CreateEvent, CreateTask

import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import ChatMessage, ToolMessage, SystemMessage, HumanMessage, AIMessage, BaseMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.types import Command, interrupt

from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import InMemorySaver

from data_schemas import CreateEvent, CreateTask, Email
import calendar_tools
import gmail_tools
import utils

os.environ["GOOGLE_API_KEY"] = utils.get_json_field('config.json', 'gemini_key')

SYSTEM_PROMPT = f"""You are a helpful AI agent responsible for managing a user's Gmail inbox.
An AI chatbot is talking to the user and will relay requests to you in order to help the user. 

Your goal:
- Fulfill the chatbot's requests using ONLY the tools registered in your system.
- Think step by step about what the user wants.
- Include reasoning in your response.
- ALWAYS call a registered tool to perform actions or respond.
- If the request is vague, ask the chatbot for clarification using the AskQuestion tool.
- Use keyword search when looking for specific words or names in emails.
- You must have a tool call in EVERY response.

INFO:
- Today's date: {calendar_tools.today}

Behavior example:
1. Think through the steps you need to complete the request.
2. Determine which tool is needed.
3. Call the tool with the appropriate arguments.
4. Include reasoning/thoughts if helpful
5. Use the `Respond` tool to reply to the request."""


REQUEST_STATUS = Enum("REQUEST_STATUS", { "FAILURE": "failure", "SUCCESS": "success" })


@tool
@validate_call
def add_label_to_email(
        email_id: str = Field(..., description="The id of the email to add the label to."), 
        label_name:str = Field(..., description="The label name.")
    ):
    """Used to add a label to an email"""
    return gmail_tools.add_email_label(email_id, label_name)


@tool
@validate_call
def remove_label_from_email(
        email_id: str = Field(..., description="The id of the email to remove the label from."), 
        label_name:str = Field(..., description="The label name.")
    ):
    """Used to remove a label form an email"""
    return gmail_tools.remove_email_label(email_id, label_name)


@tool
@validate_call
def keyword_query_inbox(
        keywords: str = Field(..., description="A string containing the space-separated keywords for your query. Should NOT contain email addresses."), 
        subject: str = Field(None, description="A string containing the subject query."), 
        start: date = Field(None, description="A start date for your query"), 
        end: date = Field(None, description="An end date for your query") 
    ):
    """Used to query the user's inbox using keywords. Use when specific words, such as people, places, and things should be contained in the email."""
    return gmail_tools.keyword_query_inbox(keywords, subject, start, end, None)

@tool
@validate_call
def semantically_query_inbox(
        query: str = Field(..., description="A string with your semantic query."), 
        start: date = Field(None, description="A start date for your query"), 
        end: date = Field(None, description="An end date for your query")
    ):
    """Used to query the user's inbox using semantics. Use when the general meaning of the query is more important than specific words in it."""
    return gmail_tools.semantically_query_inbox(query,start,end)

class AskQuestion(BaseModel):
    """Used to ask the chatbot for more information or clarification about the request."""
    question: str

class Respond(BaseModel):
    """Used to respond back to the chatbot with requested information and indicate task completion."""
    
    request_status: REQUEST_STATUS = Field(..., description="Whether the task was successfully fulfilled or ended in failure.")
    summary: str = Field(..., description="A SHORT summary of what you did during the task.")
    information: str = Field(None, description="The information the chatbot requested in detail. Only use if the chatbot requested information and the task ended in success.")
    error_info: str = Field(None, description="A summary of the issues that arose during the task if it ended in failure.")

tools = [add_label_to_email, remove_label_from_email, keyword_query_inbox, semantically_query_inbox]
tool_node = ToolNode(tools)

summarizer = ChatGoogleGenerativeAI(model='gemini-1.5-pro')

g_agent = summarizer.bind_tools(tools + [AskQuestion, Respond])


def ask_question(state):
    call = state['messages'][-1].tool_calls[0]
    tool_call_id = call["id"]
    q = AskQuestion.model_validate(call["args"])
    
    
    tool_message = ToolMessage(tool_call_id=tool_call_id, content=interrupt(q.question))
  
    return {"messages": state["messages"] + [tool_message]}

def respond(state):
    call = state['messages'][-1].tool_calls[0]
    tool_call_id = call["id"]
    r = Respond.model_validate(call["args"])

    tool_message = ToolMessage(tool_call_id=tool_call_id, content=json.dumps(r.model_dump(mode='json')))

    return {"messages": state["messages"] + [tool_message]}



def route(state):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls[0]['name'] == "AskQuestion":
        return "ask_question"
    elif last_message.tool_calls[0]['name'] == "Respond":
        return "respond"
    else:
        return "action"
    
def call_agent(state):
    messages = state["messages"]

    print(messages[-1].content)
    response = g_agent.invoke(messages)
    print(response.content)
    print(response.tool_calls[0]['name'])
    
    return {"messages": messages + [response]}


workflow = StateGraph(MessagesState)


workflow.add_node("agent", call_agent)
workflow.add_node("action", tool_node)
workflow.add_node("respond", respond)
workflow.add_node("ask_question", ask_question)
workflow.add_edge(START, "agent")

workflow.add_conditional_edges(
    # First, we define the start node. We use `agent`.
    # This means these are the edges taken after the `agent` node is called.
    "agent",
    # Next, we pass in the function that will determine which node is called next.
    route,
    path_map=["action", "respond", "ask_question"]
)

workflow.add_edge("action", "agent")
workflow.add_edge("respond", END)
workflow.add_edge("ask_question", "agent")


memory = InMemorySaver()

app = workflow.compile(checkpointer=memory)


config = {"configurable": {"thread_id": "1"}}

def start_workflow(request: str = None, answer: str = None):

    if answer:
        events = list(app.stream(
            Command(resume=answer),
            config=config,
            stream_mode="values"
        ))
    else:
        events = list(app.stream(
            {
                "messages": [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=request)
                ]
            },
            config,
            stream_mode="values"
        ))


    if len(app.get_state(config).next) > 0 and app.get_state(config).next[0] == 'ask_question':
        return (events[-1]['messages'][-1].tool_calls[0]['args']['question'],True)
    else:
        memory.storage.clear()
        for i in events[-1]['messages']:
            i.pretty_print()
        return (events[-1]['messages'][-1].content, False)
    

inp = None

while True:
    res = start_workflow("""{
    "task": "Are there any emails about meetings or gatherings? Search semantically. Give a summary of their content."
}""", answer=inp)
    if res[1]:
        inp = input(res[0])
        continue
    else:
        break