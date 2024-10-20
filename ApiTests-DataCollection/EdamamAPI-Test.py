from fastapi import FastAPI
import requests

app = FastAPI()

app_id = "0e3eddce"
app_key = "f763e8664b4279d4f3598dff84190c29"

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