import gmail_tools
import example_agent
import google.generativeai as genai
import json
import threading


prompts = []
notifier = threading.Condition()

with open("ArthurCreds/gemini.json") as g:
    api_key = json.load(g)['key']
    genai.configure(api_key=api_key)

def insert_prompts(list_of_emails, prompts):
    with notifier:
        prompts.extend(list_of_emails)
        notifier.notify()

def prompt_chat() -> bool:

    while True:
        response = input("Open new chat? ")
        if response == 'y':
            return True
        elif response == 'n':
            return False
        else:
            print("Answer with a 'y' or 'n'. ")



creds = gmail_tools.get_creds("ArthurCreds", gmail_tools.SCOPES)
gmail_tools.start_email_checking(creds, insert_prompts, prompts)

print("Welcome to the Gmail Assistant app.")

while True:
    if prompt_chat():
        example_agent.start_conversation_agent()
    
    with notifier:
        notifier.wait()
        example_agent.start_agent(prompts.pop(0))



