from fastapi import FastAPI
import requests
from dotenv import load_dotenv
import os

load_dotenv()
app = FastAPI()

app_id = os.getenv("app_id")
app_key = os.getenv("app_key")
print(app_id, app_key)

def api_tester(query: str) :
    url = f"https://api.edamam.com/search?q={query}&app_id={app_id}&app_key={app_key}"

    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return {"Error": "Request failed with status code {}".format(response.status_code)}

@app.get("/recipes")
async def get_recipes(query: str):
    return api_tester(query)