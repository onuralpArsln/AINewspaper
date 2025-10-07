# AI Newspaper

An intelligent news aggregation platform that collects RSS feeds from 30+ Turkish news sources, groups similar articles, and uses AI to rewrite them into professional unified news pieces. Built with FastAPI backend and Express.js + EJS frontend.

## 🏗️ Project Structure

```
AINewspaper/
├── backend/                    # Python backend processing pipeline
│   ├── rss2db.py              # RSS feed collector → rss_articles.db
│   ├── article_similarity.py  # Article grouping engine
│   ├── group_articles.py      # CLI for article grouping
│   ├── ai_writer.py           # AI article rewriter → our_articles.db
│   ├── backendServer.py       # FastAPI API server
│   ├── db_query.py            # Database query utilities
│   ├── writer_prompt.txt      # AI writing instructions
│   └── rsslist.txt            # 30+ Turkish RSS feed URLs
│
└── frontend/                  # Express.js frontend
    ├── server.js              # Express server
    ├── views/                 # EJS templates
    │   ├── index.ejs         # Main news grid page
    │   ├── news.ejs          # Individual article page
    │   └── error.ejs         # Error page
    └── public/               # Static assets (CSS, images)
```

## 📋 Features

### Backend Processing Pipeline
- 📡 **Multi-Source RSS Collection** - Fetches from 30+ Turkish news sources
- 🔄 **Duplicate Prevention** - Content hashing to avoid duplicate articles
- 🤝 **Smart Article Grouping** - Uses Jaccard & Cosine similarity to group articles about the same event
- 🧠 **AI-Powered Rewriting** - Google Gemini AI rewrites and unifies articles
- 🏷️ **Automatic Tagging** - Generates categories (sports, politics, etc.) and locations
- 🖼️ **Image Collection** - Extracts images from multiple sources (image_url, image_urls, media_content)
- 📊 **Source Tracking** - Maintains references to original articles

