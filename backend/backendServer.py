from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any, Optional, List
from db_query import OurArticlesDatabaseQuery

# uvicorn backendServer:app --reload

# Database query interface
db = OurArticlesDatabaseQuery('our_articles.db')

# Storage for articles and served tracking
articles_cache = []
served_indices = set()
current_offset = 0
BATCH_SIZE = 20  # Load articles in batches

def load_articles_batch():
    """Load a batch of articles from database"""
    global articles_cache, current_offset
    
    new_articles = db.get_recent_articles(limit=BATCH_SIZE, offset=current_offset)
    
    if new_articles:
        # Process articles - parse JSON images field
        for article in new_articles:
            parse_article_images(article)
        
        articles_cache.extend(new_articles)
        current_offset += len(new_articles)
        return len(new_articles)
    
    return 0

def get_next_unserved_article() -> Optional[Dict[str, Any]]:
    """Get the next unserved article from cache"""
    global articles_cache, served_indices
    
    # Try to find an unserved article in current cache
    for i, article in enumerate(articles_cache):
        if i not in served_indices:
            served_indices.add(i)
            return article
    
    # If all cached articles are served, load more
    loaded = load_articles_batch()
    
    if loaded > 0:
        # Try again with newly loaded articles
        for i, article in enumerate(articles_cache):
            if i not in served_indices:
                served_indices.add(i)
                return article
    
    # No more articles available
    return None

def parse_article_images(article: Dict[str, Any]) -> Dict[str, Any]:
    """Parse JSON images field in article"""
    if article.get('images'):
        try:
            article['images'] = json.loads(article['images'])
        except (json.JSONDecodeError, TypeError):
            article['images'] = []
    else:
        article['images'] = []
    return article

def parse_article_data(article: Dict[str, Any]) -> Dict[str, Any]:
    """Parse JSON fields in article (images and tags) - enhanced version for RSS"""
    # Parse images
    if article.get('images'):
        try:
            article['images'] = json.loads(article['images'])
        except (json.JSONDecodeError, TypeError):
            article['images'] = []
    else:
        article['images'] = []
    
    # Parse tags
    if article.get('tags'):
        try:
            article['tags'] = json.loads(article['tags'])
        except (json.JSONDecodeError, TypeError):
            # Fallback: treat as comma-separated string
            if isinstance(article['tags'], str):
                article['tags'] = [tag.strip() for tag in article['tags'].split(',') if tag.strip()]
            else:
                article['tags'] = []
    else:
        article['tags'] = []
    
    return article

def format_date_for_rss(date_str: str) -> str:
    """Format date string for RSS (RFC 2822 format)"""
    if not date_str:
        return datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    try:
        # Try to parse the date string
        if isinstance(date_str, str):
            # Handle different date formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
                except ValueError:
                    continue
        
        # If all parsing fails, return current time
        return datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
    except Exception:
        return datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")

