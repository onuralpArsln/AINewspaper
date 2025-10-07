#!/usr/bin/env python3
"""
AI Writer for RSS Articles
Uses Gemini AI to rewrite and unify articles from rss_articles.db

WORKFLOW:
1. Iterates through unread articles in rss_articles.db (newest first)
2. For each article:
   - Checks if it has images (if ONLY_IMAGES flag is True)
   - If article is in a group, reads ALL articles in that group
   - Sends article(s) to Gemini AI for professional rewriting
   - Follows rules from writer_prompt.txt
   - Generates: Title, Description, Body, Tags (categories + locations)
3. Saves to our_articles.db with:
   - Title, Description, Body, Tags
   - All image URLs from source articles (image_url, image_urls, media_content)
   - Source article IDs for reference
   - Publication date
4. Marks source articles as read (is_read = 1)

USAGE:
    python ai_writer.py                    # Process ARTICLE_COUNT articles
    python ai_writer.py --max-articles 20  # Process 20 articles
    python ai_writer.py --stats            # Show statistics only
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from google import genai
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION FLAGS - Modify these to control AI writer behavior
# ============================================================================
ONLY_IMAGES = False  # Set to True to only process articles with images
ARTICLE_COUNT = 10   # Number of articles to process per run
# ============================================================================

class AIWriter:
    """AI-powered article writer using Gemini"""
    
    def __init__(self, rss_db_path: str = 'rss_articles.db', our_articles_db_path: str = 'our_articles.db'):
        self.rss_db_path = rss_db_path
        self.our_articles_db_path = our_articles_db_path
        self.only_images = ONLY_IMAGES
        self.article_count = ARTICLE_COUNT
        
        # Load environment variables
        load_dotenv()
        api_key = os.getenv("GEMINI_FREE_API")
        
        if not api_key:
            raise ValueError("GEMINI_FREE_API environment variable not found. Please set it in your .env file.")
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=api_key)
        
        # Load writer prompt
        self.writer_prompt = self._load_writer_prompt()
        
        # Initialize databases
        self._init_databases()
    
    def _load_writer_prompt(self) -> str:
        """Load the writer prompt from file"""
        try:
            with open('writer_prompt.txt', 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error("writer_prompt.txt not found!")
            return "You are a seasoned journalist. Rewrite the given news articles in a professional tone."
    
    def _init_databases(self):
        """Initialize both databases with required schemas"""
        # Initialize RSS database with read status and event grouping
        with sqlite3.connect(self.rss_db_path) as conn:
            cursor = conn.cursor()
            # Add read status column if it doesn't exist
            try:
                cursor.execute('ALTER TABLE articles ADD COLUMN is_read BOOLEAN DEFAULT 0')
                logger.info("Added is_read column to RSS articles table")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Add event_group_id column if it doesn't exist
            try:
                cursor.execute('ALTER TABLE articles ADD COLUMN event_group_id INTEGER')
                logger.info("Added event_group_id column to RSS articles table")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Add indexes for performance
            try:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_read ON articles(is_read, created_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_group_read ON articles(event_group_id, is_read)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_group_id ON articles(event_group_id)')
            except sqlite3.OperationalError:
                pass
        
        # Initialize our articles database
        with sqlite3.connect(self.our_articles_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS our_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    body TEXT NOT NULL,
                    tags TEXT,
                    images TEXT,  -- JSON array of image URLs
                    date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    source_group_id INTEGER,  -- Reference to event group
                    source_article_ids TEXT,  -- JSON array of source article IDs
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Add indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_our_articles_date ON our_articles(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_our_articles_group ON our_articles(source_group_id)')
    
    def get_connection(self, db_path: str):
        """Get database connection with row factory"""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_next_articles_to_process(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get next unread articles to process starting from newest, considering only_images flag"""
        with self.get_connection(self.rss_db_path) as conn:
            cursor = conn.cursor()
            
            # Build query based on only_images flag
            if self.only_images:
                # Only get articles with images (image_url, image_urls, or media_content)
                cursor.execute('''
                    SELECT * FROM articles 
                    WHERE is_read = 0 
                        AND (
                            (image_url IS NOT NULL AND image_url != '') 
                            OR (image_urls IS NOT NULL AND image_urls != '[]' AND image_urls != 'null')
                            OR (media_content IS NOT NULL AND media_content != '[]' AND media_content != 'null')
                        )
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (limit,))
            else:
                # Get all unread articles regardless of images
                cursor.execute('''
                    SELECT * FROM articles 
                    WHERE is_read = 0
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (limit,))
            
            articles = [dict(row) for row in cursor.fetchall()]
            logger.info(f"Found {len(articles)} unread articles to process (only_images={self.only_images})")
            return articles
    
    def get_group_articles(self, group_id: int) -> List[Dict[str, Any]]:
        """Get all articles in a specific group (both read and unread)"""
        with self.get_connection(self.rss_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM articles 
                WHERE event_group_id = ?
                ORDER BY created_at DESC
            ''', (group_id,))
            group_articles = [dict(row) for row in cursor.fetchall()]
            logger.info(f"Found {len(group_articles)} articles in group {group_id}")
            return group_articles
    
    def group_has_images(self, group_id: int) -> bool:
        """Check if at least one article in the group has images"""
        with self.get_connection(self.rss_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM articles 
                WHERE event_group_id = ? 
                    AND is_read = 0
                    AND (image_url IS NOT NULL AND image_url != '' 
                         OR image_urls IS NOT NULL AND image_urls != '[]')
            ''', (group_id,))
            count = cursor.fetchone()[0]
            return count > 0
    
    def _collect_images_from_articles(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Collect all unique images from source articles (image_url, image_urls, media_content)"""
        all_images = []
        
        for article in articles:
            # 1. Check image_url (primary image)
            if article.get('image_url') and article['image_url'].strip():
                if article['image_url'] not in all_images:
                    all_images.append(article['image_url'])
            
            # 2. Check image_urls (JSON array of all images)
            if article.get('image_urls'):
                try:
                    image_urls = json.loads(article['image_urls'])
                    if isinstance(image_urls, list):
                        for img_url in image_urls:
                            if img_url and img_url.strip() and img_url not in all_images:
                                all_images.append(img_url)
                except (json.JSONDecodeError, TypeError):
                    logger.debug(f"Could not parse image_urls for article {article.get('id', 'unknown')}")
            
            # 3. Check media_content (JSON array with media information)
            if article.get('media_content'):
                try:
                    media_content = json.loads(article['media_content'])
                    if isinstance(media_content, list):
                        for media in media_content:
                            if isinstance(media, dict) and media.get('url'):
                                img_url = media['url']
                                if img_url and img_url.strip() and img_url not in all_images:
                                    all_images.append(img_url)
                except (json.JSONDecodeError, TypeError):
                    logger.debug(f"Could not parse media_content for article {article.get('id', 'unknown')}")
        
        logger.info(f"Collected {len(all_images)} unique images from {len(articles)} articles")
        return all_images
    
    def prepare_articles_for_ai(self, articles: List[Dict[str, Any]]) -> str:
        """Prepare articles text for AI processing"""
        if not articles:
            return ""
        
        if len(articles) == 1:
            # Single article
            article = articles[0]
            return f"""
Article Title: {article.get('title', 'N/A')}
Source: {article.get('source_name', 'N/A')}
Published: {article.get('published', 'N/A')}
Content: {article.get('description', article.get('content', 'N/A'))}
Link: {article.get('link', 'N/A')}
"""
        else:
            # Multiple articles (group)
            text = f"Multiple articles about the same event (Group ID: {articles[0]['event_group_id']}):\n\n"
            for i, article in enumerate(articles, 1):
                text += f"Article {i}:\n"
                text += f"Title: {article.get('title', 'N/A')}\n"
                text += f"Source: {article.get('source_name', 'N/A')}\n"
                text += f"Published: {article.get('published', 'N/A')}\n"
                text += f"Content: {article.get('description', article.get('content', 'N/A'))}\n"
                text += f"Link: {article.get('link', 'N/A')}\n\n"
            return text
    
    def generate_article_with_ai(self, articles_text: str) -> Optional[Dict[str, str]]:
        """Generate article using Gemini AI with enhanced prompt for tags"""
        try:
            # Enhanced prompt to specifically request tags with categories and locations
            enhanced_prompt = f"""{self.writer_prompt}

IMPORTANT: Generate tags in the following format:
- Include article category (e.g., sports, science, technology, politics, economy, health, etc.)
- Include geographic location (city or country mentioned in the article)
- Include other relevant keywords
- Separate tags with commas
- Example: "sports, Istanbul, football, championship"

Please rewrite the following articles:

{articles_text}"""
            
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=enhanced_prompt,
            )
            
            # Parse the AI response
            return self._parse_ai_response(response.text)
            
        except Exception as e:
            logger.error(f"Error generating article with AI: {e}")
            return None
    
    def _parse_ai_response(self, response_text: str) -> Optional[Dict[str, str]]:
        """Parse AI response into structured format"""
        try:
            lines = response_text.strip().split('\n')
            article_data = {}
            
            current_section = None
            current_content = []
            
            for line in lines:
                line = line.strip()
                if line.startswith('Title:'):
                    if current_section and current_content:
                        article_data[current_section] = '\n'.join(current_content).strip()
                    current_section = 'title'
                    current_content = [line.replace('Title:', '').strip()]
                elif line.startswith('Description:'):
                    if current_section and current_content:
                        article_data[current_section] = '\n'.join(current_content).strip()
                    current_section = 'description'
                    current_content = [line.replace('Description:', '').strip()]
                elif line.startswith('Body:'):
                    if current_section and current_content:
                        article_data[current_section] = '\n'.join(current_content).strip()
                    current_section = 'body'
                    current_content = [line.replace('Body:', '').strip()]
                elif line.startswith('Tags:'):
                    if current_section and current_content:
                        article_data[current_section] = '\n'.join(current_content).strip()
                    current_section = 'tags'
                    current_content = [line.replace('Tags:', '').strip()]
                elif line and current_section:
                    current_content.append(line)
            
            # Add the last section
            if current_section and current_content:
                article_data[current_section] = '\n'.join(current_content).strip()
            
            # Validate required fields
            if 'title' in article_data and 'body' in article_data:
                return article_data
            else:
                logger.warning(f"AI response missing required fields: {list(article_data.keys())}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return None
    
    def save_article(self, article_data: Dict[str, str], source_articles: List[Dict[str, Any]]) -> int:
        """Save generated article to our_articles database with all metadata"""
        with self.get_connection(self.our_articles_db_path) as conn:
            cursor = conn.cursor()
            
            # Prepare source tracking data
            source_group_id = source_articles[0].get('event_group_id') if source_articles[0].get('event_group_id') else None
            source_article_ids = [str(article['id']) for article in source_articles]
            source_ids_str = ','.join(source_article_ids)
            
            # Get publication date from the earliest article
            pub_date = None
            for article in sorted(source_articles, key=lambda x: x.get('published', '') or '', reverse=True):
                if article.get('published'):
                    pub_date = article['published']
                    break
            
            # Collect all images from source articles (from all three image columns)
            all_images = self._collect_images_from_articles(source_articles)
            images_json = json.dumps(all_images) if all_images else None
            
            # Extract data from AI response
            title = article_data.get('title', '')
            description = article_data.get('description', '')
            body = article_data.get('body', '')
            tags = article_data.get('tags', '')
            
            # Insert into our_articles
            cursor.execute('''
                INSERT INTO our_articles 
                (title, description, body, tags, images, date, source_group_id, source_article_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                title,
                description,
                body,
                tags,
                images_json,
                pub_date,
                source_group_id,
                source_ids_str
            ))
            
            article_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"✓ Saved article ID {article_id}: '{title[:50]}...'")
            logger.info(f"  - Images: {len(all_images)}, Tags: {tags}, Source IDs: {source_ids_str}")
            
            return article_id
    
    def mark_articles_as_read(self, articles: List[Dict[str, Any]]):
        """Mark articles as read in RSS database"""
        if not articles:
            return
        
        article_ids = [article['id'] for article in articles]
        
        with self.get_connection(self.rss_db_path) as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in article_ids])
            cursor.execute(f'''
                UPDATE articles 
                SET is_read = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
            ''', article_ids)
            conn.commit()
            
            logger.info(f"Marked {len(article_ids)} articles as read")
    
    def process_articles(self, max_articles: int = None):
        """
        Main processing function that iterates through unread articles starting from newest.
        For each article:
        1. Check if it has images (if only_images flag is True)
        2. Check if it's part of a group - if yes, read all articles in the group
        3. Send to Gemini AI for rewriting
        4. Save to our_articles.db with title, description, body, tags, and images
        5. Mark source articles as read
        """
        # Use class-level article_count if max_articles not provided
        if max_articles is None:
            max_articles = self.article_count
        
        mode_str = "ONLY IMAGES mode" if self.only_images else "ALL ARTICLES mode"
        logger.info(f"Starting AI article writing process ({mode_str})...")
        logger.info(f"Processing up to {max_articles} articles")
        
        # Get unread articles starting from newest
        articles_to_process = self.get_next_articles_to_process(max_articles)
        
        if not articles_to_process:
            logger.info("✓ No unread articles found to process")
            return
        
        processed_count = 0
        skipped_count = 0
        
        for article in articles_to_process:
            try:
                article_id = article['id']
                article_title = article['title'][:60]
                
                logger.info(f"\n{'='*80}")
                logger.info(f"Processing article {article_id}: {article_title}...")
                
                # Check if article is part of a group
                group_id = article.get('event_group_id')
                
                if group_id and group_id > 0:
                    # Article is part of a group - get ALL articles in the group
                    logger.info(f"Article is part of group {group_id}")
                    source_articles = self.get_group_articles(group_id)
                    logger.info(f"Processing {len(source_articles)} articles from group {group_id}")
                else:
                    # Individual article (not in a group)
                    logger.info("Processing individual article (not in a group)")
                    source_articles = [article]
                
                # Prepare text for AI
                articles_text = self.prepare_articles_for_ai(source_articles)
                
                # Generate article with AI
                logger.info("Sending to Gemini AI for rewriting...")
                ai_article = self.generate_article_with_ai(articles_text)
                
                if ai_article:
                    # Save generated article with all images and metadata
                    saved_id = self.save_article(ai_article, source_articles)
                    
                    # Mark source articles as read
                    self.mark_articles_as_read(source_articles)
                    
                    processed_count += 1
                    logger.info(f"✓ Successfully processed and saved article {saved_id}")
                else:
                    logger.error("✗ Failed to generate article with AI")
                    skipped_count += 1
                    
            except Exception as e:
                logger.error(f"✗ Error processing article {article.get('id', 'unknown')}: {e}")
                skipped_count += 1
                continue
        
        logger.info(f"\n{'='*80}")
        logger.info(f"AI writing process completed!")
        logger.info(f"  ✓ Successfully processed: {processed_count} articles")
        logger.info(f"  ✗ Skipped/Failed: {skipped_count} articles")
        logger.info(f"{'='*80}\n")
    
    def get_writing_statistics(self) -> Dict[str, Any]:
        """Get statistics about the writing process"""
        with self.get_connection(self.rss_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM articles WHERE is_read = 1')
            read_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM articles')
            total_count = cursor.fetchone()[0]
        
        with self.get_connection(self.our_articles_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM our_articles')
            our_articles_count = cursor.fetchone()[0]
        
        return {
            'total_rss_articles': total_count,
            'read_rss_articles': read_count,
            'unread_rss_articles': total_count - read_count,
            'our_articles_count': our_articles_count,
            'processing_percentage': round((read_count / total_count * 100), 2) if total_count > 0 else 0
        }
    
    def print_statistics(self):
        """Print writing statistics"""
        stats = self.get_writing_statistics()
        
        print("=" * 80)
        print("AI WRITER STATISTICS")
        print("=" * 80)
        print(f"Total RSS articles: {stats['total_rss_articles']:,}")
        print(f"Read articles: {stats['read_rss_articles']:,}")
        print(f"Unread articles: {stats['unread_rss_articles']:,}")
        print(f"Our generated articles: {stats['our_articles_count']:,}")
        print(f"Processing percentage: {stats['processing_percentage']}%")
        print("=" * 80)

def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="AI Writer for RSS Articles - Rewrites news using Gemini AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Configuration Settings (edit in ai_writer.py):
  ONLY_IMAGES   = {ONLY_IMAGES}   (Process only articles with images)
  ARTICLE_COUNT = {ARTICLE_COUNT}   (Number of articles to process per run)

Examples:
  python ai_writer.py                    # Process {ARTICLE_COUNT} articles
  python ai_writer.py --max-articles 20  # Process 20 articles
  python ai_writer.py --stats            # Show statistics only
        """
    )
    
    parser.add_argument('--max-articles', type=int, 
                       help=f'Override ARTICLE_COUNT setting (default: {ARTICLE_COUNT})')
    parser.add_argument('--stats', action='store_true',
                       help='Show statistics only without processing')
    parser.add_argument('--rss-db', default='rss_articles.db',
                       help='RSS articles database path (default: rss_articles.db)')
    parser.add_argument('--our-db', default='our_articles.db',
                       help='Our articles database path (default: our_articles.db)')
    
    args = parser.parse_args()
    
    try:
        writer = AIWriter(args.rss_db, args.our_db)
        
        if args.stats:
            # Show statistics only
            writer.print_statistics()
        else:
            # Show initial statistics
            print("\n" + "="*80)
            print("INITIAL DATABASE STATUS")
            print("="*80)
            writer.print_statistics()
            
            # Process articles
            print()
            writer.process_articles(args.max_articles)
            
            # Show final statistics
            print("\n" + "="*80)
            print("FINAL DATABASE STATUS")
            print("="*80)
            writer.print_statistics()
            
    except KeyboardInterrupt:
        logger.info("\n\nProcess interrupted by user.")
        return 1
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
