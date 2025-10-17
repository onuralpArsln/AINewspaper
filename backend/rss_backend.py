from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sqlite3
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any, List, Optional
from db_query import OurArticlesDatabaseQuery

# RSS Backend Server
# uvicorn rss_backend:app --reload --port 8001

# Database query interface
db = OurArticlesDatabaseQuery('our_articles.db')

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    print("Starting RSS Backend Server...")
    print("Connecting to our_articles.db...")
    
    # Test database connection
    try:
        stats = db.get_statistics()
        print(f"Connected successfully!")
        print(f"Total articles in database: {stats['total_articles']}")
        print(f"Articles with images: {stats['articles_with_images']}")
    except Exception as e:
        print(f"Database connection error: {e}")
    
    yield  # Server is running
    
    # Shutdown
    print("Shutting down RSS Backend Server...")

# Initialize FastAPI app with lifespan handler
app = FastAPI(
    title="AI Newspaper RSS Backend",
    description="RSS feed server for newsarticles",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def parse_article_data(article: Dict[str, Any]) -> Dict[str, Any]:
    """Parse JSON fields in article (images and tags)"""
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
                   feed_url: str = "http://localhost:8001") -> str:
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
    ET.SubElement(channel, "generator").text = "AI Newspaper RSS Backend"
    
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
        ET.SubElement(item, "link").text = f"{feed_url}/article/{article['id']}"
        ET.SubElement(item, "guid").text = f"{feed_url}/article/{article['id']}"
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

@app.get("/")
def root():
    """Root endpoint with RSS feed information"""
    stats = db.get_statistics()
    return {
        "message": "AI Newspaper RSS Backend",
        "status": "running",
        "database": "our_articles.db",
        "statistics": stats,
        "rss_feeds": {
            "main_feed": "/rss",
            "latest_10": "/rss/latest",
            "by_category": "/rss/category/{category_name}",
            "by_tag": "/rss/tag/{tag_name}",
            "search": "/rss/search?q={query}"
        },
        "categories": ["gündem", "ekonomi", "spor", "siyaset", "magazin", "yaşam", "eğitim", "sağlık", "astroloji"]
    }

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
            feed_url="http://localhost:8001"
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
            feed_url="http://localhost:8001"
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
            feed_url="http://localhost:8001"
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
            feed_url="http://localhost:8001"
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
            feed_url="http://localhost:8001"
        )
        
        return Response(
            content=rss_content,
            media_type="application/rss+xml",
            headers={"Content-Type": "application/rss+xml; charset=utf-8"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating RSS feed: {str(e)}")

@app.get("/article/{article_id}")
def get_article_page(article_id: int):
    """Get individual article page (for RSS item links)"""
    try:
        article = db.get_article_by_id(article_id)
        
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        # Parse data
        parse_article_data(article)
        
        return {
            "article": article,
            "rss_feed": "/rss"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving article: {str(e)}")

@app.get("/api/articles")
def get_articles_api(limit: int = 10, offset: int = 0):
    """API endpoint to get articles as JSON (for debugging)"""
    try:
        articles = db.get_recent_articles(limit=limit, offset=offset)
        
        # Parse data for each article
        for article in articles:
            parse_article_data(article)
        
        return {"articles": articles, "count": len(articles)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving articles: {str(e)}")

@app.get("/api/articles/category/{category_name}")
def get_articles_by_category_api(category_name: str, limit: int = 10, offset: int = 0):
    """API endpoint to get articles by category as JSON"""
    try:
        # Validate category
        valid_categories = ["gündem", "ekonomi", "spor", "siyaset", "magazin", "yaşam", "eğitim", "sağlık", "astroloji"]
        if category_name not in valid_categories:
            raise HTTPException(status_code=400, detail=f"Invalid category. Valid categories: {valid_categories}")
        
        articles = db.get_articles_by_category(category_name, limit=limit)
        
        # Parse data for each article
        for article in articles:
            parse_article_data(article)
        
        return {"articles": articles, "count": len(articles), "category": category_name}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving articles: {str(e)}")

@app.get("/api/statistics")
def get_statistics_api():
    """Get database statistics"""
    return db.get_statistics()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
