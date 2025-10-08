# AI Newspaper Backend - Documentation

## 🚀 Quick Start

```bash
# 1. Collect RSS articles
venv/bin/python rss2db.py

# 2. Group similar articles (optional but recommended)
venv/bin/python group_articles.py --threshold 0.3

# 3. Generate 10 output articles with AI (images sorted by resolution)
venv/bin/python ai_writer.py --max-articles 10

# 4. Start backend server (serves our articles)
venv/bin/python -m uvicorn backendServer:app --reload

# 5. Query database (optional)
venv/bin/python db_query.py
```

**Note:** Always use `venv/bin/python` (Python 3.11 virtual environment)

## 📋 Core Scripts

| Script | Purpose |
|--------|---------|
| **`rss2db.py`** | Fetches RSS feeds, extracts images, prevents duplicates |
| **`rsstester.py`** | RSS parser (RSS, Atom, RDF formats) |
| **`group_articles.py`** | Groups similar articles from different sources |
| **`ai_writer.py`** | Generates OUTPUT articles using Gemini AI |
| **`db_query.py`** | Database queries and statistics |
| **`backendServer.py`** | FastAPI server that serves articles from our_articles.db |

## 🗄️ Database Schema

### `rss_articles.db` - Source Articles Table

```sql
CREATE TABLE articles (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    content TEXT,
    summary TEXT,
    link TEXT UNIQUE,
    guid TEXT UNIQUE,
    published DATETIME,
    author TEXT,
    category TEXT,
    tags TEXT,                    -- JSON array
    enclosures TEXT,              -- JSON array (image attachments)
    media_content TEXT,           -- JSON array (media info)
    image_urls TEXT,              -- JSON array (ALL images consolidated)
    source_name TEXT,
    feed_url TEXT,
    content_hash TEXT UNIQUE,     -- Duplicate detection
    event_group_id INTEGER,       -- NULL or group ID
    is_read BOOLEAN DEFAULT 0,    -- Processing status
    created_at DATETIME,
    updated_at DATETIME
);
```

### `our_articles.db` - Generated Articles Table

```sql
CREATE TABLE our_articles (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    body TEXT NOT NULL,
    tags TEXT,                    -- Categories + locations
    images TEXT,                  -- JSON array of image URLs
    date DATETIME,
    source_group_id INTEGER,      -- Reference to event_group_id
    source_article_ids TEXT,      -- Comma-separated IDs
    created_at DATETIME,
    updated_at DATETIME
);
```

## 🔄 Complete Workflow

### Step 1: Collect RSS Articles
```bash
venv/bin/python rss2db.py
```
**What happens:**
- Fetches articles from `rsslist.txt`
- Extracts images from 3 sources
- Prevents duplicates (content hash)
- Marks all as `is_read = 0`

### Step 2: Group Similar Articles (Optional)
```bash
venv/bin/python group_articles.py --threshold 0.3
```
**What happens:**
- Finds similar articles from different sources
- Assigns same `event_group_id` to related articles
- Example: 12 articles about same event → group #5

### Step 3: Generate OUTPUT Articles
```bash
venv/bin/python ai_writer.py --max-articles 10
```
**What happens:**
1. Gets unread articles (newest first, with images if `ONLY_IMAGES=True`)
2. For each output article:
   - If grouped (12 articles) → merges ALL → **1 output**
   - If not grouped → **1 output**
3. Collects images from all source articles
4. **Sorts images by resolution** (highest first)
5. **Filters out tiny images** (<200×200 pixels)
6. Saves to `our_articles.db`
7. Marks source articles as `is_read = 1`
8. Continues until **10 output articles** generated

**Result:** 10 high-quality articles with sorted images in `our_articles.db`

**Note:** `--max-articles 10` = **10 output articles**, not input count!

### Step 4: Query Results
```bash
venv/bin/python db_query.py          # View statistics
venv/bin/python ai_writer.py --stats # AI writer statistics
```

## 🖼️ Image Handling & Sorting

Images are extracted, sorted by resolution, and filtered:

### Collection (3 sources)
1. **`image_urls`** - Primary consolidated array
2. **`enclosures`** - Image attachments (`image/*`)
3. **`media_content`** - RSS media tags

