from dotenv import load_dotenv
import os
import google.generativeai as genai
from gmail_tools import add_email_label, clear_all_labels

def init_gemini():

    load_dotenv()  # load from .env file

    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)



model = genai.GenerativeModel("gemini-1.5-pro")


def _prompt_llm(emails):
    
    for i, email in enumerate(emails, start=1):

        prompt = f"""Classify the following email by two levels: Urgency level and content category

    From: {email.sender}
    To: {', '.join(email.recipients)}
    Date: {email.date}
    Subject: {email.subject}

    Text:
    {email.text}

    Respond in exactly two lines:
    - Line 1: Only one of the following urgency labels — needs_reply, follow_up_required, or no_action_required.
    - Line 2: Up to three of the following categories, separated by commas — work, personal, newsletters, financial, travel, health, orders, events, notifications, spam_or_junk.
    Do not include any other text or explanation.


    """
    # Clear all labels before applying new ones
    for i, email in enumerate(emails, start=1):
        clear_all_labels(email) 
        try:
            response = model.generate_content(prompt)
            print(f"Email #{i} {email.subject} classification: {response.text.strip()}")

            # Split the AI response into two lines
            email_labels = response.text.strip().splitlines()
            if len(email_labels) >= 2:
                urgency_label = email_labels[0].strip()
                category_labels = [label.strip() for label in email_labels[1].split(",") if label.strip()]

                # Apply both urgency and category labels
                add_email_label(email, urgency_label)
                for label in category_labels:
                    add_email_label(email, label)
            else:
                print(f"Email #{i} returned an unexpected response format:\n{response.text.strip()}")

        except Exception as e:
            print(f"Error with email #{i}: {e}")

