#!/usr/bin/env python3
"""
RSS Feed Reader and Tester
Handles multiple RSS feeds with different structures and provides unified data model
"""

import feedparser
import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
import logging
import re
from urllib.parse import urljoin, urlparse
import time
import json

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
        self.image_url: str = ""
        
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
            import email.utils
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

    def extract_image_url(self, entry: Dict[str, Any]) -> str:
        """Extract image URL from various possible locations"""
        # Check for media:content
        if 'media_content' in entry:
            for media in entry['media_content']:
                if media.get('type', '').startswith('image/'):
                    return media.get('url', '')
        
        # Check for enclosures
        if 'enclosures' in entry:
            for enclosure in entry['enclosures']:
                if enclosure.get('type', '').startswith('image/'):
                    return enclosure.get('href', '')
        
        # Check for media:thumbnail
        if 'media_thumbnail' in entry:
            return entry['media_thumbnail'][0].get('url', '')
        
        # Check for content with images
        content = entry.get('content', [{}])
        if content and isinstance(content, list):
            content_text = content[0].get('value', '')
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content_text)
            if img_match:
                return img_match.group(1)
        
        # Check summary for images
        summary = entry.get('summary', '')
        if summary:
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
            if img_match:
                return img_match.group(1)
        
        return ""

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
        article.image_url = self.extract_image_url(entry)
        
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

def main():
    """Main function to test RSS feeds"""
    reader = RSSFeedReader()
    
    # Process all feeds
    articles = reader.process_all_feeds('rsslist.txt')
    
    # Print summary
    reader.print_summary(articles)
    
    # Save to JSON
    reader.save_articles_to_json(articles, 'rss_articles.json')
    
    # Create RSS log
    reader.create_rss_log('rsslog.txt')
    
    # Show some sample articles
    if articles:
        print(f"\n{'='*60}")
        print(f"SAMPLE ARTICLES")
        print(f"{'='*60}")
        
        for i, article in enumerate(articles[:3], 1):
            print(f"\nArticle {i}:")
            print(f"Title: {article.title}")
            print(f"Source: {article.source_name}")
            print(f"Published: {article.published}")
            print(f"Description: {article.description[:200]}...")
            if article.image_url:
                print(f"Image: {article.image_url}")
            print(f"Link: {article.link}")

if __name__ == "__main__":
    main()