def create_rss_feed(articles: List[Dict[str, Any]], feed_title: str = "AI Newspaper", 
                   feed_description: str = "AI-generated news articles", 
                   feed_url: str = "http://localhost:8000") -> str:
    """Create RSS XML feed from articles"""
    
    # Create RSS root element
    rss = ET.Element("rss")
    rss.set("version", "2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    rss.set("xmlns:media", "http://search.yahoo.com/mrss/")
    
    # Create channel element
    channel = ET.SubElement(rss, "channel")
    
    # Channel metadata
    ET.SubElement(channel, "title").text = feed_title
    ET.SubElement(channel, "description").text = feed_description
    ET.SubElement(channel, "link").text = feed_url
    ET.SubElement(channel, "language").text = "tr-TR"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
    ET.SubElement(channel, "generator").text = "AI Newspaper Backend Server"
    
    # Add atom:link for self-reference
    atom_link = ET.SubElement(channel, "atom:link")
    atom_link.set("href", f"{feed_url}/rss")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")
    
    # Add items for each article
    for article in articles:
        item = ET.SubElement(channel, "item")
        
        # Basic item fields
        ET.SubElement(item, "title").text = article.get('title', 'Untitled')
        ET.SubElement(item, "description").text = article.get('description', '')
        ET.SubElement(item, "link").text = f"{feed_url}/articles/{article['id']}"
        ET.SubElement(item, "guid").text = f"{feed_url}/articles/{article['id']}"
        ET.SubElement(item, "pubDate").text = format_date_for_rss(article.get('date'))
        
        # Add main category
        if article.get('category'):
            ET.SubElement(item, "category").text = article['category']
        
        # Add tags as additional categories
        if article.get('tags') and isinstance(article['tags'], list):
            for tag in article['tags']:
                if tag and tag.strip():
                    ET.SubElement(item, "category").text = tag.strip()
        
        # Add media content (images)
        images = article.get('images', [])
        if images:
            for image_url in images[:3]:  # Limit to first 3 images
                if image_url:
                    media_content = ET.SubElement(item, "media:content")
                    media_content.set("url", image_url)
                    media_content.set("type", "image/jpeg")
                    media_content.set("medium", "image")
    
    # Convert to string
    rough_string = ET.tostring(rss, encoding='unicode')
    
    # Pretty print the XML
    import xml.dom.minidom
    dom = xml.dom.minidom.parseString(rough_string)
    return dom.toprettyxml(indent="  ")

def get_source_article_link(source_article_ids: str) -> Optional[str]:
    """
    Retrieve the original article link from RSS database using source article IDs.
    Returns the link from the first source article, or None if not available.
    """
    if not source_article_ids:
        return None
    
    try:
        # Get the first source article ID
        first_id = source_article_ids.split(',')[0].strip()
        
        # Query RSS database for the original link
        conn = sqlite3.connect('rss_articles.db')
        cursor = conn.cursor()
        cursor.execute('SELECT link FROM articles WHERE id = ?', (first_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    except Exception as e:
        print(f"Error retrieving source link: {e}")
        return None

def format_article_for_frontend(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format article data for frontend consumption.
    Maps database fields to frontend-expected field names:
    - description → summary (for article cards and summary section)
    - body → content (for full article content)
    - Adds link field from source articles
    """
    # Get first image if available
    images = article.get('images', [])
    image = images[0] if images else None
    thumbnail = images[0] if images else None  # Use same as image, or could use a smaller version
    
    # Get original source link from RSS database
    link = get_source_article_link(article.get('source_article_ids'))
    
    return {
        "id": article['id'],
        "title": article['title'],
        "summary": article.get('description', ''),      # Frontend expects 'summary'
        "content": article['body'],                      # Frontend expects 'content'
        "tags": article.get('tags', ''),
        "published": article.get('date', ''),
        "image": image,
        "thumbnail": thumbnail,
        "link": link if link else "#",                  # Original source link
        "images": images,  # All images
        "source_group_id": article.get('source_group_id'),
        "created_at": article.get('created_at', '')
    }

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for FastAPI application.
    Handles startup and shutdown events using modern async context manager.
    """
    # Startup: Load initial batch of articles
    print("Starting backend server...")
    print("Loading articles from our_articles.db...")
    
    loaded = load_articles_batch()
    print(f"Loaded {loaded} articles on startup")
    
    # Print statistics
    stats = db.get_statistics()
    print(f"Total articles in database: {stats['total_articles']}")
    print(f"Articles with images: {stats['articles_with_images']}")
    
    yield  # Server is running
    
    # Shutdown: Cleanup code goes here (if needed)
    print("Shutting down backend server...")

# Initialize FastAPI app with lifespan handler
app = FastAPI(lifespan=lifespan)

# Add CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    """Root endpoint with both frontend API and RSS feed information"""
    stats = db.get_statistics()
    return {
        "message": "AI Newspaper Backend Server",
        "status": "running",
        "database": "our_articles.db",
        "statistics": stats,
        "frontend_api": {
            "get_one_new": "/getOneNew",
            "articles": "/articles",
            "articles_by_id": "/articles/{id}",
            "search": "/search?q={query}",
            "articles_by_tag": "/tags/{tag}",
            "statistics": "/statistics",
            "reset": "/reset (POST)"
        },
        "rss_feeds": {
            "main_feed": "/rss",
            "latest_10": "/rss/latest",
            "by_category": "/rss/category/{category_name}",
            "by_tag": "/rss/tag/{tag_name}",
            "search": "/rss/search?q={query}"
        },
        "categories": ["gündem", "ekonomi", "spor", "siyaset", "magazin", "yaşam", "eğitim", "sağlık", "astroloji"]
    }

@app.get("/getOneNew")
def get_one_new():
    """Return the next unserved article, mark it as served"""
    article = get_next_unserved_article()
    
    if article:
        formatted_article = format_article_for_frontend(article)
        return {"news": formatted_article}
    
    # No more articles - return end of line marker
    return {
        "news": {
            "title": "endofline",
            "summary": "endofline",
            "content": "endofline",
            "published": "endofline",
            "image": "endofline",
            "thumbnail": "endofline",
            "link": "endofline",
            "served": 1
        }
    }

@app.get("/articles")
def get_articles(limit: int = 10, offset: int = 0):
    """Get articles with pagination"""
    articles = db.get_recent_articles(limit=limit, offset=offset)
    
    # Parse images for each article
    for article in articles:
        parse_article_images(article)
    
    return {"articles": articles, "count": len(articles)}

@app.get("/articles/{article_id}")
def get_article(article_id: int):
    """Get a specific article by ID"""
    article = db.get_article_by_id(article_id)
    
    if not article:
        raise HTTPException(status_code=404, detail="Makale bulunamadı")
    
    # Parse images
    parse_article_images(article)
    
    return {"article": article}

@app.get("/search")
def search_articles(q: str, limit: int = 20):
    """Search articles by keyword"""
    if not q:
        raise HTTPException(status_code=400, detail="Arama sorgusu gerekli")
    
    articles = db.search_articles(q, limit=limit)
    
    # Parse images for each article
    for article in articles:
        parse_article_images(article)
    
    return {"articles": articles, "count": len(articles), "query": q}

@app.get("/tags/{tag}")
def get_articles_by_tag(tag: str, limit: int = 20):
    """Get articles by tag"""
    articles = db.get_articles_by_tag(tag, limit=limit)
    
    # Parse images for each article
    for article in articles:
        parse_article_images(article)
    
    return {"articles": articles, "count": len(articles), "tag": tag}

@app.get("/statistics")
def get_statistics():
    """Get database statistics"""
    return db.get_statistics()

@app.post("/reset")
def reset_served():
    """Reset served status - allows articles to be served again"""
    global served_indices, current_offset, articles_cache
    served_indices.clear()
    current_offset = 0
    articles_cache = []
    load_articles_batch()
    return {"message": "Sunum durumu sıfırlandı", "articles_loaded": len(articles_cache)}

# RSS Feed Endpoints

@app.get("/rss", response_class=Response)
def get_rss_feed(limit: int = 20):
    """Main RSS feed - returns latest articles"""
    try:
        articles = db.get_recent_articles(limit=limit)
        
        # Parse data for each article
        for article in articles:
            parse_article_data(article)
        
        # Create RSS feed
        rss_content = create_rss_feed(
            articles=articles,
            feed_title="AI Newspaper - Latest News",
            feed_description="Latest AI-generated news articles",
            feed_url="http://localhost:8000"
        )
        
        return Response(
            content=rss_content,
            media_type="application/rss+xml",
            headers={"Content-Type": "application/rss+xml; charset=utf-8"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating RSS feed: {str(e)}")

@app.get("/rss/latest", response_class=Response)
def get_latest_rss_feed(limit: int = 10):
    """Latest articles RSS feed"""
    try:
        articles = db.get_recent_articles(limit=limit)
        
        # Parse data for each article
        for article in articles:
            parse_article_data(article)
        
        # Create RSS feed
        rss_content = create_rss_feed(
            articles=articles,
            feed_title="AI Newspaper - Latest 10",
            feed_description="Latest 10 AI-generated news articles",
            feed_url="http://localhost:8000"
        )
        
        return Response(
            content=rss_content,
            media_type="application/rss+xml",
            headers={"Content-Type": "application/rss+xml; charset=utf-8"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating RSS feed: {str(e)}")

@app.get("/rss/category/{category_name}", response_class=Response)
def get_rss_feed_by_category(category_name: str, limit: int = 20):
    """RSS feed filtered by category"""
    try:
        # Validate category
        valid_categories = ["gündem", "ekonomi", "spor", "siyaset", "magazin", "yaşam", "eğitim", "sağlık", "astroloji"]
        if category_name not in valid_categories:
            raise HTTPException(status_code=400, detail=f"Invalid category. Valid categories: {valid_categories}")
        
        articles = db.get_articles_by_category(category_name, limit=limit)
        
        # Parse data for each article
        for article in articles:
            parse_article_data(article)
        
        # Create RSS feed
        rss_content = create_rss_feed(
            articles=articles,
            feed_title=f"AI Newspaper - {category_name.title()}",
            feed_description=f"AI-generated news articles in category '{category_name}'",
            feed_url="http://localhost:8000"
        )
        
        return Response(
            content=rss_content,
            media_type="application/rss+xml",
            headers={"Content-Type": "application/rss+xml; charset=utf-8"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating RSS feed: {str(e)}")

@app.get("/rss/tag/{tag_name}", response_class=Response)
def get_rss_feed_by_tag(tag_name: str, limit: int = 20):
    """RSS feed filtered by tag"""
    try:
        articles = db.get_articles_by_tag(tag_name, limit=limit)
        
        # Parse data for each article
        for article in articles:
            parse_article_data(article)
        
        # Create RSS feed
        rss_content = create_rss_feed(
            articles=articles,
            feed_title=f"AI Newspaper - {tag_name.title()}",
            feed_description=f"AI-generated news articles tagged with '{tag_name}'",
            feed_url="http://localhost:8000"
        )
        
        return Response(
            content=rss_content,
            media_type="application/rss+xml",
            headers={"Content-Type": "application/rss+xml; charset=utf-8"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating RSS feed: {str(e)}")

@app.get("/rss/search", response_class=Response)
def get_rss_feed_search(q: str, limit: int = 20):
    """RSS feed with search results"""
    if not q:
        raise HTTPException(status_code=400, detail="Search query is required")
    
    try:
        articles = db.search_articles(q, limit=limit)
        
        # Parse data for each article
        for article in articles:
            parse_article_data(article)
        
        # Create RSS feed
        rss_content = create_rss_feed(
            articles=articles,
            feed_title=f"AI Newspaper - Search: {q}",
            feed_description=f"AI-generated news articles matching '{q}'",
            feed_url="http://localhost:8000"
        )
        
        return Response(
            content=rss_content,
            media_type="application/rss+xml",
            headers={"Content-Type": "application/rss+xml; charset=utf-8"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating RSS feed: {str(e)}")