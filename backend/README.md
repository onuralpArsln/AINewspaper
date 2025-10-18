# AI Newspaper Backend

Unified backend server for AI-generated news articles with RSS feed support.

## 🚀 Quick Start

```bash
cd /home/onuralp/project/AINewspaper/backend
source venv/bin/activate

# 1. Collect RSS articles
python rss2db.py

# 2. Group similar articles (optional)
python group_articles.py --threshold 0.3

# 3. Generate AI articles
python ai_writer.py --max-articles 10

# 4. Start unified server (frontend API + RSS feeds)
python -m uvicorn backendServer:app --reload --port 8000
```

## 📋 Core Scripts

| Script | Purpose |
|--------|---------|
| **`rss2db.py`** | Fetches RSS feeds, extracts images, prevents duplicates |
| **`group_articles.py`** | Groups similar articles from different sources |
| **`ai_writer.py`** | Generates articles using Gemini AI with image sorting |
| **`backendServer.py`** | Unified FastAPI server (frontend API + RSS feeds) |
| **`db_query.py`** | Database queries and statistics |

## 🗄️ Database Schema

### `rss_articles.db` - Source Articles
```sql
CREATE TABLE articles (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    content TEXT,
    link TEXT UNIQUE,
    published DATETIME,
    author TEXT,
    category TEXT,
    tags TEXT,                    -- JSON array
    image_urls TEXT,              -- JSON array (ALL images)
    source_name TEXT,
    content_hash TEXT UNIQUE,     -- Duplicate detection
    event_group_id INTEGER,       -- Group ID for similar articles
    is_read BOOLEAN DEFAULT 0,
    created_at DATETIME
);
```

### `our_articles.db` - Generated Articles
```sql
CREATE TABLE our_articles (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    body TEXT NOT NULL,
    tags TEXT,                    -- Categories + locations
    images TEXT,                  -- JSON array (sorted by resolution)
    date DATETIME,
    source_group_id INTEGER,
    source_article_ids TEXT,
    created_at DATETIME
);
```

## 🔄 Workflow

```
rsslist.txt → rss2db.py → rss_articles.db → group_articles.py → ai_writer.py → our_articles.db → backendServer.py
```

1. **Collect**: `rss2db.py` fetches RSS feeds, extracts images, prevents duplicates
2. **Group**: `group_articles.py` groups similar articles (optional)
3. **Generate**: `ai_writer.py` creates articles with sorted images
4. **Serve**: `backendServer.py` serves both frontend API and RSS feeds

## 🖼️ Image Handling

- **Extraction**: From 3 sources (image_urls, enclosures, media_content)
- **Sorting**: By resolution (highest first)
- **Filtering**: Removes images <200×200 pixels
- **Result**: `images[0]` is always the best quality image

## 🌐 Backend Server API

### Frontend API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Server status and API info |
| `/getOneNew` | GET | Next unserved article (frontend) |
| `/articles` | GET | Paginated articles |
| `/articles/{id}` | GET | Single article by ID |
| `/search` | GET | Search articles |
| `/tags/{tag}` | GET | Articles by tag |
| `/statistics` | GET | Database statistics |
| `/reset` | POST | Reset served status |

### RSS Feed Endpoints
| Endpoint | Description |
|----------|-------------|
| `/rss` | Main RSS feed (20 articles) |
| `/rss/latest` | Latest 10 articles RSS |
| `/rss/category/{category}` | RSS by category |
| `/rss/tag/{tag}` | RSS by tag |
| `/rss/search?q={query}` | RSS search results |

## ⚙️ Configuration

### Environment
```bash
# Python 3.11 virtual environment required
source venv/bin/activate
pip install -r requirements.txt
```

### Key Files
| File | Purpose |
|------|---------|
| `rsslist.txt` | RSS feed URLs |
| `writer_prompt.txt` | AI generation instructions |
| `requirements.txt` | Dependencies |
| `.env` | API keys (GEMINI_FREE_API) |

## 🎯 Features

✅ Multi-format RSS support (RSS, Atom, RDF)  
✅ Duplicate prevention  
✅ Image extraction and sorting  
✅ Article grouping and similarity detection  
✅ AI-powered article generation  
✅ Unified backend server (frontend + RSS)  
✅ Turkish language support  
✅ CORS enabled  

## 🐛 Troubleshooting

**No groups created**: Lower threshold with `--threshold 0.2`  
**Fewer articles generated**: Check unread articles with `python ai_writer.py --stats`  
**Images filtered out**: Lower minimum resolution in `ai_writer.py`  
**Import errors**: Reinstall dependencies with `pip install -r requirements.txt`  

## 📊 Example Usage

```bash
# Get server status
curl http://localhost:8000/

# Get next article (frontend)
curl http://localhost:8000/getOneNew

# Get RSS feed
curl http://localhost:8000/rss

# Search articles
curl http://localhost:8000/search?q=ekonomi

# Reset served status
curl -X POST http://localhost:8000/reset
```

## 📝 Response Format

### Frontend API
```json
{
  "news": {
    "id": 2,
    "title": "Article Title",
    "summary": "Brief description",
    "content": "Full article content",
    "tags": "category, location, keywords",
    "published": "2025-10-08T14:38:00+03:00",
    "image": "https://example.com/image.jpg",
    "images": ["https://example.com/image1.jpg", "..."],
    "link": "https://original-source.com/article"
  }
}
```

### RSS Feed
Standard RSS 2.0 format with media content support, proper date formatting, and Turkish language support.