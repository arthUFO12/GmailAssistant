
# Gmail Assistant instructions

To start run the assistant...
1. Clone the repo from github. Make sure you are on the 'accessible-branch' using `git status` in the terminal . If not use `git switch accessible-branch`
2. Email 'arth.ufongene@gmail.com' the gmail account for the inbox you would like to use. Might take a while to respond and give you access to the app.
3. You will receive an invite to the google cloud project. Accept it, and use this linkg to take you to the project: https://console.cloud.google.com/apis/dashboard?hl=en&inv=1&invt=Ab5IYA&project=starry-diode-464720-n0
4. Navigate to APIs and Services using the navigation menu (Three lines top left) and then to credentials which will be on the sidebar.
5. At the top of the screen, there will be an option to create your Gemini API key and Oauth Client ID named 'Create Credentials'.
  - Create your Oath Client ID and ensure the application type is set to Desktop App.
  - Download the json at the bottom of the popup 
  - Put this file into the directory `json_dir` under the name `credentials.json`
  - Use the popup to create your Gemini API key
  - Put this API key into `json_dir/config.json` as a value next to the key `gemini_key`

## The next steps will be ran through your computer terminal. These instructions assume you are using a Linux/MacOs computer. They should all be ran from the root of the repository.
6. Create a virtual environment using in your `python -m venv myenv` and activate it using `source myenv/bin/activate`
7. Run `pip install -r requirements.txt`
8. Run `python main.py`
9. You will have to sign into the correct google account and probably enable your IDE to monitor input.

## What the assistant does right now
As of now, the assistant can only monitor incoming emails and make changes in the user's calendar. The agent is proactive, meaning it will notify you of new emails and ask you what action you would like to take. It can check your availability, schedule tasks or event, reschedule, or delete them.

On start, your assistant will give you a summary of emails you received since it last ran.
To open a conversation left click your mouse.
As you receive emails while the program is running, the assistant will notify you.
Right click to close the program.