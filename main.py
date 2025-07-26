from LLM import _prompt_llm, init_gemini
import gmail_tools
import json
from datetime import datetime
import atexit
from typing import Union

creds = None  # define globally

def init():
    global creds
    init_gemini()
    creds = gmail_tools.get_creds("Creds", gmail_tools.SCOPES)
    gmail_tools.init_gmail(creds) # Initialize Gmail with the credentials

def save_last_run_time(path="last_run.json"):
    with open(path, "w") as f:
        json.dump({"last_run": gmail_tools.latest_id}, f)
    print(f"[Saved] App closed with history ID: {gmail_tools.latest_id}")
    
def load_last_run_time(path="last_run.json") -> Union[datetime, str]:
    try:
        with open(path, "r") as f:
            data = json.load(f)
            latest_id = data["last_run"]
            print(f"[Loaded] App last closed with history ID: {latest_id}")
            return latest_id
    except (FileNotFoundError, KeyError, ValueError) as e:
        print(f"[Info] No previous run time found. Defaulting to now.")
        return datetime.utcnow()

def _prompt_backlog_emails_from_date(date: Union[datetime, str]):
    if isinstance(date, str):
        gmail_tools.latest_id = date
        return
        
    emails = gmail_tools.query_inbox(start=date, end=datetime.utcnow(), max_results=100)
    if emails:
       _prompt_llm(emails)
    else:
        print("No emails found for the specified date.")



def _prompt_new_mail(email):
    _prompt_llm(email)  # Process the new email with the LLM


def main():
    init()

    _prompt_backlog_emails(load_last_run_time())
    gmail_tools.start_email_checking(creds, _prompt_new_mail)
    
    atexit.register(save_last_run_time)
         
    
if __name__ == "__main__":
    main()