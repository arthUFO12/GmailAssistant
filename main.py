import gmail_tools
import example_agent
import google.generativeai as genai
import json
import threading

prompts = []
gotten = threading.Condition()

with open("ArthurCreds/gemini.json") as g:
    api_key = json.load(g)['key']
    genai.configure(api_key=api_key)

def insert_prompts(list_of_emails, prompts):
    with gotten:
        prompts.extend(list_of_emails)
        gotten.notify()

creds = gmail_tools.get_creds("ArthurCreds", gmail_tools.SCOPES)
gmail_tools.start_email_checking(creds, insert_prompts, prompts)

while True:
    while not prompts:
        with gotten:
            gotten.wait()

    example_agent.start_agent(prompts.pop(0))



