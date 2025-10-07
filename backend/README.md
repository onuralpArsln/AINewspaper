# Backend - AI Newspaper RSS System

This backend system automatically collects news from multiple RSS feeds, stores them in a SQLite database, and groups similar articles from different sources to provide intelligent news aggregation.

## Scripts Overview

### Core RSS Processing
- **`rsstester.py`** - RSS feed reader and parser that fetches and parses articles from RSS feeds, handles different RSS formats (RSS, Atom, RDF), and provides article validation and error handling.
- **`rss2db.py`** - Main RSS-to-database processor that reads RSS feed URLs from `rsslist.txt`, fetches articles using `rsstester.py`, and stores them in the database with duplicate prevention using content hashing.
- **`db_query.py`** - Database query interface that provides functions to search articles, get statistics, retrieve articles by source, date range, or keywords, and includes new grouping functionality for similar articles.

### Article Grouping & Similarity
- **`article_similarity.py`** - Advanced similarity detection engine that uses Jaccard and Cosine similarity algorithms to identify articles about the same events from different sources, with Turkish language support and configurable similarity thresholds.
- **`group_articles.py`** - Command-line interface for article grouping that orchestrates the similarity detection process, provides flexible parameters (similarity threshold, time range, minimum group size), and offers search and statistics capabilities.

## Database Structure

### Articles Table
```sql
CREATE TABLE articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,                    -- Article title
    description TEXT,                       -- Article description/summary
    content TEXT,                           -- Full article content
    summary TEXT,                           -- Article summary
    link TEXT UNIQUE,                       -- Original article URL
    guid TEXT UNIQUE,                       -- RSS GUID
    comments TEXT,                          -- Comments URL
    published DATETIME,                     -- Publication date
    updated DATETIME,                       -- Last update date
    author TEXT,                            -- Article author
    category TEXT,                          -- Article category
    tags TEXT,                              -- JSON array of tags
    enclosures TEXT,                        -- JSON array of enclosures
    media_content TEXT,                     -- JSON array of media
    image_url TEXT,                         -- Featured image URL
    source_name TEXT,                       -- News source name
    source_url TEXT,                        -- News source URL
    feed_url TEXT,                          -- RSS feed URL
    language TEXT,                          -- Article language
    rights TEXT,                            -- Copyright info
    content_hash TEXT UNIQUE,               -- Hash for duplicate detection
    event_group_id INTEGER,                 -- Groups similar articles
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Feed Statistics Table
```sql
CREATE TABLE feed_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_url TEXT UNIQUE,                   -- RSS feed URL
    last_processed DATETIME,                -- Last processing time
    total_articles INTEGER DEFAULT 0,      -- Total articles from this feed
    last_article_count INTEGER DEFAULT 0,  -- Articles in last run
    processing_duration REAL,               -- Processing time in seconds
    status TEXT DEFAULT 'success',          -- Processing status
    error_message TEXT,                     -- Error details if failed
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Current Pipeline

### 1. RSS Collection Pipeline
```
rsslist.txt → rsstester.py → rss2db.py → rss_articles.db
```
- **Input**: RSS feed URLs stored in `rsslist.txt` (one URL per line)
- **Processing**: `rsstester.py` fetches and parses RSS feeds, `rss2db.py` processes all feeds and stores articles
- **Output**: Articles stored in `rss_articles.db` with duplicate prevention
- **Usage**: `python rss2db.py`

### 2. Article Grouping Pipeline
```
rss_articles.db → article_similarity.py → group_articles.py → Updated DB with event_group_id
```
- **Input**: Articles from database (recent articles without group assignments)
- **Processing**: `article_similarity.py` detects similar articles, `group_articles.py` creates event groups
- **Output**: Articles updated with `event_group_id` for grouping similar articles
- **Usage**: `python group_articles.py --threshold 0.3 --days 7`

