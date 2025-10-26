#!/usr/bin/env python3
"""
AI Rewriter for Rejected Articles
Uses Gemini AI to enhance rejected articles from our_articles.db based on editorial feedback

WORKFLOW:
1. Reads articles with state 'rejected' and review_count < MAX_REVIEW_COUNT from our_articles.db
2. Fetches source articles from the event group using source_group_id
3. Analyzes editor's JSON feedback with specific metric scores and suggestions
4. Uses Gemini AI to enhance the article addressing failing metrics
5. Updates article with enhanced content and sets status to 'not_reviewed'
6. Updates updated_at timestamp for re-evaluation by ai_editor.py

IMPORTANT: MAX_REVIEW_COUNT = maximum reviews before article can't be rewritten
Example: If MAX_REVIEW_COUNT=3, articles with review_count >= 3 are skipped

USAGE:
    python ai_rewriter.py                    # Rewrite REWRITE_BATCH_SIZE articles
    python ai_rewriter.py --max-rewrites 5   # Rewrite 5 articles
    python ai_rewriter.py --stats            # Show statistics only
"""

import os
import sqlite3
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from google import genai
import logging
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION FLAGS - Modify these to control AI rewriter behavior
# ============================================================================
MAX_REVIEW_COUNT = 3   # Maximum reviews before article can't be rewritten
REWRITE_BATCH_SIZE = 2  # Number of articles to rewrite per run
# ============================================================================

