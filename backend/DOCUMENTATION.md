# AI Newspaper Backend - Complete Documentation

## 🚀 Quick Start

```bash
# 1. Collect RSS articles
python rss2db.py

# 2. Group similar articles
python group_articles.py --threshold 0.3

# 3. Generate AI articles
python ai_writer.py --max-articles 10

# 4. Query database
python db_query.py
```

## 📋 Core Scripts

### RSS Processing
- **`rss2db.py`** - Fetches RSS feeds, stores articles with duplicate prevention
- **`rsstester.py`** - RSS parser supporting RSS, Atom, and RDF formats
- **`db_query.py`** - Database query interface with statistics

### Article Grouping
- **`article_similarity.py`** - Similarity detection using Jaccard/Cosine algorithms
- **`group_articles.py`** - Groups similar articles from different sources

### AI Generation
- **`ai_writer.py`** - Generates professional articles using Gemini AI
- **`writer_prompt.txt`** - AI prompt template

## 🗄️ Database Schema

```sql
CREATE TABLE articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    content TEXT,
    link TEXT UNIQUE,
    guid TEXT UNIQUE,
    published DATETIME,
    author TEXT,
    category TEXT,
    tags TEXT,                              -- JSON array
    image_urls TEXT,                        -- JSON array of ALL images
    source_name TEXT,
    feed_url TEXT,
    content_hash TEXT UNIQUE,               -- Duplicate detection
    event_group_id INTEGER,                 -- Groups similar articles
    is_read BOOLEAN DEFAULT FALSE,          -- Processing status
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 🔄 Processing Pipeline

```
RSS Feeds → rss2db.py → rss_articles.db → group_articles.py → ai_writer.py → our_articles.db
```

### Workflow
1. **Collect**: `python rss2db.py` - Fetch articles from RSS feeds
2. **Group**: `python group_articles.py` - Group similar articles by event
3. **Generate**: `python ai_writer.py` - Create professional articles
4. **Query**: `python db_query.py` - Analyze and search

## 🖼️ Image Handling

All images stored in unified `image_urls` JSON array column:

```python
from rss2db import RSSDatabase
import json

db = RSSDatabase()
articles = db.get_recent_articles(10)

for article in articles:
    images = json.loads(article['image_urls']) if article.get('image_urls') else []
    print(f"{article['title']}: {len(images)} images")
```

**Extraction Sources:**
- RSS media tags (`media:content`, `media:thumbnail`)
- HTML content (`<img>`, `data-src`, `srcset`, CSS backgrounds)
- Enclosures with image MIME types
- Lazy-loaded and responsive images

## 📊 Article Grouping

### Group Similar Articles
```bash
# Default grouping
python group_articles.py

# Custom parameters
python group_articles.py --threshold 0.3 --days 7 --max-time-diff 2

# View groups
python group_articles.py --show-groups 10

# Search groups
python group_articles.py --search "ekonomi"
```

### Parameters
- **`--threshold`** (0.0-1.0): Similarity threshold (default: 0.3)
- **`--days`**: Days back to process (default: 7)
- **`--max-time-diff`**: Max time between articles in days (default: 2)
- **`--min-group-size`**: Minimum articles per group (default: 2)

### Programmatic Usage
```python
from article_similarity import ArticleSimilarityDetector

detector = ArticleSimilarityDetector('rss_articles.db')
stats = detector.group_similar_articles(
    similarity_threshold=0.3,
    days_back=7,
    max_time_diff_days=2
)
```

## ✅ Read Status Tracking

Track processed articles with `is_read` column:

```python
from rss2db import RSSDatabase

db = RSSDatabase()

# Get unread articles
unread = db.get_unread_articles(limit=10)

# Process and mark as read
for article in unread:
    process_article(article)
    db.mark_article_as_read(article['id'])

# Batch mark as read
db.mark_articles_as_read([123, 124, 125])

# Get counts
print(f"Unread: {db.get_unread_count()}")
print(f"Read: {db.get_read_count()}")
```

### Available Functions

**RSSDatabase:**
- `get_unread_articles(limit, offset)` - Get unread articles
- `get_read_articles(limit, offset)` - Get read articles
- `get_unread_count()` - Count unread
- `get_read_count()` - Count read
- `mark_article_as_read(id)` - Mark single as read
- `mark_articles_as_read(ids)` - Batch mark as read
- `get_unread_articles_by_source(source, limit)` - Filter by source

**RSSDatabaseQuery:**
Same functions available in query interface.

## 🤖 AI Article Generation

```bash
# Generate articles
python ai_writer.py --max-articles 10

# View statistics
python ai_writer.py --stats
```

**Features:**
- Processes unread articles from `rss_articles.db`
- Groups similar articles into unified content
- Generates professional format (title, description, body, tags)
- Saves to `our_articles.db`
- Marks source articles as read

**Configuration:**
Edit `ai_writer.py`:
- `ONLY_IMAGES = False` - Process only articles with images
- `ARTICLE_COUNT = 10` - Articles per run

## 📈 Database Queries

### Python
```python
from db_query import RSSDatabaseQuery

db = RSSDatabaseQuery()

# Get statistics
print(f"Total: {db.get_total_articles()}")
print(f"Unread: {db.get_unread_count()}")

# Get grouped articles
groups = db.get_all_event_groups(10)

# Search
results = db.search_articles("ekonomi", limit=20)

# Get by source
articles = db.get_articles_by_source_detail("BBC News", 10)
```

### SQL
```sql
-- Get articles by event group
SELECT title, source_name FROM articles WHERE event_group_id = 18;

-- Get ungrouped articles
SELECT title FROM articles WHERE event_group_id IS NULL;

-- Get unread articles
SELECT title FROM articles WHERE is_read = 0;

-- Group statistics
SELECT event_group_id, COUNT(*) as count 
FROM articles 
WHERE event_group_id IS NOT NULL 
GROUP BY event_group_id 
ORDER BY count DESC;
```

## 📝 Configuration Files

- **`rsslist.txt`** - RSS feed URLs (one per line)
- **`writer_prompt.txt`** - AI generation prompt template
- **`requirements.txt`** - Python dependencies

## 🔧 Key Features

✅ Multi-source RSS processing (RSS, Atom, RDF)  
✅ Duplicate prevention via content hashing  
✅ Comprehensive image extraction (1,775+ images)  
✅ Similarity detection with Turkish support  
✅ Event grouping across sources  
✅ Read status tracking  
✅ AI-powered article generation  
✅ Advanced querying and statistics  
✅ Performance-optimized with indexes  

## 🐛 Troubleshooting

**No groups created:**
- Lower similarity threshold (try 0.2-0.3)
- Check articles are from different sources
- Verify minimum group size

**Performance issues:**
- Reduce `--days` parameter
- Process in smaller batches
- Check database indexes

**Images not found:**
- Verify articles have HTML content
- Check image URLs are valid HTTP/HTTPS
- Review extraction patterns

## 📊 Statistics

The system provides comprehensive statistics:
- Total articles and by source
- Image statistics (count, average, max)
- Read/unread counts and percentages
- Grouping coverage and average size
- Feed processing status

Run `python db_query.py` to view full statistics.

