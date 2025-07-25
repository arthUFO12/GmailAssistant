from LLM import _prompt_llm, init_gemini
from gmail_tools import get_creds, init_gmail, query_inbox, SCOPES, start_email_checking
import json
from datetime import datetime
import atexit

creds = None  # define globally

def init():
    global creds
    init_gemini()
    creds = get_creds("Creds", SCOPES)
    init_gmail(creds) # Initialize Gmail with the credentials

def save_last_run_time(path="last_run.json"):
    now = datetime.utcnow()
    with open(path, "w") as f:
        json.dump({"last_run": now.isoformat()}, f)
    print(f"[Saved] App closed at UTC: {now.isoformat()}")
    
def load_last_run_time(path="last_run.json") -> datetime:
    try:
        with open(path, "r") as f:
            data = json.load(f)
            dt = datetime.fromisoformat(data["last_run"])
            print(f"[Loaded] App last closed at UTC: {dt.isoformat()}")
            return dt
    except (FileNotFoundError, KeyError, ValueError) as e:
        print(f"[Info] No previous run time found. Defaulting to now.")
        return datetime.utcnow()

def _prompt_backlog_emails(date):
    emails = query_inbox(start=date, end=datetime.utcnow(), max_results=100)
    if emails:
        _prompt_llm(emails)
    else:
        print("No emails found for the specified date.")

def _prompt_new_mail(email):
    _prompt_llm(email)  # Process the new email with the LLM


def main():
    init()

    _prompt_backlog_emails(load_last_run_time())
    start_email_checking(creds, _prompt_new_mail)
    
    atexit.register(save_last_run_time)
         
    
if __name__ == "__main__":
    main()