### 3. Query & Analysis Pipeline
```
rss_articles.db → db_query.py → Statistics, Search Results, Grouped Articles
```
- **Input**: Database queries for articles, groups, or statistics
- **Processing**: `db_query.py` provides various query functions
- **Output**: Search results, statistics, grouped articles, or raw data
- **Usage**: `python db_query.py` or import functions in other scripts

## Quick Start

### Collect News Articles
```bash
# Process all RSS feeds and store in database
python rss2db.py
```

### Group Similar Articles
```bash
# Group similar articles with default settings
python group_articles.py

# Check current status
python group_articles.py --status

# View sample groups
python group_articles.py --show-groups 10

# Custom parameters
python group_articles.py --threshold 0.4 --days 14 --min-group-size 3 --max-time-diff 1

# Search for specific groups
python group_articles.py --search "ekonomi"

# Reset all grouping (start over)
python group_articles.py --reset
```

### Query Database
```bash
# Interactive database query
python db_query.py
```

## Article Grouping System

### How Similarity Detection Works
The system uses advanced text similarity algorithms to:
- Detect articles about the same event from different sources
- Group similar articles together with a unique event group ID
- Provide comprehensive statistics and search capabilities
- Allow for configurable similarity thresholds and grouping parameters

### Key Features
- **Title Similarity**: Uses Jaccard and Cosine similarity on article titles
- **Content Similarity**: Analyzes article descriptions and content
- **Turkish Language Support**: Includes Turkish stop words for better accuracy
- **Multi-source Grouping**: Only groups articles from different sources

### Understanding the `event_group_id` Column
- **`NULL`** or **`0`** = Article is NOT grouped (stands alone)
- **Same number** = Articles are about the same event (grouped together)

**Example**: All articles with `event_group_id = 18` are about the same event (e.g., "Türk Devletleri Teşkilatı 12. Zirvesi")

### Configuration Parameters

#### Similarity Threshold (`--threshold`)
- **Range**: 0.0 to 1.0
- **Default**: 0.3
- **Description**: Minimum similarity score required to group articles
- **Recommendation**: 
  - 0.2-0.3: More aggressive grouping (more groups, larger groups)
  - 0.4-0.5: Balanced approach
  - 0.6+: Conservative grouping (fewer, smaller groups)

#### Days Back (`--days`)
- **Default**: 7
- **Description**: Number of days back to process for grouping
- **Recommendation**: 
  - 3-7 days: Recent news focus
  - 14-30 days: Broader coverage
  - 90+ days: Historical analysis

#### Minimum Group Size (`--min-group-size`)
- **Default**: 2
- **Description**: Minimum number of articles required to form a group
- **Recommendation**: 
  - 2: Include all similar pairs
  - 3+: Focus on major events with multiple sources

#### Maximum Time Difference (`--max-time-diff`)
- **Default**: 2
- **Description**: Maximum time difference in days between article publications for grouping
- **Purpose**: Prevents grouping old articles with new updates about the same topic
- **Recommendation**: 
  - 1 day: Very strict temporal grouping
  - 2 days: Balanced approach (default)
  - 3-7 days: More flexible temporal grouping

### Programmatic Usage
```python
from article_similarity import ArticleSimilarityDetector
from db_query import RSSDatabaseQuery

# Initialize components
detector = ArticleSimilarityDetector('rss_articles.db')
db_query = RSSDatabaseQuery('rss_articles.db')

# Run grouping
stats = detector.group_similar_articles(
    similarity_threshold=0.3,
    days_back=7,
    min_group_size=2,
    max_time_diff_days=2
)

# Get grouping statistics
grouping_stats = db_query.get_grouping_statistics()
print(f"Total groups: {grouping_stats['total_groups']}")
print(f"Grouped articles: {grouping_stats['grouped_articles']}")

# Get all event groups
groups = db_query.get_all_event_groups(10)
for group in groups:
    print(f"Group {group['event_group_id']}: {group['article_count']} articles")
```

### Database Queries for Grouped Articles

