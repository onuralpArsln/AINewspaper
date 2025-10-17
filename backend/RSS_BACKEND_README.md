# RSS Backend Server

This is a FastAPI-based RSS backend server that reads articles from `our_articles.db` and serves them as RSS feeds.

## 🚀 Quick Start

```bash
# Start the RSS backend server
./start_rss_backend.sh

# Or manually:
cd backend
source venv/bin/activate
uvicorn rss_backend:app --reload --host 0.0.0.0 --port 8001
```

The server will be available at: **http://localhost:8001**

## 📡 RSS Feed Endpoints

| Endpoint | Description | Example |
|----------|-------------|---------|
| `/rss` | Main RSS feed (latest 20 articles) | http://localhost:8001/rss |
| `/rss/latest` | Latest 10 articles RSS feed | http://localhost:8001/rss/latest |
| `/rss/tag/{tag_name}` | RSS feed filtered by tag | http://localhost:8001/rss/tag/Ekonomi |
| `/rss/search?q={query}` | RSS feed with search results | http://localhost:8001/rss/search?q=ekonomi |

## 🔧 API Endpoints

| Endpoint | Description | Example |
|----------|-------------|---------|
| `/` | Server status and information | http://localhost:8001/ |
| `/api/articles` | Get articles as JSON | http://localhost:8001/api/articles?limit=10 |
| `/api/statistics` | Database statistics | http://localhost:8001/api/statistics |
| `/article/{id}` | Individual article page | http://localhost:8001/article/1 |

## 📋 RSS Feed Features

- **Standard RSS 2.0 format** with proper XML structure
- **Media content support** - includes images as media:content elements
- **Category tags** - articles are categorized by their tags
- **Proper date formatting** - RFC 2822 format for pubDate
- **Self-referencing links** - atom:link for feed discovery
- **Turkish language support** - language set to "tr-TR"

## 🗄️ Database Integration

The RSS backend reads from the `our_articles.db` database with the following schema:

```sql
CREATE TABLE our_articles (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    body TEXT NOT NULL,
    tags TEXT,                    -- Categories + locations
    images TEXT,                  -- JSON array of image URLs
    date DATETIME,
    source_group_id INTEGER,
    source_article_ids TEXT,
    created_at DATETIME,
    updated_at DATETIME
);
```

## 🔄 RSS Feed Structure

Each RSS item includes:
- **Title** - Article title
- **Description** - Article summary/description
- **Link** - Link to individual article page
- **GUID** - Unique identifier for the article
- **PubDate** - Publication date in RFC 2822 format
- **Categories** - Tags from the article
- **Media Content** - Images as media:content elements (up to 3 images per article)

## 🛠️ Configuration

The server runs on **port 8001** by default to avoid conflicts with the main backend server (port 8000).

To change the port, modify the startup command:
```bash
uvicorn rss_backend:app --reload --host 0.0.0.0 --port 8002
```

## 📱 RSS Reader Compatibility

The RSS feeds are compatible with:
- **RSS readers** (Feedly, Inoreader, etc.)
- **Podcast apps** (if you add audio content)
- **News aggregators**
- **Browser RSS extensions**

## 🔍 Testing RSS Feeds

You can test the RSS feeds using:

1. **Browser**: Open http://localhost:8001/rss in your browser
2. **RSS Reader**: Add http://localhost:8001/rss to your RSS reader
3. **Command line**: `curl http://localhost:8001/rss`
4. **RSS Validator**: Use online RSS validators to check feed validity

## 🚨 Troubleshooting

- **Port conflicts**: Make sure port 8001 is not in use
- **Database issues**: Ensure `our_articles.db` exists and has data
- **Import errors**: Make sure all dependencies are installed in the virtual environment
- **CORS issues**: The server allows all origins for development

## 📊 Statistics

The server provides statistics about the database:
- Total articles count
- Articles with/without images
- Oldest and newest article dates

Access at: http://localhost:8001/api/statistics