### Automatic Sorting (NEW!)
When `ai_writer.py` saves articles:
- ✅ Downloads each image to check resolution
- ✅ Filters out tiny images (<200×200 pixels by default)
- ✅ Sorts by quality (highest resolution first)
- ✅ Saves sorted URLs to `our_articles.db`

**Result:** `images[0]` is always the best quality image!

### Configuration
Edit `ai_writer.py` line ~472:
```python
# Default: 200×200 minimum (40,000 pixels)
all_images = self._sort_images_by_resolution(all_images, min_resolution=40000)

# Stricter: 500×500 minimum
all_images = self._sort_images_by_resolution(all_images, min_resolution=250000)

# Lenient: 100×100 minimum
all_images = self._sort_images_by_resolution(all_images, min_resolution=10000)
```

## 📊 Article Grouping

### Basic Usage
```bash
# Group articles
venv/bin/python group_articles.py

# View groups
venv/bin/python group_articles.py --show-groups 10

# Search groups
venv/bin/python group_articles.py --search "ekonomi"
```

### Parameters
- `--threshold 0.3` - Similarity threshold (0.0-1.0, lower = more groups)
- `--days 7` - Process articles from last N days
- `--max-time-diff 2` - Max days between grouped articles

## 🤖 AI Article Generation

### Configuration (in `ai_writer.py`)
```python
ONLY_IMAGES = True   # Only process articles with images
ARTICLE_COUNT = 10   # Number of OUTPUT articles to generate
```

### Usage Examples
```bash
# Generate 10 output articles (uses config)
venv/bin/python ai_writer.py

# Generate 20 output articles (override)
venv/bin/python ai_writer.py --max-articles 20

# Only show statistics
venv/bin/python ai_writer.py --stats
```

### Features
- ✅ Processes unread articles (newest first)
- ✅ Merges grouped articles into one output
- ✅ Extracts images from all sources
- ✅ **Sorts images by resolution** (highest first)
- ✅ **Filters tiny images** (<200×200 pixels)
- ✅ Generates: Title, Description, Body, Tags
- ✅ Tags include: category + location + keywords
- ✅ Marks source articles as read
- ✅ Tracks processed groups (no duplicates)

## 📈 Database Queries

### Python API
```python
from db_query import RSSDatabaseQuery

db = RSSDatabaseQuery()

# Statistics
print(f"Total: {db.get_total_articles()}")
print(f"Unread: {db.get_unread_count()}")

# Get grouped articles
groups = db.get_all_event_groups(limit=10)

# Search
results = db.search_articles("ekonomi", limit=20)
```

### SQL Queries
```sql
-- Get articles in a group
SELECT title, source_name 
FROM articles 
WHERE event_group_id = 5;

-- Get unread articles
SELECT * FROM articles 
WHERE is_read = 0 
ORDER BY created_at DESC;

-- Group statistics
SELECT event_group_id, COUNT(*) as count
FROM articles 
WHERE event_group_id IS NOT NULL
GROUP BY event_group_id
ORDER BY count DESC;
```

## 🔧 Configuration & Setup

### Environment Setup
```bash
# Python 3.11 virtual environment required
cd /home/onuralp/project/AINewspaper/backend

# Dependencies (already installed)
venv/bin/pip install -r requirements.txt
```

### Configuration Files
| File | Purpose |
|------|---------|
| `rsslist.txt` | RSS feed URLs (one per line) |
| `writer_prompt.txt` | AI generation instructions |
| `requirements.txt` | Python dependencies (includes `requests`, `Pillow` for images) |
| `.env` | API keys (`GEMINI_FREE_API`) |

## ⚙️ Key Features

✅ Multi-format RSS support (RSS, Atom, RDF)  
✅ Duplicate prevention (content hash)  
✅ Comprehensive image extraction (3 sources)  
✅ **Image sorting by resolution** (highest first)  
✅ **Smart image filtering** (removes tiny images)  
✅ Similarity detection (Jaccard + Cosine)  
✅ Event grouping across sources  
✅ Read status tracking  
✅ AI-powered article generation (Gemini)  
✅ Smart output counting (groups → 1 article)  
✅ Turkish language support  