```sql
-- Find all articles in a specific group
SELECT title, source_name FROM articles WHERE event_group_id = 18;

-- Find articles that are NOT grouped
SELECT title, source_name FROM articles WHERE event_group_id IS NULL;

-- See all groups and their sizes
SELECT event_group_id, COUNT(*) as article_count 
FROM articles 
WHERE event_group_id IS NOT NULL 
GROUP BY event_group_id 
ORDER BY article_count DESC;

-- Find groups with specific keywords
SELECT event_group_id, title, source_name 
FROM articles 
WHERE event_group_id IS NOT NULL 
AND title LIKE '%ekonomi%';
```

## Configuration Files

- **`rsslist.txt`** - List of RSS feed URLs (one per line)
- **`requirements.txt`** - Python dependencies
- **`rss_articles.db`** - SQLite database with articles and statistics
- **`rsslog.txt`** - Processing logs and error messages

## Key Features

- **Multi-source RSS Processing**: Handles RSS, Atom, and RDF formats
- **Duplicate Prevention**: Uses content hashing to avoid duplicate articles
- **Similarity Detection**: Groups articles about the same events from different sources
- **Turkish Language Support**: Optimized for Turkish news with stop words
- **Comprehensive Statistics**: Detailed processing and grouping statistics
- **Flexible Querying**: Search by keywords, date range, source, or groups
- **Error Handling**: Robust error handling with detailed logging
- **Performance Optimized**: Indexed database with efficient queries

## Performance Considerations

### Processing Time
- **1000 articles**: ~30 seconds
- **Scaling**: O(n²) complexity for similarity comparison
- **Optimization**: Process recent articles only for better performance

### Memory Usage
- **Moderate**: Loads articles in batches
- **Recommendation**: Process in smaller chunks for very large datasets

### Database Performance
- **Indexes**: Added for event_group_id queries
- **Queries**: Optimized for grouped article retrieval

## Troubleshooting

### Common Issues

1. **No Groups Created**
   - Check similarity threshold (try lowering it)
   - Ensure articles are from different sources
   - Verify minimum group size setting

2. **Too Many Small Groups**
   - Increase similarity threshold
   - Increase minimum group size
   - Check for duplicate articles

3. **Performance Issues**
   - Reduce days_back parameter
   - Process in smaller batches
   - Check database indexes

### Debugging
```bash
# Verbose output
python group_articles.py --verbose

# Database inspection
sqlite3 rss_articles.db "SELECT event_group_id, COUNT(*) FROM articles GROUP BY event_group_id;"
```

## Integration with Existing System

### RSS2DB Integration
The grouping system works seamlessly with the existing RSS to database pipeline:

1. **Run RSS Collection**: `python rss2db.py` (collects new articles)
2. **Run Grouping**: `python group_articles.py` (groups similar articles)
3. **Query Results**: Use updated `db_query.py` functions

### Backend Integration
The system can be integrated with the backend server:

```python
# In backendServer.py
from db_query import RSSDatabaseQuery

def get_news_with_groups():
    db = RSSDatabaseQuery()
    groups = db.get_all_event_groups(20)
    return groups
```

## Current Database Statistics

The database contains articles from 22 different news sources with intelligent grouping capabilities to identify when multiple sources cover the same events, making the news aggregation system more intelligent and organized.

### Example Output
```
Articles processed: 1,000
Groups created: 82
Articles grouped: 212
Processing time: 30.21 seconds
Average group size: 2.6 articles
```

### Sample Event Groups
```
Group 18 (7 articles):
  1. "Türk Devletleri Teşkilatı 12. Zirvesi" başladı! Cumhurbaşkanı Erdoğan...
     Source: İnternethaber
  2. Türk Devletleri Teşkilatı 12. Zirvesi başladı...
     Source: Sputnik Haberler
  3. Türk Devletleri Teşkilatı 12. Zirvesi başladı...
     Source: TRT Haber
  ... and 4 more articles
```