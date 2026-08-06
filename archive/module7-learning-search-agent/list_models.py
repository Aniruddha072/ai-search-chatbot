import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("Models supporting generateContent:\n")

for model in client.models.list():
    print(model.name)