import gmail_tools
import email_search
import utils

from googleapiclient.discovery import build, Resource

gmail = build('gmail', 'v1', credentials=utils.creds)
emails, ids = gmail_tools.query_inbox('2025/08/05', '2025/08/16')

str_emails = [str(email) for email in emails]

email_search.add_embeddings(str_emails, ids)
ids = email_search.query_index("New connections made",4)

for id in ids:
    print(str(gmail_tools._retrieve_email_from_id(gmail, id).text) + "\n\n")
