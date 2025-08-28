

import semantics
import classification
from data_schemas import Email

agent_relevant_categories = set(['needs_action', 'to_schedule'])

agent_relevant_emails = []

def process_emails(emails: list[Email]):
    semantics.add_embeddings(emails)
    classifications = classification.classify(emails)
    for i in range(len(emails)):
        if classifications[i] in agent_relevant_categories:
            agent_relevant_emails.append(emails[i])

        

    

