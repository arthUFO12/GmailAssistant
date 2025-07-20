from dotenv import load_dotenv
import os
import google.generativeai as genai

load_dotenv()  # load from .env file

api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

model = genai.GenerativeModel("gemini-1.5-pro")
response = model.generate_content("WHY IS THE SKY BLUE")
print(response.text)