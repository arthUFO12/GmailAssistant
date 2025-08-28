## Gmail Assistant

### Module Descriptions
1. `data_schemas.py` - BaseModel definitions for events, tasks, etc.
2. `calendar_agent.py` - Contains the workflow and tooling for the agent that manages the user's calendar.
3. `chatbot.py` - Contains the workflow for a chatbot that communicates with the user and gives requests to the two different agents.
4. `classification.py` - Contains logic for classifying emails into the user's labels.
5. `semantics.py` - Contains logic for embedding email meaning and querying those embeddings for the closest match. Supports index saving and loading.
6. `workflow.py` - Will soon contain the entire workflow for handling incoming emails
7. `utils.py` - Miscellaneous functions
8. `agent.py` - deprecated


### Problems to Solve
1. Gmail inboxes don't have categories for emails that might require a reply or action, and sometimes you may forget to reply to an email or perform an action specified in an email.
2. Many Gmail inboxes aren't checked for long periods of times, or receive large volumes of emails in short amounts of times that are difficult to navigate.
3. When receiving an email about an upcoming event, it's sometimes cumbersome to have to switch between Gmail and google calendar to check availability.

### Solution
My solution is to implement a gmail assistant that exists as a popup box in the corner of the screen. Through this interface, the user will be able to query their inbox for information, preparing a brief of unread emails, check availability on a certain day or time, schedule reminders in google calendar for replies or actions, as well as events. The assistant will also be proactive, automatically categorizing emails into different categories based on content and providing useful suggestions to the user based on that categorization.

#### Labeling
1. The assistant will first categorize emails into important and unimportant. Personal emails from other individuals will be prioritized and promotional and social emails will be marked as unimportant by default. The user can also provide input to what emails should be marked as important or unimportant, such as, 'all emails from linkedin are important' or 'all emails pertaining to social media are important'.
2. The assistant will then be given a list of predecided labels for to categorize emails into the labels 'needs reply', 'action required', 'needs scheduling', and 'miscellaneous information'. It will then retroactively apply these labels to existing emails in the inbox. Incoming emails will automatically be categorized into the correct labels. The Assistant will them ask the user what action they might want to take with this email, i.e. 'do you want to schedule a reminder to reply to this email' or 'do you want me to give you your availability on the day of this event?'.

Possible features: 
1. More specific categorizing based off of user input, e.g. 'organize the subscriptions label by company', 'put all emails older than a year in a 'to delete' label'.

#### Summarizing
The assistant will prepare briefs after the inbox between certain dates. The user will also be able to query emails to summarize, e.g. 'summarize my last conversation with joe bradford'.

#### Asking the Inbox
The user will be able to ask information that might be contained in the inbox similar to a google search. The user will be able to ask questions such as 'when is my doctor's appointment'.

#### Calendar and Availability
The assistant will also be connected to the user's google calendar and will be able to check availability. The user will be able to ask for their availability, and if there are possible conflicts the assistant will list them. The assistant will also be able to create and delete events on user request.

### Implementation
#### Tech Stack/ Modules Needed
1. Google API services and authorization - To handle logging into services and retrieving emails and google calendar evemts.
2. Google Gemini LLM - To handle tasks such as creating labels, filters, and summarizing text.
3. LangChain and LangGraph - To handle the thinking aspects of the assistant, i.e. figuring out which functions to call based on user request.
4. Pydantic - For JSON validation of event objects and descriptions of tool arguments.

#### Labeling Implementation Steps
1. Create a gmail tools module that contains functions that can retrieve emails from google APIs and organize them into Email objects.
2. Engineer a prompt to feed to the LLM that will categorize these emails into the labels.
3. Create a function that categorizes already received emails as well as incoming emails

**We will finish this feature and then focus on implementation of the others later**
