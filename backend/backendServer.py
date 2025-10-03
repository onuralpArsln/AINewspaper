from fastapi import FastAPI
import feedparser

# uvicorn main:app --reload

app = FastAPI()

RSS_URL = "https://www.gazeteabc.com/rss_arahaberi_178.xml"

# storage arrays
incoming = []
apiMemory = []

def fetch_incoming():
    """Fetch RSS and update the incoming list."""
    global incoming
    feed = feedparser.parse(RSS_URL)
    temp = []
    for entry in feed.entries:
        temp.append({
            "title": entry.get("title"),
            "link": entry.get("link"),
            "published": entry.get("published"),
            "summary": entry.get("summary"),
            "content": entry.get("content")[0]["value"] if "content" in entry else None,
            "image": entry["media_content"][0]["url"] if "media_content" in entry else None,
            "thumbnail": entry["media_thumbnail"][0]["url"] if "media_thumbnail" in entry else None,
            "served": 0   # new field
        })
    incoming = temp

def newsSelector():
    """Compare incoming with apiMemory, add only new news (at the front)."""
    global apiMemory, incoming
    # Collect all links we already have
    known_links = {n["link"] for n in apiMemory}
    new_items = [item for item in incoming if item["link"] not in known_links]

    # newest first
    for item in reversed(new_items):  # reverse so that newest ends up at 0
        apiMemory.insert(0, item)


@app.on_event("startup")
def startup_event():
    print("bu startup kodu")



@app.get("/getOneNew")
def get_one_new():
    """Return the oldest unserved news, mark it as served."""
    global apiMemory
    for i in range(len(apiMemory) - 1, -1, -1):  # check from oldest to newest
        if apiMemory[i]["served"] == 0:
            apiMemory[i]["served"] = 1
            return {"news": apiMemory[i]}
    
    # if no unserved left → return dummy "endofline"
    return {
        "news": {
            "title": "endofline",
            "link": "endofline",
            "published": "endofline",
            "summary": "endofline",
            "content": "endofline",
            "image": "endofline",
            "thumbnail": "endofline",
            "served": 1
        }
    }