## 🐛 Troubleshooting

**No groups created:**
- Lower threshold: `--threshold 0.2`
- Check articles are from different sources

**AI writer generates fewer articles:**
- Not enough unread articles with images (`ONLY_IMAGES=True`)
- Check: `venv/bin/python ai_writer.py --stats`

**All images filtered out:**
- Lower minimum resolution in `ai_writer.py` line ~472
- Check source image quality: `SELECT image_urls FROM articles LIMIT 10;`

**Image sorting is slow:**
- Normal! Downloads each image once to check resolution
- Reduce timeout in `_get_image_resolution()` for faster processing

**Import errors (PIL, requests):**
- Reinstall dependencies: `venv/bin/pip install -r requirements.txt`

## 📊 Example Output Counts

**Scenario:** 50 unread articles, `ARTICLE_COUNT = 10`

| Source Articles | Groups | Output Articles |
|----------------|--------|-----------------|
| 12 articles | Group #5 | **1 article** |
| 8 articles | Group #7 | **1 article** |
| 1 article | No group | **1 article** |
| 5 articles | Group #9 | **1 article** |
| ... | ... | ... |
| **50 total** | **Various** | **10 total** ✅ |

All 50 source articles marked as `is_read = 1` after processing.

## 📝 Pipeline Summary

```
rsslist.txt
    ↓
rss2db.py → rss_articles.db (is_read=0, images collected)
    ↓
group_articles.py → assigns event_group_id (groups similar articles)
    ↓
ai_writer.py → collects images → sorts by resolution → filters small images
    ↓
our_articles.db (OUTPUT: 10 articles with sorted images)
    ↓
backendServer.py → serves articles to frontend
```

**Result:** High-quality articles with best images first!

## 🌐 Backend Server (backendServer.py)

### Starting the Server
```bash
# Start with auto-reload (development)
venv/bin/python -m uvicorn backendServer:app --reload

# Start on specific port
venv/bin/python -m uvicorn backendServer:app --port 8000
```

### API Endpoints

#### Core Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Server status and statistics |
| `/getOneNew` | GET | Get next unserved article (for frontend) |
| `/articles` | GET | Get articles with pagination (`?limit=10&offset=0`) |
| `/articles/{id}` | GET | Get specific article by ID |
| `/search` | GET | Search articles (`?q=keyword&limit=20`) |
| `/tags/{tag}` | GET | Get articles by tag |
| `/statistics` | GET | Database statistics |
| `/reset` | POST | Reset served status (allows re-serving articles) |

#### Example Usage
```bash
# Get server status
curl http://localhost:8000/

# Get next article (same as frontend uses)
curl http://localhost:8000/getOneNew

# Get 10 recent articles
curl http://localhost:8000/articles?limit=10

# Search for articles
curl http://localhost:8000/search?q=ekonomi

# Get articles by tag
curl http://localhost:8000/tags/sports

# Reset served status (start serving from beginning)
curl -X POST http://localhost:8000/reset
```

### Features
- ✅ Serves articles from `our_articles.db` (NOT from RSS feeds)
- ✅ Tracks which articles have been served
- ✅ Automatic image JSON parsing
- ✅ Returns "endofline" when all articles served
- ✅ Batch loading for performance (20 articles at a time)
- ✅ CORS enabled for frontend access
- ✅ Full REST API for article management

### Response Format
```json
{
  "news": {
    "id": 2,
    "title": "Article Title",
    "description": "Brief description",
    "body": "Full article content",
    "tags": "category, location, keywords",
    "published": "2025-10-08T14:38:00+03:00",
    "image": "https://example.com/image.jpg",
    "thumbnail": "https://example.com/image.jpg",
    "images": ["https://example.com/image1.jpg", "..."],
    "source_group_id": null,
    "created_at": "2025-10-08 20:57:39"
  }
}
```

### Integration with Frontend
The backend server is designed to work seamlessly with the frontend:
1. Frontend calls `/getOneNew` to get articles one by one
2. Server automatically tracks served articles
3. When all articles are served, returns `{"news": {"title": "endofline", ...}}`
4. Frontend can reset and start over by calling `/reset`
