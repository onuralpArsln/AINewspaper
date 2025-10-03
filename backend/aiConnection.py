import os
from dotenv import load_dotenv
from google import genai # install google-genai

# Load variables from .env into the environment
load_dotenv()

# Get your API key
api_key = os.getenv("GEMINI_FREE_API")


client = genai.Client(api_key=api_key)


if __name__=="__main__":
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Explain how AI works in a few words",
    )

    print(response.text)