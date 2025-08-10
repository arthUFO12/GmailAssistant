import gmail_tools
import agent
import google.generativeai as genai
import json
import threading

prompts = []
gotten = threading.Condition()

def insert_prompts(list_of_emails, prompts):
    with gotten:
        prompts.extend(list_of_emails)
        gotten.notify()

agent.start_conversation_agent()