class AIRewriter:
    """AI-powered article rewriter using Gemini for enhancing rejected articles"""
    
    def __init__(self, our_articles_db_path: str = 'our_articles.db', rss_db_path: str = 'rss_articles.db'):
        # Resolve paths relative to script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.our_articles_db_path = our_articles_db_path if os.path.isabs(our_articles_db_path) else os.path.join(script_dir, our_articles_db_path)
        self.rss_db_path = rss_db_path if os.path.isabs(rss_db_path) else os.path.join(script_dir, rss_db_path)
        self.max_review_count = MAX_REVIEW_COUNT
        self.rewrite_batch_size = REWRITE_BATCH_SIZE
        
        # Load environment variables
        load_dotenv()
        api_key = os.getenv("GEMINI_FREE_API")
        
        if not api_key:
            raise ValueError("GEMINI_FREE_API environment variable not found. Please set it in your .env file.")
        
        # Initialize separate Gemini client for isolation
        self.client = genai.Client(api_key=api_key)
        
        # Load rewriter prompt
        self.rewriter_prompt = self._load_rewriter_prompt()
        
        # Initialize databases
        self._init_databases()
    
    def _load_rewriter_prompt(self) -> str:
        """Load the rewriter prompt from file"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            prompt_path = os.path.join(script_dir, 'rewriter_prompt.txt')
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error("rewriter_prompt.txt not found!")
            return "You are an AI article enhancement specialist. Enhance the rejected article based on editorial feedback."
    
    def _init_databases(self):
        """Initialize database connections and verify schemas"""
        # Verify our_articles database has required columns
        with sqlite3.connect(self.our_articles_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(our_articles)")
            existing_columns = [column[1] for column in cursor.fetchall()]
            
            required_columns = ['article_state', 'editors_note', 'review_count', 'source_group_id', 'source_article_ids']
            missing_columns = [col for col in required_columns if col not in existing_columns]
            
            if missing_columns:
                logger.warning(f"Missing required columns in our_articles: {missing_columns}")
                logger.warning("Please ensure the database schema is up to date")
            
            # Add indexes for performance
            try:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_our_articles_rejected ON our_articles(article_state, review_count, updated_at)')
                conn.commit()
            except sqlite3.OperationalError as e:
                logger.debug(f"Index might already exist: {e}")
        
        # Verify rss_articles database
        with sqlite3.connect(self.rss_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(articles)")
            existing_columns = [column[1] for column in cursor.fetchall()]
            
            if 'event_group_id' not in existing_columns:
                logger.warning("event_group_id column not found in rss_articles table")
    
    def get_connection(self, db_path: str):
        """Get database connection with row factory"""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_rejected_articles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get rejected articles eligible for rewriting (review_count < MAX_REVIEW_COUNT, max 48 hours old)"""
        with self.get_connection(self.our_articles_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM our_articles 
                WHERE article_state = 'rejected' 
                    AND review_count < ?
                    AND created_at >= datetime('now', '-48 hours')
                ORDER BY updated_at DESC 
                LIMIT ?
            ''', (self.max_review_count, limit))
            
            articles = [dict(row) for row in cursor.fetchall()]
            logger.info(f"Found {len(articles)} rejected articles eligible for rewriting (review_count < {self.max_review_count}, within 48 hours)")
            return articles
    
    def get_source_articles(self, article: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all source articles from the event group"""
        source_group_id = article.get('source_group_id')
        
        if not source_group_id:
            logger.warning(f"Article {article.get('id')} has no source_group_id")
            return []
        
        with self.get_connection(self.rss_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM articles 
                WHERE event_group_id = ?
                ORDER BY created_at DESC
            ''', (source_group_id,))
            
            source_articles = [dict(row) for row in cursor.fetchall()]
            logger.info(f"Found {len(source_articles)} source articles for group {source_group_id}")
            return source_articles
    
    def prepare_rewriter_prompt(self, article: Dict[str, Any], editors_note: Dict[str, Any], source_articles: List[Dict[str, Any]]) -> str:
        """Prepare comprehensive prompt for AI rewriter"""
        try:
            # Start with base rewriter prompt
            prompt = self.rewriter_prompt
            
            # Add original article information
            prompt += f"""

ORIGINAL REJECTED ARTICLE:
Title: {article.get('title', 'N/A')}
Summary: {article.get('summary', 'N/A')}
Body: {article.get('body', 'N/A')}
Category: {article.get('category', 'N/A')}
Tags: {article.get('tags', 'N/A')}

EDITORIAL FEEDBACK ANALYSIS:
The article was rejected with the following detailed evaluation:
{json.dumps(editors_note, indent=2, ensure_ascii=False)}

"""
            
            # Add source articles information
            if source_articles:
                prompt += f"SOURCE ARTICLES (Event Group {article.get('source_group_id')}):\n\n"
                for i, source_article in enumerate(source_articles, 1):
                    prompt += f"SOURCE ARTICLE {i} (ID: {source_article.get('id', 'N/A')}):\n"
                    prompt += f"Title: {source_article.get('title', 'N/A')}\n"
                    prompt += f"Source: {source_article.get('source_name', 'N/A')}\n"
                    prompt += f"Published: {source_article.get('published', 'N/A')}\n"
                    prompt += f"Content: {source_article.get('description', source_article.get('content', 'N/A'))}\n"
                    prompt += f"Link: {source_article.get('link', 'N/A')}\n\n"
            else:
                prompt += "WARNING: No source articles found for this event group.\n\n"
            
            prompt += """
IMPORTANT: Use ONLY the information provided in the source articles above. Do not add any facts, details, or information not explicitly stated in these source articles. Address each failing metric from the editorial feedback with specific improvements.

Please enhance the rejected article to address the editorial concerns while maintaining factual accuracy.
"""
            
            return prompt
            
        except Exception as e:
            logger.error(f"Error preparing rewriter prompt: {e}")
            return self.rewriter_prompt
    
    def enhance_article_with_ai(self, prompt: str) -> Optional[Dict[str, str]]:
        """Enhance article using Gemini AI"""
        try:
            logger.info("Sending article to Gemini AI for enhancement...")
            
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            
            # Parse the AI response
            return self._parse_enhanced_response(response.text)
            
        except Exception as e:
            logger.error(f"Error enhancing article with AI: {e}")
            return None
    
    def _parse_enhanced_response(self, response_text: str) -> Optional[Dict[str, str]]:
        """Parse AI enhancement response into structured format"""
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
                elif line.startswith('Summary:'):
                    if current_section and current_content:
                        article_data[current_section] = '\n'.join(current_content).strip()
                    current_section = 'summary'
                    current_content = [line.replace('Summary:', '').strip()]
                elif line.startswith('Body:'):
                    if current_section and current_content:
                        article_data[current_section] = '\n'.join(current_content).strip()
                    current_section = 'body'
                    current_content = [line.replace('Body:', '').strip()]
                elif line.startswith('Category:'):
                    if current_section and current_content:
                        article_data[current_section] = '\n'.join(current_content).strip()
                    current_section = 'category'
                    current_content = [line.replace('Category:', '').strip()]
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
            
            # Process tags - convert to JSON array if needed
            if 'tags' in article_data:
                tags_text = article_data['tags']
                try:
                    # Try to parse as JSON first
                    tags_json = json.loads(tags_text)
                    if isinstance(tags_json, list):
                        article_data['tags'] = json.dumps(tags_json, ensure_ascii=False)
                    else:
                        # Convert single string to array
                        article_data['tags'] = json.dumps([tags_json], ensure_ascii=False)
                except (json.JSONDecodeError, TypeError):
                    # Parse comma-separated tags
                    tags_list = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
                    article_data['tags'] = json.dumps(tags_list, ensure_ascii=False)
            
            # Validate required fields
            if 'title' in article_data and 'body' in article_data:
                return article_data
            else:
                logger.warning(f"AI response missing required fields: {list(article_data.keys())}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing AI enhancement response: {e}")
            return None
    
    def update_article(self, article_id: int, enhanced_data: Dict[str, str]) -> bool:
        """Update article with enhanced content and reset status to not_reviewed"""
        try:
            # Use Istanbul time for consistency
            istanbul_time = (datetime.utcnow() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
            
            with self.get_connection(self.our_articles_db_path) as conn:
                cursor = conn.cursor()
                
                # Extract data from enhanced response
                title = enhanced_data.get('title', '')
                summary = enhanced_data.get('summary', '')
                body = enhanced_data.get('body', '')
                category = enhanced_data.get('category', 'gündem')
                tags = enhanced_data.get('tags', '[]')
                
                cursor.execute('''
                    UPDATE our_articles 
                    SET title = ?, 
                        summary = ?, 
                        body = ?, 
                        category = ?, 
                        tags = ?,
                        article_state = 'not_reviewed',
                        updated_at = ?
                    WHERE id = ?
                ''', (title, summary, body, category, tags, istanbul_time, article_id))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"✓ Updated article {article_id}: status=not_reviewed, enhanced content saved")
                    return True
                else:
                    logger.warning(f"No rows updated for article {article_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating article {article_id}: {e}")
            return False
    
    def process_rewrites(self, max_rewrites: int = None):
        """
        Main processing function that enhances rejected articles.
        For each article:
        1. Get next rejected article eligible for rewriting
        2. Fetch source articles from event group
        3. Parse editor's feedback JSON
        4. Send to Gemini AI for enhancement
        5. Update article with enhanced content and reset status
        6. Continue until max_rewrites articles are processed
        """
        # Use class-level rewrite_batch_size if max_rewrites not provided
        if max_rewrites is None:
            max_rewrites = self.rewrite_batch_size
        
        logger.info(f"Starting AI article rewriting process...")
        logger.info(f"Target: Enhance {max_rewrites} rejected articles")
        logger.info(f"Max review count threshold: {self.max_review_count}")
        
        enhanced_count = 0
        skipped_count = 0
        error_count = 0
        
        # Keep processing until we enhance the target number of articles
        while enhanced_count < max_rewrites:
            # Get next batch of articles to rewrite
            batch_size = max(5, max_rewrites - enhanced_count)
            articles_to_rewrite = self.get_rejected_articles(batch_size)
            
            if not articles_to_rewrite:
                logger.info(f"✓ No more rejected articles eligible for rewriting (enhanced {enhanced_count} articles)")
                break
            
            # Process articles until we reach our target
            for article in articles_to_rewrite:
                if enhanced_count >= max_rewrites:
                    break
                
                try:
                    article_id = article['id']
                    article_title = article['title'][:60]
                    
                    logger.info(f"\n{'='*80}")
                    logger.info(f"Enhancing article {article_id}: {article_title}...")
                    logger.info(f"Enhancement {enhanced_count + 1}/{max_rewrites}")
                    logger.info(f"Review count: {article.get('review_count', 0)}/{self.max_review_count}")
                    
                    # Parse editor's note JSON
                    editors_note = {}
                    if article.get('editors_note'):
                        try:
                            editors_note = json.loads(article['editors_note'])
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.error(f"Failed to parse editors_note for article {article_id}: {e}")
                            error_count += 1
                            continue
                    
                    # Get source articles
                    source_articles = self.get_source_articles(article)
                    
                    # Prepare rewriter prompt
                    prompt = self.prepare_rewriter_prompt(article, editors_note, source_articles)
                    
                    # Enhance article with AI
                    enhanced_data = self.enhance_article_with_ai(prompt)
                    
                    if enhanced_data:
                        # Update article with enhanced content
                        if self.update_article(article_id, enhanced_data):
                            enhanced_count += 1
                            logger.info(f"✓ Successfully enhanced article {enhanced_count}/{max_rewrites} (ID: {article_id})")
                        else:
                            error_count += 1
                            logger.error(f"✗ Failed to update article {article_id}")
                    else:
                        error_count += 1
                        logger.error(f"✗ Failed to enhance article {article_id}")
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"✗ Error processing article {article.get('id', 'unknown')}: {e}")
                    continue
        
        logger.info(f"\n{'='*80}")
        logger.info(f"AI rewriting process completed!")
        logger.info(f"  ✓ Articles enhanced: {enhanced_count}/{max_rewrites}")
        logger.info(f"  ✗ Errors: {error_count}")
        logger.info(f"  📊 Skipped: {skipped_count}")
        logger.info(f"{'='*80}\n")
    
    def get_rewrite_statistics(self) -> Dict[str, Any]:
        """Get statistics about the rewriting process"""
        with self.get_connection(self.our_articles_db_path) as conn:
            cursor = conn.cursor()
            
            # Total articles
            cursor.execute('SELECT COUNT(*) FROM our_articles')
            total_count = cursor.fetchone()[0]
            
            # Rejected articles
            cursor.execute("SELECT COUNT(*) FROM our_articles WHERE article_state = 'rejected'")
            rejected_count = cursor.fetchone()[0]
            
            # Rejected articles eligible for rewriting (within 48 hours)
            cursor.execute('''
                SELECT COUNT(*) FROM our_articles 
                WHERE article_state = 'rejected' 
                    AND review_count < ?
                    AND created_at >= datetime('now', '-48 hours')
            ''', (self.max_review_count,))
            eligible_count = cursor.fetchone()[0]
            
            # Not reviewed articles
            cursor.execute("SELECT COUNT(*) FROM our_articles WHERE article_state = 'not_reviewed'")
            not_reviewed_count = cursor.fetchone()[0]
            
            # Accepted articles
            cursor.execute("SELECT COUNT(*) FROM our_articles WHERE article_state = 'accepted'")
            accepted_count = cursor.fetchone()[0]
            
            # Average review count for rejected articles
            cursor.execute('''
                SELECT AVG(review_count) FROM our_articles 
                WHERE article_state = 'rejected' AND review_count > 0
            ''')
            avg_review_count = cursor.fetchone()[0] or 0
        
        return {
            'total_articles': total_count,
            'rejected_articles': rejected_count,
            'eligible_for_rewrite': eligible_count,
            'not_reviewed': not_reviewed_count,
            'accepted': accepted_count,
            'avg_review_count_rejected': round(avg_review_count, 2),
            'max_review_count': self.max_review_count
        }
    
    def print_statistics(self):
        """Print rewriting statistics"""
        stats = self.get_rewrite_statistics()
        
        print("=" * 80)
        print("AI REWRITER STATISTICS")
        print("=" * 80)
        print(f"Total articles: {stats['total_articles']:,}")
        print(f"Rejected articles: {stats['rejected_articles']:,}")
        print(f"  - Eligible for rewrite (within 48h): {stats['eligible_for_rewrite']:,}")
        print(f"  - Max review count: {stats['max_review_count']}")
        print(f"Not reviewed: {stats['not_reviewed']:,}")
        print(f"Accepted: {stats['accepted']:,}")
        print(f"Average review count (rejected): {stats['avg_review_count_rejected']}")
        print("=" * 80)