### Frontend Display
- 🎨 **Modern UI** - Beautiful, responsive design with gradient themes
- 📰 **News Grid Layout** - Card-based news display
- 📖 **Full Article View** - Detailed news pages with images
- 🖼️ **Image Support** - Displays thumbnails and full images
- 🔗 **Source Links** - Links to original articles

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Node.js 16+
- Google Gemini API key ([Get one here](https://ai.google.dev/))

### Quick Setup

1. **Install Backend Dependencies:**
```bash
cd backend
pip install -r requirements.txt
```

2. **Configure Environment Variables:**

Create `backend/.env`:
```env
GEMINI_FREE_API=your_gemini_api_key_here
```

Create `frontend/.env`:
```env
PORT=3000
BACKEND_URL=http://localhost:8000
```

3. **Install Frontend Dependencies:**
```bash
cd frontend
npm install
```

### Complete News Processing Pipeline

```bash
# Step 1: Collect RSS articles (30+ Turkish news sources)
cd backend
python rss2db.py

# Step 2: Group similar articles using similarity detection
python group_articles.py --threshold 0.3 --max-time-diff 2

# Step 3: AI rewrite articles (configure in ai_writer.py)
# Edit ai_writer.py: Set ONLY_IMAGES = True/False, ARTICLE_COUNT = 10
python ai_writer.py

# Step 4: Start web servers
cd ..
powershell -ExecutionPolicy Bypass -File start.ps1
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

## 🔧 Running the Full Application

### Option 1: Quick Start Scripts (Recommended)

**Windows - Batch File (start.bat):**
```cmd
start.bat
```
- Starts both servers in minimized windows
- **Closing the main window stops ALL servers automatically**
- Press any key in the window to stop servers and exit

**Windows - PowerShell (start.ps1):**
```powershell
powershell -ExecutionPolicy Bypass -File start.ps1
```
- Better process management
- **Closing the window or Ctrl+C stops ALL servers automatically**
- Recommended for better cleanup

**Linux/Mac (start.sh):**
```bash
chmod +x start.sh
./start.sh
```
- Starts both servers
- **Ctrl+C stops ALL servers automatically**

### Option 2: Separate Terminals (Manual)

**Terminal 1 - Backend:**
```bash
cd backend
uvicorn backendServer:app --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

## 📊 How It Works

### Processing Pipeline

```
RSS Feeds → Collection → Grouping → AI Rewriting → Display
    ↓          ↓           ↓            ↓            ↓
rsslist.txt  rss2db.py  group_     ai_writer.py  Frontend
                        articles                  (Express)
                          .py
    ↓                      ↓            ↓
rss_articles.db ←─── Similarity ──→ our_articles.db
```

### 1. RSS Collection (`rss2db.py`)
- Reads 30+ RSS feed URLs from `rsslist.txt`
- Fetches articles using `feedparser`
- Extracts: title, content, images, author, date, etc.
- **Duplicate prevention** using content hashing
- Stores in `rss_articles.db` with `is_read = 0`

### 2. Article Grouping (`group_articles.py`)
- Finds articles about the **same event** from different sources
- Uses **Jaccard & Cosine similarity** (title + content)
- Groups articles with `event_group_id`
- Only groups different sources within 2 days
- Example: 7 articles about "Türk Devletleri Zirvesi" → Group 18

### 3. AI Rewriting (`ai_writer.py`)

**Configuration** (edit in file):
```python
ONLY_IMAGES = False  # True = only process articles with images
ARTICLE_COUNT = 10   # Number of articles per run
```

**Process:**
1. Iterates unread articles (newest first)
2. If article has `event_group_id` → reads ALL group articles
3. Sends to **Google Gemini AI** with `writer_prompt.txt` rules
4. AI generates: Title, Description, Body, Tags (categories + locations)
5. Collects ALL images from 3 columns: `image_url`, `image_urls`, `media_content`
6. Saves to `our_articles.db` with source IDs
7. Marks source articles `is_read = 1`

**Usage:**
```bash
python ai_writer.py                    # Process ARTICLE_COUNT articles
python ai_writer.py --max-articles 20  # Process 20 articles
python ai_writer.py --stats            # Show statistics only
```

### 4. Frontend Display
- Express.js serves news from backend API
- Responsive grid layout with cards
- Individual article pages with full content
- Images and source links

## 📝 Database Schemas

### `rss_articles.db` (Source Articles)
```sql
articles:
  - id, title, description, content, summary
  - link, published, author, source_name
  - image_url, image_urls, media_content  (3 image columns)
  - event_group_id  (NULL or group number)
  - is_read  (0 = unread, 1 = processed)
```

### `our_articles.db` (AI-Generated Articles)
```sql
our_articles:
  - id, title, description, body
  - tags  (e.g., "sports, Istanbul, football")
  - images  (JSON array of all image URLs)
  - date  (publication date from source)
  - source_group_id  (reference to event group)
  - source_article_ids  (e.g., "567,568,569")
```

## 🎨 Customization

### AI Writer Configuration

Edit `backend/ai_writer.py`:
```python
ONLY_IMAGES = False  # True to only process articles with images
ARTICLE_COUNT = 10   # Number of articles to process per run
```

### RSS Feed Sources

Add/remove feeds in `backend/rsslist.txt`:
```
https://www.ntv.com.tr/gundem.rss
https://www.aa.com.tr/tr/rss/default?cat=guncel
# Add your feeds here (one per line)
```

### Article Grouping Parameters

```bash
python group_articles.py \
  --threshold 0.3 \      # Similarity threshold (0.0-1.0)
  --days 7 \             # Days back to process
  --max-time-diff 2      # Max days between articles in same group
```

### AI Writing Prompt

Customize `backend/writer_prompt.txt` to change:
- Writing tone and style
- Article structure requirements
- Language and terminology
- Tag generation rules

## 🐛 Troubleshooting

### No Articles Processed
```bash
# Check statistics
python ai_writer.py --stats

# If ONLY_IMAGES = True, ensure articles have images
# Check database: SELECT COUNT(*) FROM articles WHERE is_read = 0 AND image_url IS NOT NULL;
```

### AI Generation Fails
- Verify Gemini API key in `.env`
- Check `writer_prompt.txt` exists
- Review logs for API errors
- Try with fewer articles: `python ai_writer.py --max-articles 5`

### No Groups Created
```bash
# Lower similarity threshold
python group_articles.py --threshold 0.2

# Check grouping status
python group_articles.py --status
```

### Database Issues
```bash
# View recent articles
python db_query.py

# Check unread count
sqlite3 backend/rss_articles.db "SELECT COUNT(*) FROM articles WHERE is_read = 0"

# View generated articles
sqlite3 backend/our_articles.db "SELECT id, title FROM our_articles LIMIT 10"
```

## 📦 Key Technologies

### Backend (Python)
- **RSS Processing**: `feedparser`, `requests`
- **Similarity Detection**: Jaccard & Cosine algorithms with Turkish stop words
- **AI Integration**: Google Gemini (`google-genai`)
- **Database**: SQLite3 with content hashing
- **API Server**: FastAPI + Uvicorn

### Frontend (Node.js)
- **Server**: Express.js
- **Templates**: EJS
- **HTTP Client**: Axios
- **Auto-reload**: Nodemon (dev)

## 🔧 Command Reference

### RSS Collection
```bash
python rss2db.py                    # Collect from all feeds in rsslist.txt
```

### Article Grouping
```bash
python group_articles.py            # Group with default settings
python group_articles.py --status   # Show grouping statistics
python group_articles.py --show-groups 10  # View top 10 groups
python group_articles.py --search "ekonomi"  # Search groups
python group_articles.py --reset    # Reset all grouping
```

### AI Writing
```bash
python ai_writer.py                 # Use ARTICLE_COUNT from config
python ai_writer.py --max-articles 20  # Process 20 articles
python ai_writer.py --stats         # Show statistics only
```

### Database Queries
```bash
python db_query.py                  # Interactive database query
```

### Start Servers
```bash
# Windows PowerShell (recommended)
powershell -ExecutionPolicy Bypass -File start.ps1

# Windows Batch
start.bat

# Linux/Mac
./start.sh
```

## 📚 Additional Documentation

- **`backend/AI_WRITER_GUIDE.md`** - Comprehensive AI writer usage guide
- **`backend/AI_WRITER_CHANGES.md`** - Detailed changelog for AI writer
- **`backend/README.md`** - Backend system architecture and pipeline details

## 🎯 Example Workflow

```bash
# 1. Collect news (run daily)
cd backend
python rss2db.py
# Result: ~100 new articles in rss_articles.db

# 2. Group similar articles (run after collection)
python group_articles.py --threshold 0.3 --max-time-diff 2
# Result: Similar articles grouped by event_group_id

# 3. Configure AI writer (edit once)
# Set ONLY_IMAGES = True, ARTICLE_COUNT = 20

# 4. Generate AI articles (run as needed)
python ai_writer.py
# Result: Professional articles in our_articles.db with:
#   - Categories & location tags
#   - All images from sources
#   - Source article references

# 5. Start web interface
cd ..
powershell -ExecutionPolicy Bypass -File start.ps1
# Visit: http://localhost:3000
```

## 🔑 Key Features Explained

### Smart Grouping
- Groups articles from **different sources** about the same event
- Example: 7 articles from NTV, TRT, Cumhuriyet about "Summit" → 1 group
- Uses temporal proximity (max 2 days apart)
- AI combines all perspectives into one comprehensive article

### Image Collection
Collects from **3 database columns**:
1. `image_url` - Primary image
2. `image_urls` - JSON array of images
3. `media_content` - Media metadata with URLs

All unique images transferred to AI-generated article.

### Category & Location Tags
AI automatically generates:
- **Categories**: sports, politics, economy, science, technology, health, etc.
- **Locations**: Istanbul, Turkey, Ankara, etc.
- **Keywords**: Relevant terms from article

Example: `"sports, Istanbul, football, Galatasaray, championship"`

## 📄 License

This project is open source and available under the MIT License.

---

**Built with ❤️ for intelligent news aggregation 📰**

