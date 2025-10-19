#!/usr/bin/env python3
"""
RSS to Database Module
Stores RSS articles in database with duplicate prevention and unified image handling
"""

import sqlite3
import hashlib
import json
import re
import time
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Set, Tuple
import logging
from pathlib import Path
from urllib.parse import urlparse, urljoin
import feedparser
import requests
import email.utils

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RSSArticle:
    """Unified data model for RSS articles"""
    
    def __init__(self):
        # Core article information
        self.title: str = ""
        self.description: str = ""
        self.content: str = ""
        self.summary: str = ""
        
        # URLs and links
        self.link: str = ""
        self.guid: str = ""
        self.comments: str = ""
        
        # Publication information
        self.published: Optional[datetime] = None
        self.updated: Optional[datetime] = None
        self.author: str = ""
        self.category: str = ""
        self.tags: List[str] = []
        
        # Media information
        self.enclosures: List[Dict[str, str]] = []
        self.media_content: List[Dict[str, str]] = []
        self.image_url: str = ""  # Primary image (backward compatibility)
        self.image_urls: List[str] = []  # All images
        
        # Source information
        self.source_name: str = ""
        self.source_url: str = ""
        self.feed_url: str = ""
        
        # Additional metadata
        self.language: str = ""
        self.rights: str = ""
        self.raw_data: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert article to dictionary for JSON serialization"""
        return {
            'title': self.title,
            'description': self.description,
            'content': self.content,
            'summary': self.summary,
            'link': self.link,
            'guid': self.guid,
            'comments': self.comments,
            'published': self.published.isoformat() if self.published else None,
            'updated': self.updated.isoformat() if self.updated else None,
            'author': self.author,
            'category': self.category,
            'tags': self.tags,
            'enclosures': self.enclosures,
            'media_content': self.media_content,
            'image_url': self.image_url,
            'image_urls': self.image_urls,
            'source_name': self.source_name,
            'source_url': self.source_url,
            'feed_url': self.feed_url,
            'language': self.language,
            'rights': self.rights
        }

    def __str__(self):
        return f"RSSArticle(title='{self.title[:50]}...', source='{self.source_name}', published='{self.published}')"

class RSSFeedReader:
    """RSS Feed Reader with unified data model"""
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Logging data
        self.feed_results = {
            'successful_feeds': [],
            'failed_feeds': [],
            'total_articles': 0,
            'articles_by_source': {},
            'processing_start_time': None,
            'processing_end_time': None
        }

    def parse_datetime(self, date_string: str) -> Optional[datetime]:
        """Parse various datetime formats from RSS feeds"""
        if not date_string:
            return None
            
        # Common datetime formats in RSS feeds
        formats = [
            '%a, %d %b %Y %H:%M:%S %z',  # RFC 2822
            '%a, %d %b %Y %H:%M:%S %Z',  # RFC 2822 with timezone name
            '%Y-%m-%dT%H:%M:%S%z',       # ISO 8601
            '%Y-%m-%dT%H:%M:%SZ',        # ISO 8601 UTC
            '%Y-%m-%dT%H:%M:%S',         # ISO 8601 without timezone
            '%Y-%m-%d %H:%M:%S',         # Simple format
            '%d.%m.%Y %H:%M',            # Turkish format
            '%d/%m/%Y %H:%M',            # Alternative format
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue
        
        # Try feedparser's date parsing as fallback
        try:
            parsed_date = email.utils.parsedate_tz(date_string)
            if parsed_date:
                timestamp = email.utils.mktime_tz(parsed_date)
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except:
            pass
            
        logger.warning(f"Could not parse date: {date_string}")
        return None

    def clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Decode HTML entities
        import html
        text = html.unescape(text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def extract_all_image_urls(self, entry: Dict[str, Any]) -> List[str]:
        """Extract all image URLs from various possible locations"""
        image_urls = []
        
        # Check for media:content
        if 'media_content' in entry:
            for media in entry['media_content']:
                if media.get('type', '').startswith('image/'):
                    url = media.get('url', '')
                    if url and url not in image_urls:
                        image_urls.append(url)
        
        # Check for enclosures
        if 'enclosures' in entry:
            for enclosure in entry['enclosures']:
                if enclosure.get('type', '').startswith('image/'):
                    url = enclosure.get('href', '')
                    if url and url not in image_urls:
                        image_urls.append(url)
        
        # Check for media:thumbnail
        if 'media_thumbnail' in entry:
            for thumbnail in entry['media_thumbnail']:
                url = thumbnail.get('url', '')
                if url and url not in image_urls:
                    image_urls.append(url)
        
        # Check for content with images
        content = entry.get('content', [{}])
        if content and isinstance(content, list):
            content_text = content[0].get('value', '')
            urls = self._extract_images_from_html(content_text)
            for url in urls:
                if url not in image_urls:
                    image_urls.append(url)
        
        # Check summary for images
        summary = entry.get('summary', '')
        if summary:
            urls = self._extract_images_from_html(summary)
            for url in urls:
                if url not in image_urls:
                    image_urls.append(url)
        
        # Check description for images
        description = entry.get('description', '')
        if description:
            urls = self._extract_images_from_html(description)
            for url in urls:
                if url not in image_urls:
                    image_urls.append(url)
        
        return image_urls
    
    def _extract_images_from_html(self, html_content: str) -> List[str]:
        """Extract all image URLs from HTML content using multiple patterns"""
        if not html_content:
            return []
        
        image_urls = []
        
        # Common image patterns in HTML
        patterns = [
            r'<img[^>]+src=["\']([^"\']+)["\']',  # Standard img tags
            r'<figure[^>]*>.*?<img[^>]+src=["\']([^"\']+)["\']',  # Images in figure tags
            r'background-image:\s*url\(["\']?([^"\']+)["\']?\)',  # CSS background images
            r'data-src=["\']([^"\']+)["\']',  # Lazy loading images
            r'data-lazy=["\']([^"\']+)["\']',  # Alternative lazy loading
            r'data-original=["\']([^"\']+)["\']',  # Another lazy loading pattern
            r'data-srcset=["\']([^"\']+)["\']',  # Responsive images
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                # Clean up the URL (remove HTML entities, etc.)
                clean_url = self._clean_image_url(match)
                if clean_url and clean_url not in image_urls:
                    image_urls.append(clean_url)
        
        return image_urls
    
    def _clean_image_url(self, url: str) -> str:
        """Clean and normalize image URL"""
        if not url:
            return ""
        
        # Decode HTML entities
        import html
        url = html.unescape(url)
        
        # Remove common URL parameters that might cause issues
        # Keep essential ones like width, height for responsive images
        url = re.sub(r'&amp;', '&', url)
        
        # Remove trailing parameters that are not essential
        # Keep width, height, quality, format parameters
        essential_params = ['width', 'height', 'w', 'h', 'quality', 'q', 'format', 'f']
        
        # Basic URL validation
        if not (url.startswith('http://') or url.startswith('https://')):
            return ""
        
        return url.strip()
    
    def extract_image_url(self, entry: Dict[str, Any]) -> str:
        """Extract primary image URL (backward compatibility)"""
        image_urls = self.extract_all_image_urls(entry)
        return image_urls[0] if image_urls else ""

    def parse_entry(self, entry: Dict[str, Any], feed_info: Dict[str, Any]) -> RSSArticle:
        """Parse a single RSS entry into unified format"""
        article = RSSArticle()
        
        # Basic information
        article.title = self.clean_text(entry.get('title', ''))
        article.description = self.clean_text(entry.get('description', ''))
        article.summary = self.clean_text(entry.get('summary', ''))
        article.link = entry.get('link', '')
        article.guid = entry.get('id', entry.get('guid', ''))
        article.comments = entry.get('comments', '')
        
        # Content (prefer content over description)
        content = entry.get('content', [])
        if content and isinstance(content, list):
            article.content = self.clean_text(content[0].get('value', ''))
        elif entry.get('content'):
            article.content = self.clean_text(entry['content'])
        else:
            article.content = article.description
        
        # Publication dates
        article.published = self.parse_datetime(entry.get('published', ''))
        article.updated = self.parse_datetime(entry.get('updated', ''))
        
        # Author information
        author = entry.get('author', '')
        if isinstance(author, dict):
            article.author = author.get('name', '')
        else:
            article.author = str(author) if author else ''
        
        # Category and tags
        article.category = entry.get('category', '')
        tags = entry.get('tags', [])
        if tags:
            article.tags = [tag.get('term', str(tag)) for tag in tags]
        
        # Media information
        article.image_urls = self.extract_all_image_urls(entry)
        article.image_url = article.image_urls[0] if article.image_urls else ""  # Primary image for backward compatibility
        
        # Enclosures
        if 'enclosures' in entry:
            article.enclosures = [
                {
                    'url': enc.get('href', ''),
                    'type': enc.get('type', ''),
                    'length': enc.get('length', '')
                }
                for enc in entry['enclosures']
            ]
        
        # Media content
        if 'media_content' in entry:
            article.media_content = [
                {
                    'url': media.get('url', ''),
                    'type': media.get('type', ''),
                    'width': media.get('width', ''),
                    'height': media.get('height', '')
                }
                for media in entry['media_content']
            ]
        
        # Source information
        article.source_name = feed_info.get('title', '')
        article.source_url = feed_info.get('link', '')
        article.feed_url = feed_info.get('href', '')
        
        # Additional metadata
        article.language = feed_info.get('language', '')
        article.rights = feed_info.get('rights', '')
        
        # Store raw data for debugging
        article.raw_data = entry
        
        return article

    def fetch_feed(self, feed_url: str) -> Optional[Dict[str, Any]]:
        """Fetch and parse a single RSS feed"""
        feed_info = {
            'url': feed_url,
            'attempts': 0,
            'errors': [],
            'status': None,
            'article_count': 0,
            'feed_title': '',
            'success': False
        }
        
        for attempt in range(self.max_retries):
            feed_info['attempts'] = attempt + 1
            try:
                logger.info(f"Fetching feed: {feed_url} (attempt {attempt + 1})")
                
                response = self.session.get(feed_url, timeout=self.timeout)
                response.raise_for_status()
                
                # Parse with feedparser
                feed = feedparser.parse(response.content)
                
                if feed.bozo:
                    warning_msg = f"Feed parsing warnings for {feed_url}: {feed.bozo_exception}"
                    logger.warning(warning_msg)
                    feed_info['errors'].append(warning_msg)
                
                feed_info['status'] = feed.status if hasattr(feed, 'status') else 200
                feed_info['article_count'] = len(feed.entries)
                feed_info['feed_title'] = feed.feed.get('title', '')
                feed_info['success'] = True
                
                return {
                    'href': feed_url,
                    'title': feed.feed.get('title', ''),
                    'link': feed.feed.get('link', ''),
                    'description': feed.feed.get('description', ''),
                    'language': feed.feed.get('language', ''),
                    'rights': feed.feed.get('rights', ''),
                    'entries': feed.entries,
                    'status': feed.status if hasattr(feed, 'status') else 200,
                    'feed_info': feed_info
                }
                
            except requests.exceptions.RequestException as e:
                error_msg = f"Network error fetching {feed_url}: {e}"
                logger.error(error_msg)
                feed_info['errors'].append(error_msg)
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    self.feed_results['failed_feeds'].append(feed_info)
                    return None
            except Exception as e:
                error_msg = f"Error parsing feed {feed_url}: {e}"
                logger.error(error_msg)
                feed_info['errors'].append(error_msg)
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    self.feed_results['failed_feeds'].append(feed_info)
                    return None
        
        self.feed_results['failed_feeds'].append(feed_info)
        return None

    def read_feeds_from_file(self, file_path: str) -> List[str]:
        """Read RSS feed URLs from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            logger.info(f"Loaded {len(urls)} RSS feed URLs from {file_path}")
            return urls
        except Exception as e:
            logger.error(f"Error reading RSS list file {file_path}: {e}")
            return []

    def process_all_feeds(self, rss_list_file: str) -> List[RSSArticle]:
        """Process all RSS feeds from the list file"""
        feed_urls = self.read_feeds_from_file(rss_list_file)
        all_articles = []
        
        # Initialize processing start time
        self.feed_results['processing_start_time'] = datetime.now()
        
        logger.info(f"Processing {len(feed_urls)} RSS feeds...")
        
        for i, feed_url in enumerate(feed_urls, 1):
            logger.info(f"Processing feed {i}/{len(feed_urls)}: {feed_url}")
            
            feed_data = self.fetch_feed(feed_url)
            if not feed_data:
                logger.error(f"Failed to fetch feed: {feed_url}")
                continue
            
            # Track successful feed
            feed_info = feed_data.get('feed_info', {})
            self.feed_results['successful_feeds'].append(feed_info)
            
            # Parse entries
            articles_from_feed = 0
            for entry in feed_data['entries']:
                try:
                    article = self.parse_entry(entry, feed_data)
                    if article.title:  # Only add articles with titles
                        all_articles.append(article)
                        articles_from_feed += 1
                        
                        # Track articles by source
                        source_name = article.source_name or 'Unknown'
                        self.feed_results['articles_by_source'][source_name] = \
                            self.feed_results['articles_by_source'].get(source_name, 0) + 1
                            
                except Exception as e:
                    logger.error(f"Error parsing entry from {feed_url}: {e}")
                    continue
            
            # Update feed info with actual article count
            feed_info['article_count'] = articles_from_feed
            
            # Small delay between requests to be respectful
            time.sleep(0.5)
        
        # Set processing end time and total articles
        self.feed_results['processing_end_time'] = datetime.now()
        self.feed_results['total_articles'] = len(all_articles)
        
        logger.info(f"Successfully processed {len(all_articles)} articles from {len(feed_urls)} feeds")
        return all_articles

    def save_articles_to_json(self, articles: List[RSSArticle], filename: str):
        """Save articles to JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump([article.to_dict() for article in articles], f, 
                         ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(articles)} articles to {filename}")
        except Exception as e:
            logger.error(f"Error saving articles to {filename}: {e}")

    def create_rss_log(self, filename: str = 'rsslog.txt'):
        """Create detailed RSS processing log file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # Header
                f.write("=" * 80 + "\n")
                f.write("RSS FEED PROCESSING LOG\n")
                f.write("=" * 80 + "\n")
                f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Processing started: {self.feed_results['processing_start_time'].strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Processing ended: {self.feed_results['processing_end_time'].strftime('%Y-%m-%d %H:%M:%S')}\n")
                
                if self.feed_results['processing_start_time'] and self.feed_results['processing_end_time']:
                    duration = self.feed_results['processing_end_time'] - self.feed_results['processing_start_time']
                    f.write(f"Total processing time: {duration}\n")
                
                f.write("\n")
                
                # Summary
                f.write("SUMMARY\n")
                f.write("-" * 40 + "\n")
                f.write(f"Total articles processed: {self.feed_results['total_articles']}\n")
                f.write(f"Successful feeds: {len(self.feed_results['successful_feeds'])}\n")
                f.write(f"Failed feeds: {len(self.feed_results['failed_feeds'])}\n")
                f.write(f"Total feeds attempted: {len(self.feed_results['successful_feeds']) + len(self.feed_results['failed_feeds'])}\n")
                f.write("\n")
                
                # Articles by source
                f.write("ARTICLES BY SOURCE\n")
                f.write("-" * 40 + "\n")
                if self.feed_results['articles_by_source']:
                    sorted_sources = sorted(self.feed_results['articles_by_source'].items(), 
                                          key=lambda x: x[1], reverse=True)
                    for source, count in sorted_sources:
                        f.write(f"{source}: {count} articles\n")
                else:
                    f.write("No articles processed\n")
                f.write("\n")
                
                # Successful feeds
                f.write("SUCCESSFUL FEEDS\n")
                f.write("-" * 40 + "\n")
                if self.feed_results['successful_feeds']:
                    for feed in self.feed_results['successful_feeds']:
                        f.write(f"✓ {feed['feed_title'] or 'Unknown Title'}\n")
                        f.write(f"  URL: {feed['url']}\n")
                        f.write(f"  Articles: {feed['article_count']}\n")
                        f.write(f"  Attempts: {feed['attempts']}\n")
                        f.write(f"  Status: {feed['status']}\n")
                        if feed['errors']:
                            f.write(f"  Warnings: {'; '.join(feed['errors'])}\n")
                        f.write("\n")
                else:
                    f.write("No successful feeds\n")
                f.write("\n")
                
                # Failed feeds
                f.write("FAILED FEEDS\n")
                f.write("-" * 40 + "\n")
                if self.feed_results['failed_feeds']:
                    for feed in self.feed_results['failed_feeds']:
                        f.write(f"✗ {feed['url']}\n")
                        f.write(f"  Attempts: {feed['attempts']}\n")
                        f.write(f"  Status: {feed['status'] or 'N/A'}\n")
                        f.write(f"  Errors:\n")
                        for error in feed['errors']:
                            f.write(f"    - {error}\n")
                        f.write("\n")
                else:
                    f.write("No failed feeds\n")
                f.write("\n")
                
                # Feed URLs list
                f.write("ALL FEED URLS PROCESSED\n")
                f.write("-" * 40 + "\n")
                all_feeds = self.feed_results['successful_feeds'] + self.feed_results['failed_feeds']
                for i, feed in enumerate(all_feeds, 1):
                    status = "✓" if feed['success'] else "✗"
                    f.write(f"{i:2d}. {status} {feed['url']}\n")
                
                f.write("\n" + "=" * 80 + "\n")
                f.write("END OF LOG\n")
                f.write("=" * 80 + "\n")
            
            logger.info(f"RSS processing log saved to {filename}")
            
        except Exception as e:
            logger.error(f"Error creating RSS log file {filename}: {e}")

    def print_summary(self, articles: List[RSSArticle]):
        """Print a summary of processed articles"""
        print(f"\n{'='*60}")
        print(f"RSS FEED PROCESSING SUMMARY")
        print(f"{'='*60}")
        print(f"Total articles processed: {len(articles)}")
        
        # Group by source
        sources = {}
        for article in articles:
            source = article.source_name or 'Unknown'
            sources[source] = sources.get(source, 0) + 1
        
        print(f"\nArticles by source:")
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
            print(f"  {source}: {count} articles")
        
        # Show recent articles
        def normalize_datetime(dt):
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        
        recent_articles = sorted([a for a in articles if a.published], 
                               key=lambda x: normalize_datetime(x.published), 
                               reverse=True)[:5]
        
        if recent_articles:
            print(f"\nMost recent articles:")
            for article in recent_articles:
                print(f"  • {article.title[:60]}...")
                print(f"    Source: {article.source_name}")
                print(f"    Published: {article.published}")
                print()


class RSSDatabase:
    """Database handler for RSS articles with duplicate prevention"""
    
    def __init__(self, db_path: str = 'rss_articles.db'):
        # Resolve paths relative to script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = db_path if os.path.isabs(db_path) else os.path.join(script_dir, db_path)
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create articles table with unified image_urls column
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS articles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        description TEXT,
                        content TEXT,
                        summary TEXT,
                        link TEXT UNIQUE,
                        guid TEXT UNIQUE,
                        comments TEXT,
                        published DATETIME,
                        updated DATETIME,
                        author TEXT,
                        category TEXT,
                        tags TEXT,  -- JSON array
                        enclosures TEXT,  -- JSON array
                        media_content TEXT,  -- JSON array
                        image_urls TEXT,  -- JSON array of ALL image URLs (consolidated)
                        source_name TEXT,
                        source_url TEXT,
                        feed_url TEXT,
                        language TEXT,
                        rights TEXT,
                        content_hash TEXT UNIQUE,  -- For duplicate detection
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        is_read BOOLEAN DEFAULT FALSE,
                        event_group_id INTEGER  -- For grouping related articles
                    )
                ''')
                
                # Create indexes for better performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_guid ON articles(guid)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_link ON articles(link)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON articles(content_hash)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_published ON articles(published)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_source_name ON articles(source_name)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON articles(created_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_is_read ON articles(is_read)')
                
                # Create feed_stats table for tracking feed processing
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS feed_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        feed_url TEXT UNIQUE,
                        last_processed DATETIME,
                        total_articles INTEGER DEFAULT 0,
                        last_article_count INTEGER DEFAULT 0,
                        processing_duration REAL,
                        status TEXT DEFAULT 'success',
                        error_message TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_feed_url ON feed_stats(feed_url)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_processed ON feed_stats(last_processed)')
                
                # Migration: Remove old image_url column if it exists and migrate data
                cursor.execute("PRAGMA table_info(articles)")
                columns = [column[1] for column in cursor.fetchall()]
                
                # Ensure image_urls column exists
                if 'image_urls' not in columns:
                    cursor.execute('ALTER TABLE articles ADD COLUMN image_urls TEXT')
                    logger.info("Added image_urls column to articles table")
                
                # Ensure is_read column exists (for backward compatibility)
                if 'is_read' not in columns:
                    cursor.execute('ALTER TABLE articles ADD COLUMN is_read BOOLEAN DEFAULT FALSE')
                    logger.info("Added is_read column to articles table")
                
                # Ensure event_group_id column exists (for article grouping)
                if 'event_group_id' not in columns:
                    cursor.execute('ALTER TABLE articles ADD COLUMN event_group_id INTEGER')
                    logger.info("Added event_group_id column to articles table")
                
                # Create index for event_group_id (after ensuring column exists)
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_event_group_id ON articles(event_group_id)')
                
                
                conn.commit()
                logger.info(f"Database initialized successfully: {self.db_path}")
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    
    
    def _validate_and_filter_image_urls(self, urls: List[str]) -> List[str]:
        """Validate and filter image URLs, removing duplicates and invalid ones"""
        seen = set()
        validated = []
        
        for url in urls:
            if not url:
                continue
            
            # Basic URL validation
            url = url.strip()
            
            # Must be valid HTTP/HTTPS URL
            if not (url.startswith('http://') or url.startswith('https://')):
                continue
            
            # Basic URL validation
            try:
                parsed = urlparse(url)
                if not parsed.netloc:
                    continue
            except:
                continue
            
            # Filter out tracking pixels and tiny images
            if any(x in url.lower() for x in ['1x1', 'pixel', 'tracking', 'beacon']):
                continue
            
            if url not in seen:
                seen.add(url)
                validated.append(url)
        
        return validated
    
    def extract_all_image_urls_from_article(self, article: RSSArticle) -> List[str]:
        """
        Extract images only from explicit RSS feed fields.
        Safe and reliable - no HTML parsing or external page fetching.
        """
        rss_images = set()
        
        # 1. RSS Feed Images (explicit image fields)
        if article.image_urls:
            rss_images.update(article.image_urls)
        
        # 2. Extract from enclosures (RSS explicit field)
        if article.enclosures:
            for enclosure in article.enclosures:
                if isinstance(enclosure, dict):
                    enc_type = enclosure.get('type', '')
                    if enc_type.startswith('image/'):
                        url = enclosure.get('url', enclosure.get('href', ''))
                        if url:
                            rss_images.add(url)
        
        # 3. Extract from media_content (RSS explicit field)
        if article.media_content:
            for media in article.media_content:
                if isinstance(media, dict):
                    media_type = media.get('type', '')
                    if media_type.startswith('image/') or 'image' in media_type.lower():
                        url = media.get('url', '')
                        if url:
                            rss_images.add(url)
        
        # 4. Add legacy image_url if it exists (RSS explicit field)
        if article.image_url:
            rss_images.add(article.image_url)
        
        # Validate and return RSS images only
        final_images = self._validate_and_filter_image_urls(list(rss_images))
        
        logger.debug(f"RSS images found: {len(final_images)} for article: {article.title[:50]}")
        
        return final_images
    
    def generate_content_hash(self, article: RSSArticle) -> str:
        """Generate a unique hash for article content to detect duplicates"""
        # Use title + link + published date for hash generation
        content_string = f"{article.title}|{article.link}|{article.published}"
        return hashlib.md5(content_string.encode('utf-8')).hexdigest()
    
    def article_exists(self, article: RSSArticle) -> bool:
        """Check if article already exists in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check by GUID first (most reliable)
                if article.guid:
                    cursor.execute('SELECT id FROM articles WHERE guid = ?', (article.guid,))
                    if cursor.fetchone():
                        return True
                
                # Check by link
                if article.link:
                    cursor.execute('SELECT id FROM articles WHERE link = ?', (article.link,))
                    if cursor.fetchone():
                        return True
                
                # Check by content hash
                content_hash = self.generate_content_hash(article)
                cursor.execute('SELECT id FROM articles WHERE content_hash = ?', (content_hash,))
                if cursor.fetchone():
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Error checking if article exists: {e}")
            return False
    
    def insert_article(self, article: RSSArticle) -> bool:
        """Insert article into database if it doesn't exist, with consolidated image URLs"""
        try:
            if self.article_exists(article):
                logger.debug(f"Article already exists, skipping: {article.title[:50]}...")
                return False
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                content_hash = self.generate_content_hash(article)
                
                # Extract ALL image URLs from all possible sources
                consolidated_image_urls = self.extract_all_image_urls_from_article(article)
                
                cursor.execute('''
                    INSERT INTO articles (
                        title, description, content, summary, link, guid, comments,
                        published, updated, author, category, tags, enclosures,
                        media_content, image_urls, source_name, source_url, feed_url,
                        language, rights, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    article.title,
                    article.description,
                    article.content,
                    article.summary,
                    article.link,
                    article.guid,
                    article.comments,
                    article.published.isoformat() if article.published else None,
                    article.updated.isoformat() if article.updated else None,
                    article.author,
                    article.category,
                    json.dumps(article.tags) if article.tags else None,
                    json.dumps(article.enclosures) if article.enclosures else None,
                    json.dumps(article.media_content) if article.media_content else None,
                    json.dumps(consolidated_image_urls) if consolidated_image_urls else None,
                    article.source_name,
                    article.source_url,
                    article.feed_url,
                    article.language,
                    article.rights,
                    content_hash
                ))
                
                conn.commit()
                
                # Log image extraction stats
                if consolidated_image_urls:
                    logger.debug(f"Article inserted with {len(consolidated_image_urls)} images: {article.title[:50]}...")
                else:
                    logger.debug(f"Article inserted (no images): {article.title[:50]}...")
                
                return True
                
        except sqlite3.IntegrityError as e:
            logger.debug(f"Article already exists (integrity error): {article.title[:50]}...")
            return False
        except Exception as e:
            logger.error(f"Error inserting article: {e}")
            return False
    
    def insert_articles_batch(self, articles: List[RSSArticle]) -> Dict[str, int]:
        """Insert multiple articles and return statistics"""
        stats = {
            'total_processed': len(articles),
            'new_articles': 0,
            'duplicates': 0,
            'errors': 0
        }
        
        for article in articles:
            try:
                if self.insert_article(article):
                    stats['new_articles'] += 1
                else:
                    stats['duplicates'] += 1
            except Exception as e:
                logger.error(f"Error processing article: {e}")
                stats['errors'] += 1
        
        return stats
    
    def update_feed_stats(self, feed_url: str, article_count: int, 
                         processing_duration: float, status: str = 'success', 
                         error_message: str = None):
        """Update feed processing statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO feed_stats (
                        feed_url, last_processed, last_article_count,
                        processing_duration, status, error_message, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (feed_url, datetime.now().isoformat(), article_count, 
                     processing_duration, status, error_message))
                
                # Update total articles count
                cursor.execute('''
                    UPDATE feed_stats 
                    SET total_articles = total_articles + ? 
                    WHERE feed_url = ?
                ''', (article_count, feed_url))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error updating feed stats: {e}")
    
    def get_article_count(self) -> int:
        """Get total number of articles in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM articles')
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting article count: {e}")
            return 0
    
    def get_articles_by_source(self) -> Dict[str, int]:
        """Get article count by source"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT source_name, COUNT(*) 
                    FROM articles 
                    GROUP BY source_name 
                    ORDER BY COUNT(*) DESC
                ''')
                return dict(cursor.fetchall())
        except Exception as e:
            logger.error(f"Error getting articles by source: {e}")
            return {}
    
    def get_recent_articles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent articles from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM articles 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting recent articles: {e}")
            return []
    
    def get_image_statistics(self) -> Dict[str, Any]:
        """Get statistics about images in the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                stats = {
                    'total_articles': 0,
                    'articles_with_images': 0,
                    'articles_without_images': 0,
                    'total_images': 0,
                    'average_images_per_article': 0,
                    'max_images_in_article': 0
                }
                
                # Get total articles
                cursor.execute('SELECT COUNT(*) FROM articles')
                stats['total_articles'] = cursor.fetchone()[0]
                
                # Get articles with images
                cursor.execute('''
                    SELECT COUNT(*) FROM articles 
                    WHERE image_urls IS NOT NULL AND image_urls != '[]'
                ''')
                stats['articles_with_images'] = cursor.fetchone()[0]
                
                stats['articles_without_images'] = stats['total_articles'] - stats['articles_with_images']
                
                # Count total images and find max
                cursor.execute('SELECT image_urls FROM articles WHERE image_urls IS NOT NULL')
                total_images = 0
                max_images = 0
                
                for row in cursor.fetchall():
                    try:
                        urls = json.loads(row[0])
                        if isinstance(urls, list):
                            count = len(urls)
                            total_images += count
                            max_images = max(max_images, count)
                    except:
                        pass
                
                stats['total_images'] = total_images
                stats['max_images_in_article'] = max_images
                
                if stats['articles_with_images'] > 0:
                    stats['average_images_per_article'] = round(
                        total_images / stats['articles_with_images'], 2
                    )
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting image statistics: {e}")
            return {}
    
    def get_feed_stats(self) -> List[Dict[str, Any]]:
        """Get feed processing statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM feed_stats 
                    ORDER BY last_processed DESC
                ''')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting feed stats: {e}")
            return []
    
    def cleanup_old_articles(self, days: int = 30):
        """Remove articles older than specified days"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM articles 
                    WHERE created_at < datetime('now', '-{} days')
                '''.format(days))
                deleted_count = cursor.rowcount
                conn.commit()
                logger.info(f"Cleaned up {deleted_count} old articles")
                return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up old articles: {e}")
            return 0
    
    def mark_article_as_read(self, article_id: int) -> bool:
        """Mark a specific article as read"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE articles 
                    SET is_read = TRUE, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (article_id,))
                conn.commit()
                logger.debug(f"Article {article_id} marked as read")
                return True
        except Exception as e:
            logger.error(f"Error marking article {article_id} as read: {e}")
            return False
    
    def mark_article_as_unread(self, article_id: int) -> bool:
        """Mark a specific article as unread"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE articles 
                    SET is_read = FALSE, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (article_id,))
                conn.commit()
                logger.debug(f"Article {article_id} marked as unread")
                return True
        except Exception as e:
            logger.error(f"Error marking article {article_id} as unread: {e}")
            return False
    
    def mark_articles_as_read(self, article_ids: List[int]) -> int:
        """Mark multiple articles as read"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                placeholders = ','.join('?' * len(article_ids))
                cursor.execute(f'''
                    UPDATE articles 
                    SET is_read = TRUE, updated_at = CURRENT_TIMESTAMP 
                    WHERE id IN ({placeholders})
                ''', article_ids)
                conn.commit()
                updated_count = cursor.rowcount
                logger.info(f"Marked {updated_count} articles as read")
                return updated_count
        except Exception as e:
            logger.error(f"Error marking articles as read: {e}")
            return 0
    
    def get_unread_articles(self, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Get unread articles from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM articles 
                    WHERE is_read = FALSE 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                ''', (limit, offset))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting unread articles: {e}")
            return []
    
    def get_read_articles(self, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Get read articles from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM articles 
                    WHERE is_read = TRUE 
                    ORDER BY updated_at DESC 
                    LIMIT ? OFFSET ?
                ''', (limit, offset))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting read articles: {e}")
            return []
    
    def get_unread_count(self) -> int:
        """Get count of unread articles"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM articles WHERE is_read = FALSE')
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            return 0
    
    def get_read_count(self) -> int:
        """Get count of read articles"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM articles WHERE is_read = TRUE')
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting read count: {e}")
            return 0
    
    def get_unread_articles_by_source(self, source_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get unread articles from a specific source"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM articles 
                    WHERE is_read = FALSE AND source_name = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (source_name, limit))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting unread articles by source: {e}")
            return []

class RSSToDatabase:
    """Main class for processing RSS feeds and storing in database"""
    
    def __init__(self, db_path: str = 'rss_articles.db'):
        # Resolve paths relative to script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        resolved_db_path = db_path if os.path.isabs(db_path) else os.path.join(script_dir, db_path)
        self.db = RSSDatabase(resolved_db_path)
        self.rss_reader = RSSFeedReader()
    
    def process_feeds_to_database(self, rss_list_file: str = 'rsslist.txt') -> Dict[str, Any]:
        """Process all RSS feeds and store articles in database"""
        # Resolve rss_list_file path relative to script location
        if not os.path.isabs(rss_list_file):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            rss_list_file = os.path.join(script_dir, rss_list_file)
        logger.info("Starting RSS to database processing...")
        
        start_time = datetime.now()
        total_stats = {
            'feeds_processed': 0,
            'feeds_successful': 0,
            'feeds_failed': 0,
            'total_articles_processed': 0,
            'new_articles_added': 0,
            'duplicates_skipped': 0,
            'errors': 0,
            'processing_time': 0
        }
        
        try:
            # Get feed URLs
            feed_urls = self.rss_reader.read_feeds_from_file(rss_list_file)
            total_stats['feeds_processed'] = len(feed_urls)
            
            logger.info(f"Processing {len(feed_urls)} RSS feeds...")
            
            for i, feed_url in enumerate(feed_urls, 1):
                feed_start_time = datetime.now()
                logger.info(f"Processing feed {i}/{len(feed_urls)}: {feed_url}")
                
                try:
                    # Fetch feed
                    feed_data = self.rss_reader.fetch_feed(feed_url)
                    if not feed_data:
                        logger.error(f"Failed to fetch feed: {feed_url}")
                        total_stats['feeds_failed'] += 1
                        self.db.update_feed_stats(feed_url, 0, 0, 'failed', 'Failed to fetch feed')
                        continue
                    
                    # Parse articles
                    articles = []
                    for entry in feed_data['entries']:
                        try:
                            article = self.rss_reader.parse_entry(entry, feed_data)
                            if article.title:  # Only process articles with titles
                                articles.append(article)
                        except Exception as e:
                            logger.error(f"Error parsing entry from {feed_url}: {e}")
                            total_stats['errors'] += 1
                            continue
                    
                    # Store articles in database
                    if articles:
                        batch_stats = self.db.insert_articles_batch(articles)
                        total_stats['total_articles_processed'] += len(articles)
                        total_stats['new_articles_added'] += batch_stats['new_articles']
                        total_stats['duplicates_skipped'] += batch_stats['duplicates']
                        total_stats['errors'] += batch_stats['errors']
                        
                        # Update feed stats
                        feed_duration = (datetime.now() - feed_start_time).total_seconds()
                        self.db.update_feed_stats(feed_url, batch_stats['new_articles'], 
                                                feed_duration, 'success')
                        
                        logger.info(f"Feed {feed_url}: {batch_stats['new_articles']} new, "
                                  f"{batch_stats['duplicates']} duplicates")
                    else:
                        logger.warning(f"No articles found in feed: {feed_url}")
                        self.db.update_feed_stats(feed_url, 0, 0, 'success', 'No articles found')
                    
                    total_stats['feeds_successful'] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing feed {feed_url}: {e}")
                    total_stats['feeds_failed'] += 1
                    self.db.update_feed_stats(feed_url, 0, 0, 'failed', str(e))
                    continue
                
                # Small delay between requests
                import time
                time.sleep(0.5)
            
            # Calculate total processing time
            total_stats['processing_time'] = (datetime.now() - start_time).total_seconds()
            
            logger.info("RSS to database processing completed!")
            return total_stats
            
        except Exception as e:
            logger.error(f"Error in RSS to database processing: {e}")
            total_stats['processing_time'] = (datetime.now() - start_time).total_seconds()
            return total_stats
    
    def print_processing_summary(self, stats: Dict[str, Any]):
        """Print processing summary with image statistics"""
        print(f"\n{'='*60}")
        print(f"RSS TO DATABASE PROCESSING SUMMARY")
        print(f"{'='*60}")
        print(f"Feeds processed: {stats['feeds_processed']}")
        print(f"Successful feeds: {stats['feeds_successful']}")
        print(f"Failed feeds: {stats['feeds_failed']}")
        print(f"Total articles processed: {stats['total_articles_processed']}")
        print(f"New articles added: {stats['new_articles_added']}")
        print(f"Duplicates skipped: {stats['duplicates_skipped']}")
        print(f"Errors: {stats['errors']}")
        print(f"Processing time: {stats['processing_time']:.2f} seconds")
        
        # Database statistics
        total_articles = self.db.get_article_count()
        articles_by_source = self.db.get_articles_by_source()
        
        print(f"\nDATABASE STATISTICS")
        print(f"{'='*40}")
        print(f"Total articles in database: {total_articles}")
        
        if articles_by_source:
            print(f"\nArticles by source:")
            for source, count in list(articles_by_source.items())[:10]:  # Top 10
                print(f"  {source}: {count} articles")
        
        # Image statistics
        image_stats = self.db.get_image_statistics()
        if image_stats:
            print(f"\nIMAGE STATISTICS")
            print(f"{'='*40}")
            print(f"Articles with images: {image_stats.get('articles_with_images', 0)}")
            print(f"Articles without images: {image_stats.get('articles_without_images', 0)}")
            print(f"Total images extracted: {image_stats.get('total_images', 0)}")
            print(f"Average images per article: {image_stats.get('average_images_per_article', 0)}")
            print(f"Max images in a single article: {image_stats.get('max_images_in_article', 0)}")
        
        
        # Read/Unread statistics
        unread_count = self.db.get_unread_count()
        read_count = self.db.get_read_count()
        print(f"\nREAD STATUS STATISTICS")
        print(f"{'='*40}")
        print(f"Unread articles: {unread_count}")
        print(f"Read articles: {read_count}")
        print(f"Total articles: {unread_count + read_count}")
    
    def get_database_summary(self) -> Dict[str, Any]:
        """Get comprehensive database summary"""
        return {
            'total_articles': self.db.get_article_count(),
            'unread_articles': self.db.get_unread_count(),
            'read_articles': self.db.get_read_count(),
            'articles_by_source': self.db.get_articles_by_source(),
            'recent_articles': self.db.get_recent_articles(5),
            'feed_stats': self.db.get_feed_stats()
        }

def run(rss_list_file: str = 'rsslist.txt', db_path: str = 'rss_articles.db') -> Dict[str, Any]:
    """Run RSS to database processing with optional parameters"""
    rss2db = RSSToDatabase(db_path)
    stats = rss2db.process_feeds_to_database(rss_list_file)
    rss2db.print_processing_summary(stats)
    return stats

def main():
    """Main function to run RSS to database processing"""
    rss2db = RSSToDatabase()
    
    # Process feeds and store in database
    stats = rss2db.process_feeds_to_database()
    
    # Print summary
    rss2db.print_processing_summary(stats)
    
    # Show some recent articles
    recent_articles = rss2db.db.get_recent_articles(3)
    if recent_articles:
        print(f"\n{'='*60}")
        print(f"RECENT ARTICLES IN DATABASE")
        print(f"{'='*60}")
        
        for i, article in enumerate(recent_articles, 1):
            print(f"\nArticle {i}:")
            print(f"Title: {article['title']}")
            print(f"Source: {article['source_name']}")
            print(f"Published: {article['published']}")
            print(f"Added to DB: {article['created_at']}")
            print(f"Link: {article['link']}")
            
            # Display consolidated image URLs
            if article.get('image_urls'):
                try:
                    image_urls = json.loads(article['image_urls'])
                    if image_urls:
                        print(f"Images found: {len(image_urls)}")
                        for idx, img_url in enumerate(image_urls[:3], 1):  # Show first 3
                            print(f"  Image {idx}: {img_url[:80]}...")
                        if len(image_urls) > 3:
                            print(f"  ... and {len(image_urls) - 3} more")
                except:
                    pass

if __name__ == "__main__":
    main()
