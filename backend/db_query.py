#!/usr/bin/env python3
"""
Database Query Script for RSS Articles
Simple script to query and display articles from the RSS database
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

class RSSDatabaseQuery:
    """Simple database query interface for RSS articles"""
    
    def __init__(self, db_path: str = 'rss_articles.db'):
        # Resolve paths relative to script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = db_path if os.path.isabs(db_path) else os.path.join(script_dir, db_path)
    
    def get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_total_articles(self) -> int:
        """Get total number of articles"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM articles')
            return cursor.fetchone()[0]
    
    def get_articles_by_source(self) -> Dict[str, int]:
        """Get article count by source"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT source_name, COUNT(*) as count 
                FROM articles 
                GROUP BY source_name 
                ORDER BY count DESC
            ''')
            return {row['source_name']: row['count'] for row in cursor.fetchall()}
    
    def get_recent_articles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent articles"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT title, source_name, published, created_at, link
                FROM articles 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_articles_by_date_range(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get articles from the last N days"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT title, source_name, published, created_at, link
                FROM articles 
                WHERE created_at >= datetime('now', '-{} days')
                ORDER BY created_at DESC
            '''.format(days))
            return [dict(row) for row in cursor.fetchall()]
    
    def search_articles(self, search_term: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search articles by title or content"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT title, source_name, published, created_at, link, description
                FROM articles 
                WHERE title LIKE ? OR description LIKE ? OR content LIKE ?
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_feed_statistics(self) -> List[Dict[str, Any]]:
        """Get feed processing statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT feed_url, last_processed, last_article_count, 
                       total_articles, status, error_message
                FROM feed_stats 
                ORDER BY last_processed DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_articles_by_source_detail(self, source_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get articles from a specific source"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT title, published, created_at, link, description, event_group_id
                FROM articles 
                WHERE source_name = ?
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (source_name, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_grouped_articles(self, group_id: int) -> List[Dict[str, Any]]:
        """Get all articles in a specific event group"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, description, source_name, published, created_at, link, event_group_id
                FROM articles 
                WHERE event_group_id = ?
                ORDER BY created_at DESC
            ''', (group_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_event_groups(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all event groups with their articles"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT event_group_id, COUNT(*) as article_count,
                       MIN(created_at) as first_article,
                       MAX(created_at) as last_article,
                       GROUP_CONCAT(DISTINCT source_name) as sources
                FROM articles 
                WHERE event_group_id IS NOT NULL AND event_group_id > 0
                GROUP BY event_group_id
                ORDER BY COUNT(*) DESC, MAX(created_at) DESC
                LIMIT ?
            ''', (limit,))
            
            groups = []
            for row in cursor.fetchall():
                group_info = dict(row)
                group_info['articles'] = self.get_grouped_articles(row['event_group_id'])
                groups.append(group_info)
            
            return groups
    
    def get_ungrouped_articles(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get articles that are not yet grouped"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, description, source_name, published, created_at, link, event_group_id
                FROM articles 
                WHERE event_group_id IS NULL OR event_group_id = 0
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def search_groups(self, search_term: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for event groups containing specific terms"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT event_group_id, COUNT(*) as article_count,
                       MIN(created_at) as first_article,
                       MAX(created_at) as last_article,
                       GROUP_CONCAT(DISTINCT source_name) as sources
                FROM articles 
                WHERE event_group_id IS NOT NULL 
                AND event_group_id > 0
                AND (title LIKE ? OR description LIKE ? OR content LIKE ?)
                GROUP BY event_group_id
                ORDER BY article_count DESC, MAX(created_at) DESC
                LIMIT ?
            ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', limit))
            
            groups = []
            for row in cursor.fetchall():
                group_info = dict(row)
                group_info['articles'] = self.get_grouped_articles(row['event_group_id'])
                groups.append(group_info)
            
            return groups
    
    def get_grouping_statistics(self) -> Dict[str, Any]:
        """Get statistics about article grouping"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total articles
            cursor.execute('SELECT COUNT(*) FROM articles')
            total_articles = cursor.fetchone()[0]
            
            # Grouped articles
            cursor.execute('''
                SELECT COUNT(*) FROM articles 
                WHERE event_group_id IS NOT NULL AND event_group_id > 0
            ''')
            grouped_articles = cursor.fetchone()[0]
            
            # Number of groups
            cursor.execute('''
                SELECT COUNT(DISTINCT event_group_id) FROM articles 
                WHERE event_group_id IS NOT NULL AND event_group_id > 0
            ''')
            total_groups = cursor.fetchone()[0]
            
            # Average group size
            cursor.execute('''
                SELECT AVG(group_size) FROM (
                    SELECT COUNT(*) as group_size
                    FROM articles 
                    WHERE event_group_id IS NOT NULL AND event_group_id > 0
                    GROUP BY event_group_id
                )
            ''')
            avg_group_size = cursor.fetchone()[0] or 0
            
            return {
                'total_articles': total_articles,
                'grouped_articles': grouped_articles,
                'ungrouped_articles': total_articles - grouped_articles,
                'total_groups': total_groups,
                'average_group_size': round(avg_group_size, 2),
                'grouping_percentage': round((grouped_articles / total_articles * 100), 2) if total_articles > 0 else 0
            }
    
    def get_unread_articles(self, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Get unread articles"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, description, source_name, published, created_at, link, event_group_id
                FROM articles 
                WHERE is_read = 0 OR is_read IS NULL
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_read_articles(self, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Get read articles"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, description, source_name, published, created_at, link, event_group_id
                FROM articles 
                WHERE is_read = 1
                ORDER BY updated_at DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_unread_count(self) -> int:
        """Get count of unread articles"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM articles WHERE is_read = 0 OR is_read IS NULL')
            return cursor.fetchone()[0]
    
    def get_read_count(self) -> int:
        """Get count of read articles"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM articles WHERE is_read = 1')
            return cursor.fetchone()[0]
    
    def mark_article_as_read(self, article_id: int) -> bool:
        """Mark an article as read"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE articles 
                SET is_read = 1, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (article_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def mark_article_as_unread(self, article_id: int) -> bool:
        """Mark an article as unread"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE articles 
                SET is_read = 0, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (article_id,))
            conn.commit()
            return cursor.rowcount > 0

def print_database_summary():
    """Print comprehensive database summary"""
    db = RSSDatabaseQuery()
    
    print("=" * 80)
    print("RSS ARTICLES DATABASE SUMMARY")
    print("=" * 80)
    
    # Total articles
    total = db.get_total_articles()
    print(f"Total articles in database: {total:,}")
    
    # Read/Unread statistics
    unread_count = db.get_unread_count()
    read_count = db.get_read_count()
    print(f"\nRead Status Statistics:")
    print("-" * 40)
    print(f"Unread articles: {unread_count:,}")
    print(f"Read articles: {read_count:,}")
    if total > 0:
        print(f"Unread percentage: {(unread_count / total * 100):.1f}%")
    
    # Articles by source
    print(f"\nArticles by source:")
    print("-" * 40)
    sources = db.get_articles_by_source()
    for source, count in list(sources.items())[:10]:  # Top 10
        print(f"{source}: {count:,} articles")
    
    # Grouping statistics
    print(f"\nArticle Grouping Statistics:")
    print("-" * 40)
    grouping_stats = db.get_grouping_statistics()
    print(f"Grouped articles: {grouping_stats['grouped_articles']:,}")
    print(f"Ungrouped articles: {grouping_stats['ungrouped_articles']:,}")
    print(f"Total event groups: {grouping_stats['total_groups']}")
    print(f"Average group size: {grouping_stats['average_group_size']} articles")
    print(f"Grouping coverage: {grouping_stats['grouping_percentage']}%")
    
    # Recent articles
    print(f"\nRecent articles (last 5):")
    print("-" * 40)
    recent = db.get_recent_articles(5)
    for i, article in enumerate(recent, 1):
        print(f"{i}. {article['title'][:60]}...")
        print(f"   Source: {article['source_name']}")
        print(f"   Added: {article['created_at']}")
        if article.get('event_group_id'):
            print(f"   Event Group: {article['event_group_id']}")
        print()
    
    # Recent event groups
    if grouping_stats['total_groups'] > 0:
        print(f"\nRecent event groups (top 3):")
        print("-" * 40)
        groups = db.get_all_event_groups(3)
        for i, group in enumerate(groups, 1):
            print(f"{i}. Group {group['event_group_id']} ({group['article_count']} articles)")
            print(f"   Sources: {group['sources']}")
            print(f"   First article: {group['first_article']}")
            print(f"   Last article: {group['last_article']}")
            print()
    
    # Feed statistics
    print(f"Feed processing statistics:")
    print("-" * 40)
    feed_stats = db.get_feed_statistics()
    for stat in feed_stats[:5]:  # Top 5
        print(f"Feed: {stat['feed_url']}")
        print(f"  Last processed: {stat['last_processed']}")
        print(f"  Articles in last run: {stat['last_article_count']}")
        print(f"  Total articles: {stat['total_articles']}")
        print(f"  Status: {stat['status']}")
        print()

def search_articles_interactive():
    """Interactive article search"""
    db = RSSDatabaseQuery()
    
    print("=" * 80)
    print("ARTICLE SEARCH")
    print("=" * 80)
    
    while True:
        search_term = input("\nEnter search term (or 'quit' to exit): ").strip()
        if search_term.lower() == 'quit':
            break
        
        if not search_term:
            continue
        
        results = db.search_articles(search_term, 10)
        
        if not results:
            print("No articles found.")
            continue
        
        print(f"\nFound {len(results)} articles:")
        print("-" * 40)
        
        for i, article in enumerate(results, 1):
            print(f"{i}. {article['title']}")
            print(f"   Source: {article['source_name']}")
            print(f"   Published: {article['published'] or 'N/A'}")
            print(f"   Link: {article['link']}")
            if article['description']:
                print(f"   Description: {article['description'][:100]}...")
            print()

class OurArticlesDatabaseQuery:
    """Database query interface for our generated articles"""
    
    def __init__(self, db_path: str = 'our_articles.db'):
        # Resolve paths relative to script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = db_path if os.path.isabs(db_path) else os.path.join(script_dir, db_path)
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create our_articles table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS our_articles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        summary TEXT,
                        body TEXT NOT NULL,
                        category TEXT,  -- Main category (one of: gündem,ekonomi,spor,siyaset,magazin,yaşam,eğitim,sağlık,astroloji)
                        tags TEXT,  -- JSON array of additional tags
                        images TEXT,  -- JSON array of image URLs
                        date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        source_group_id INTEGER,  -- Reference to event group
                        source_article_ids TEXT,  -- JSON array of source article IDs
                        article_state TEXT DEFAULT 'not_reviewed',  -- Review status: not_reviewed, accepted, rejected
                        review_count INTEGER DEFAULT 0,  -- Number of times article has been reviewed
                        editors_note TEXT,  -- JSON review data from editor AI (nullable)
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Add indexes for performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_our_articles_state ON our_articles(article_state, updated_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_our_articles_created ON our_articles(created_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_our_articles_category ON our_articles(category)')
                
                conn.commit()
                print(f"Our articles database initialized successfully: {self.db_path}")
                
        except Exception as e:
            print(f"Error initializing our articles database: {e}")
            raise
    
    def get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_total_articles(self) -> int:
        """Get total number of our articles"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM our_articles')
            return cursor.fetchone()[0]
    
    def get_recent_articles(self, limit: int = 10, offset: int = 0, editor_mode: bool = False) -> List[Dict[str, Any]]:
        """Get recent articles ordered by updated_at (within 48 hours of creation)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if editor_mode:
                cursor.execute('''
                    SELECT id, title, summary, body, category, tags, images, date, 
                           source_group_id, source_article_ids, created_at, updated_at
                    FROM our_articles 
                    WHERE article_state = 'accepted'
                        AND created_at >= datetime('now', '-48 hours')
                    ORDER BY updated_at DESC 
                    LIMIT ? OFFSET ?
                ''', (limit, offset))
            else:
                cursor.execute('''
                    SELECT id, title, summary, body, category, tags, images, date, 
                           source_group_id, source_article_ids, created_at, updated_at
                    FROM our_articles 
                    WHERE created_at >= datetime('now', '-48 hours')
                    ORDER BY updated_at DESC 
                    LIMIT ? OFFSET ?
                ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_article_by_id(self, article_id: int, editor_mode: bool = False) -> Dict[str, Any]:
        """Get a specific article by ID (within 48 hours of creation)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if editor_mode:
                cursor.execute('''
                    SELECT id, title, summary, body, category, tags, images, date,
                           source_group_id, source_article_ids, created_at, updated_at
                    FROM our_articles 
                    WHERE id = ? AND article_state = 'accepted'
                        AND created_at >= datetime('now', '-48 hours')
                ''', (article_id,))
            else:
                cursor.execute('''
                    SELECT id, title, summary, body, category, tags, images, date,
                           source_group_id, source_article_ids, created_at, updated_at
                    FROM our_articles 
                    WHERE id = ? AND created_at >= datetime('now', '-48 hours')
                ''', (article_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def get_articles_by_category(self, category: str, limit: int = 20, editor_mode: bool = False) -> List[Dict[str, Any]]:
        """Get articles by category (within 48 hours of creation)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if editor_mode:
                cursor.execute('''
                    SELECT id, title, summary, body, category, tags, images, date,
                           source_group_id, source_article_ids, created_at, updated_at
                    FROM our_articles 
                    WHERE category = ? AND article_state = 'accepted'
                        AND created_at >= datetime('now', '-48 hours')
                    ORDER BY updated_at DESC 
                    LIMIT ?
                ''', (category, limit))
            else:
                cursor.execute('''
                    SELECT id, title, summary, body, category, tags, images, date,
                           source_group_id, source_article_ids, created_at, updated_at
                    FROM our_articles 
                    WHERE category = ? AND created_at >= datetime('now', '-48 hours')
                    ORDER BY updated_at DESC 
                    LIMIT ?
                ''', (category, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_articles_by_tag(self, tag: str, limit: int = 20, editor_mode: bool = False) -> List[Dict[str, Any]]:
        """Get articles by tag (searches in JSON tags array, within 48 hours of creation)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if editor_mode:
                cursor.execute('''
                    SELECT id, title, summary, body, category, tags, images, date,
                           source_group_id, source_article_ids, created_at, updated_at
                    FROM our_articles 
                    WHERE tags LIKE ? AND article_state = 'accepted'
                        AND created_at >= datetime('now', '-48 hours')
                    ORDER BY updated_at DESC 
                    LIMIT ?
                ''', (f'%{tag}%', limit))
            else:
                cursor.execute('''
                    SELECT id, title, summary, body, category, tags, images, date,
                           source_group_id, source_article_ids, created_at, updated_at
                    FROM our_articles 
                    WHERE tags LIKE ? AND created_at >= datetime('now', '-48 hours')
                    ORDER BY updated_at DESC 
                    LIMIT ?
                ''', (f'%{tag}%', limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def search_articles(self, search_term: str, limit: int = 20, editor_mode: bool = False) -> List[Dict[str, Any]]:
        """Search articles by title, summary, or body (within 48 hours of creation)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if editor_mode:
                cursor.execute('''
                    SELECT id, title, summary, body, category, tags, images, date,
                           source_group_id, source_article_ids, created_at, updated_at
                    FROM our_articles 
                    WHERE (title LIKE ? OR summary LIKE ? OR body LIKE ?) AND article_state = 'accepted'
                        AND created_at >= datetime('now', '-48 hours')
                    ORDER BY updated_at DESC 
                    LIMIT ?
                ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', limit))
            else:
                cursor.execute('''
                    SELECT id, title, summary, body, category, tags, images, date,
                           source_group_id, source_article_ids, created_at, updated_at
                    FROM our_articles 
                    WHERE (title LIKE ? OR summary LIKE ? OR body LIKE ?)
                        AND created_at >= datetime('now', '-48 hours')
                    ORDER BY updated_at DESC 
                    LIMIT ?
                ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_articles_with_images(self, limit: int = 10, offset: int = 0, editor_mode: bool = False) -> List[Dict[str, Any]]:
        """Get articles that have images (within 48 hours of creation)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if editor_mode:
                cursor.execute('''
                    SELECT id, title, summary, body, category, tags, images, date,
                           source_group_id, source_article_ids, created_at, updated_at
                    FROM our_articles 
                    WHERE images IS NOT NULL AND images != '[]' AND images != 'null' 
                        AND article_state = 'accepted'
                        AND created_at >= datetime('now', '-48 hours')
                    ORDER BY updated_at DESC 
                    LIMIT ? OFFSET ?
                ''', (limit, offset))
            else:
                cursor.execute('''
                    SELECT id, title, summary, body, category, tags, images, date,
                           source_group_id, source_article_ids, created_at, updated_at
                    FROM our_articles 
                    WHERE images IS NOT NULL AND images != '[]' AND images != 'null'
                        AND created_at >= datetime('now', '-48 hours')
                    ORDER BY updated_at DESC 
                    LIMIT ? OFFSET ?
                ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_statistics(self, editor_mode: bool = False) -> Dict[str, Any]:
        """Get statistics about our articles (within 48 hours of creation)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if editor_mode:
                # Total accepted articles within 48 hours
                cursor.execute('''
                    SELECT COUNT(*) FROM our_articles 
                    WHERE article_state = 'accepted' AND created_at >= datetime('now', '-48 hours')
                ''')
                total_count = cursor.fetchone()[0]
                
                # Accepted articles with images within 48 hours
                cursor.execute('''
                    SELECT COUNT(*) FROM our_articles 
                    WHERE images IS NOT NULL AND images != '[]' AND images != 'null' 
                        AND article_state = 'accepted' AND created_at >= datetime('now', '-48 hours')
                ''')
                with_images = cursor.fetchone()[0]
                
                # Oldest and newest accepted articles within 48 hours
                cursor.execute('''
                    SELECT MIN(date), MAX(date) FROM our_articles 
                    WHERE article_state = 'accepted' AND created_at >= datetime('now', '-48 hours')
                ''')
                oldest, newest = cursor.fetchone()
            else:
                # Total articles within 48 hours
                cursor.execute('''
                    SELECT COUNT(*) FROM our_articles 
                    WHERE created_at >= datetime('now', '-48 hours')
                ''')
                total_count = cursor.fetchone()[0]
                
                # Articles with images within 48 hours
                cursor.execute('''
                    SELECT COUNT(*) FROM our_articles 
                    WHERE images IS NOT NULL AND images != '[]' AND images != 'null'
                        AND created_at >= datetime('now', '-48 hours')
                ''')
                with_images = cursor.fetchone()[0]
                
                # Oldest and newest articles within 48 hours
                cursor.execute('''
                    SELECT MIN(date), MAX(date) FROM our_articles 
                    WHERE created_at >= datetime('now', '-48 hours')
                ''')
                oldest, newest = cursor.fetchone()
            
            return {
                'total_articles': total_count,
                'articles_with_images': with_images,
                'articles_without_images': total_count - with_images,
                'oldest_article': oldest,
                'newest_article': newest,
                'filter_note': 'Statistics show only articles created within the last 48 hours'
            }
    
    def engage_killswitch(self) -> int:
        """Replace all article content with error message"""
        error_text = "hata"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE our_articles 
                SET title = ?, summary = ?, body = ?, updated_at = CURRENT_TIMESTAMP
            ''', (error_text, error_text, error_text))
            conn.commit()
            return cursor.rowcount

def main():
    """Main function"""
    print_database_summary()
    
    # Ask if user wants to search
    response = input("\nWould you like to search for articles? (y/n): ").strip().lower()
    if response == 'y':
        search_articles_interactive()

if __name__ == "__main__":
    main()
