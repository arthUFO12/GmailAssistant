import gmail_tools
import agent
import google.generativeai as genai
import json
import threading
import utils
from pynput import mouse

new_emails = []
end = False
notifier = threading.Condition()

def insert_emails(list_of_emails):
    global new_emails
    with notifier:
        new_emails.extend(list_of_emails)
        notifier.notify()

def mouse_listener():

    def on_click(x, y, button, pressed):
        global end
        if pressed:
            if button == mouse.Button.right:
                end = True

            with notifier:
                notifier.notify()

    with mouse.Listener(on_click=on_click) as listener:
        listener.join()

if backlog := gmail_tools.get_backlogged_emails():
    agent.start_backlog_agent(backlog)

gmail_tools.start_email_checking(utils.creds, insert_emails)
threading.Thread(target=mouse_listener, daemon=True).start()

while True:
    with notifier:
        notifier.wait()
        
    if end: break

    if new_emails:
        agent.start_new_email_agent(new_emails.pop(0))
    else:
        agent.start_conversation_agent()
