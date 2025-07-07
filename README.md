## Gmail Assistant

### Problems to Solve
1. Gmail inboxes don't have categories for emails that might require a reply or action.
2. Many Gmail inboxes aren't checked for long periods of times, or receive large volumes of emails in short amounts of times that are difficult to navigate.
3. When receiving an email about an upcoming event, it's sometimes cumbersome to have to switch between Gmail and google calendar to check availability.

### Solution
My solution is to implement a gmail assistant that exists as a popup box in the corner of the screen. Through this interface, the user will be able to ask requests such as categorizing the inbox into the best fitting labels, preparing a brief of unread emails, and checking availability on a certain day or time.

#### Labeling
1. The assistant will first categorize emails into important and unimportant. Personal emails from other individuals will be prioritized and promotional and social emails will be marked as unimportant by default. The user can also provide input to what emails should be marked as important or unimportant, such as, 'all emails from linkedin are important' or 'all emails pertaining to social media are important'.
2. The assistant will then be given a list of predecided labels for to categorize emails into the labels 'needs reply', 'action required', 'needs scheduling', and 'miscellaneous information'. It will then retroactively apply these labels to existing emails in the inbox. Incoming emails will automatically be categorized into the correct labels. 

Possible features: 
1. More specific categorizing based off of user input, e.g. 'organize the subscriptions label by company', 'put all emails older than a year in a 'to delete' label'.

#### Summarizing
The assistant will prepare briefs after the inbox between certain dates. The user will also be able to query emails to summarize, e.g. 'summarize my last conversation with joe bradford'.

#### Asking the Inbox
The user will be able to ask information that might be contained in the inbox similar to a google search. The user will be able to ask questions such as 'when is my doctor's appointment'.

#### Calendar and Availability
The assistant will also be connected to the user's google calendar and will be able to check availability. The user will be able to ask for their availability, and if there are possible conflicts the assistant will list them. The assistant will also be able to create and delete events on user request.

### Implementation
#### Tech Stack
1. Google API services and authorization - To handle logging into services and retrieving emails and google calendar evemts.
2. Google Gemini LLM - To handle tasks such as creating labels, filters, and summarizing text.
3. LangChain - To handle the thinking aspects of the assistant, i.e. figuring out which functions to call based on user request.

#### Labeling Implementation Steps
1. Create a gmail tools module that contains functions that can retrieve emails from google APIs and organize them into Email objects.
2. Engineer a prompt to feed to the LLM that will categorize these emails into the labels.
3. Create a function that categorizes already received emails as well as incoming emails

**We will finish this feature and then focus on implementation of the others later**