def run(max_rewrites: int = None, our_db: str = 'our_articles.db', 
        rss_db: str = 'rss_articles.db', stats_only: bool = False) -> int:
    """Run AI rewriter process with optional parameters"""
    if max_rewrites is None:
        max_rewrites = REWRITE_BATCH_SIZE
    
    rewriter = AIRewriter(our_db, rss_db)
    
    if stats_only:
        rewriter.print_statistics()
        return 0
    
    print("\n" + "="*80)
    print("INITIAL DATABASE STATUS")
    print("="*80)
    rewriter.print_statistics()
    
    rewriter.process_rewrites(max_rewrites)
    
    print("\n" + "="*80)
    print("FINAL DATABASE STATUS")
    print("="*80)
    rewriter.print_statistics()
    
    return 0

def main():
    """Main function for command line usage"""
    parser = argparse.ArgumentParser(
        description="AI Rewriter for Rejected Articles - Enhances articles using Gemini AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Configuration Settings (edit in ai_rewriter.py):
  MAX_REVIEW_COUNT   = {MAX_REVIEW_COUNT}   (Maximum reviews before article can't be rewritten)
  REWRITE_BATCH_SIZE = {REWRITE_BATCH_SIZE}   (Number of articles to rewrite per run)

Examples:
  python ai_rewriter.py                    # Rewrite {REWRITE_BATCH_SIZE} articles
  python ai_rewriter.py --max-rewrites 5   # Rewrite 5 articles
  python ai_rewriter.py --stats            # Show statistics only
        """
    )
    
    parser.add_argument('--max-rewrites', type=int, 
                       help=f'Number of articles to rewrite (default: {REWRITE_BATCH_SIZE})')
    parser.add_argument('--stats', action='store_true',
                       help='Show statistics only without processing')
    parser.add_argument('--our-db', default='our_articles.db',
                       help='Our articles database path (default: our_articles.db)')
    parser.add_argument('--rss-db', default='rss_articles.db',
                       help='RSS articles database path (default: rss_articles.db)')
    
    args = parser.parse_args()
    
    try:
        rewriter = AIRewriter(args.our_db, args.rss_db)
        
        if args.stats:
            # Show statistics only
            rewriter.print_statistics()
        else:
            # Show initial statistics
            print("\n" + "="*80)
            print("INITIAL DATABASE STATUS")
            print("="*80)
            rewriter.print_statistics()
            
            # Process rewrites
            print()
            rewriter.process_rewrites(args.max_rewrites)
            
            # Show final statistics
            print("\n" + "="*80)
            print("FINAL DATABASE STATUS")
            print("="*80)
            rewriter.print_statistics()
            
    except KeyboardInterrupt:
        logger.info("\n\nProcess interrupted by user.")
        return 1
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
