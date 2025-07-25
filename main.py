from LLM import _prompt_llm, init_gemini
from gmail_tools import get_creds, init_gmail, query_inbox, SCOPES, start_email_checking

creds = None  # define globally

def init():
    global creds
    init_gemini()
    creds = get_creds("Creds", SCOPES)
    init_gmail(creds) # Initialize Gmail with the credentials

closedate = "2023-10-01"  # Example date, adjust as needed

def _prompt_backlog_emails(date):
    emails = query_inbox(start=date, max_results=25)
    if emails:
        _prompt_llm(emails)
    else:
        print("No emails found for the specified date.")

def _prompt_new_mail(email):
    _prompt_llm([email])  # Process the new email with the LLM


def main():
    init()

    _prompt_backlog_emails(closedate)
    start_email_checking(creds, _prompt_new_mail)
         
    
if __name__ == "__main__":
    main()