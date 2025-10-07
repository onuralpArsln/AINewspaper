#!/usr/bin/env python3
"""
RSS to Database Module
Stores RSS articles in database with duplicate prevention
"""

import sqlite3
import hashlib
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
import logging
from pathlib import Path

# Import our RSS classes
from rsstester import RSSFeedReader, RSSArticle

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RSSDatabase:
    """Database handler for RSS articles with duplicate prevention"""
    
    def __init__(self, db_path: str = 'rss_articles.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create articles table
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
                        image_url TEXT,  -- Primary image (backward compatibility)
                        image_urls TEXT,  -- JSON array of all image URLs
                        source_name TEXT,
                        source_url TEXT,
                        feed_url TEXT,
                        language TEXT,
                        rights TEXT,
                        content_hash TEXT UNIQUE,  -- For duplicate detection
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create indexes for better performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_guid ON articles(guid)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_link ON articles(link)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON articles(content_hash)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_published ON articles(published)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_source_name ON articles(source_name)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON articles(created_at)')
                
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
                
                # Check if image_urls column exists, if not add it (migration)
                cursor.execute("PRAGMA table_info(articles)")
                columns = [column[1] for column in cursor.fetchall()]
                if 'image_urls' not in columns:
                    cursor.execute('ALTER TABLE articles ADD COLUMN image_urls TEXT')
                    logger.info("Added image_urls column to articles table")
                
                conn.commit()
                logger.info(f"Database initialized successfully: {self.db_path}")
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
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
        """Insert article into database if it doesn't exist"""
        try:
            if self.article_exists(article):
                logger.debug(f"Article already exists, skipping: {article.title[:50]}...")
                return False
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                content_hash = self.generate_content_hash(article)
                
                cursor.execute('''
                    INSERT INTO articles (
                        title, description, content, summary, link, guid, comments,
                        published, updated, author, category, tags, enclosures,
                        media_content, image_url, image_urls, source_name, source_url, feed_url,
                        language, rights, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    article.image_url,
                    json.dumps(article.image_urls) if article.image_urls else None,
                    article.source_name,
                    article.source_url,
                    article.feed_url,
                    article.language,
                    article.rights,
                    content_hash
                ))
                
                conn.commit()
                logger.debug(f"Article inserted: {article.title[:50]}...")
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

class RSSToDatabase:
    """Main class for processing RSS feeds and storing in database"""
    
    def __init__(self, db_path: str = 'rss_articles.db'):
        self.db = RSSDatabase(db_path)
        self.rss_reader = RSSFeedReader()
    
    def process_feeds_to_database(self, rss_list_file: str = 'rsslist.txt') -> Dict[str, Any]:
        """Process all RSS feeds and store articles in database"""
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
        """Print processing summary"""
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
    
    def get_database_summary(self) -> Dict[str, Any]:
        """Get comprehensive database summary"""
        return {
            'total_articles': self.db.get_article_count(),
            'articles_by_source': self.db.get_articles_by_source(),
            'recent_articles': self.db.get_recent_articles(5),
            'feed_stats': self.db.get_feed_stats()
        }

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

if __name__ == "__main__":
    main()
