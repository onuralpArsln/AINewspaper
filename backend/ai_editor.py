#!/usr/bin/env python3
"""
AI Editor for Article Evaluation
Uses Gemini AI to evaluate articles from our_articles.db according to editorial metrics

WORKFLOW:
1. Reads articles with state 'not_reviewed' from our_articles.db
2. Evaluates each article using metrics defined in editor_prompt.txt
3. Uses Gemini AI to analyze and score articles on 13 different metrics
4. Updates article status to 'accepted' or 'rejected' based on total score
5. Stores evaluation results as JSON in editors_note column
6. Increments review_count for each processed article

IMPORTANT: REVIEW_COUNT = number of articles to EVALUATE per run
Example: If REVIEW_COUNT=5, you review 5 articles from our_articles.db

USAGE:
    python ai_editor.py                    # Review REVIEW_COUNT articles
    python ai_editor.py --stats            # Show statistics only
    python ai_editor.py --our-db custom.db # Use custom database
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
# CONFIGURATION FLAGS - Modify these to control AI editor behavior
# ============================================================================
REVIEW_COUNT = 5   # Number of articles to review per run
# ============================================================================

class AIEditor:
    """AI-powered article editor using Gemini for evaluation"""
    
    def __init__(self, our_articles_db_path: str = 'our_articles.db'):
        # Resolve paths relative to script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.our_articles_db_path = our_articles_db_path if os.path.isabs(our_articles_db_path) else os.path.join(script_dir, our_articles_db_path)
        self.review_count = REVIEW_COUNT
        
        # Load environment variables
        load_dotenv()
        api_key = os.getenv("GEMINI_FREE_API")
        
        if not api_key:
            raise ValueError("GEMINI_FREE_API environment variable not found. Please set it in your .env file.")
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=api_key)
        
        # Load editor prompt
        self.editor_prompt = self._load_editor_prompt()
        
        # Initialize database
        self._init_database()
    
    def _load_editor_prompt(self) -> str:
        """Load the editor prompt from file"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            prompt_path = os.path.join(script_dir, 'editor_prompt.txt')
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error("editor_prompt.txt not found!")
            return "You are an AI editorial evaluation system. Evaluate the article and return a JSON object with evaluation metrics."
    
    def _init_database(self):
        """Initialize database connection and verify schema"""
        with sqlite3.connect(self.our_articles_db_path) as conn:
            cursor = conn.cursor()
            
            # Check if required columns exist
            cursor.execute("PRAGMA table_info(our_articles)")
            existing_columns = [column[1] for column in cursor.fetchall()]
            
            required_columns = ['article_state', 'editors_note', 'review_count']
            missing_columns = [col for col in required_columns if col not in existing_columns]
            
            if missing_columns:
                logger.warning(f"Missing required columns: {missing_columns}")
                logger.warning("Please ensure the database schema is up to date")
            
            # Add indexes for performance
            try:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_our_articles_state ON our_articles(article_state, updated_at)')
                conn.commit()
            except sqlite3.OperationalError as e:
                logger.debug(f"Index might already exist: {e}")
    
    def get_connection(self, db_path: str):
        """Get database connection with row factory"""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_articles_to_review(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get articles with 'not_reviewed' status for evaluation (max 48 hours old)"""
        with self.get_connection(self.our_articles_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM our_articles 
                WHERE article_state = 'not_reviewed' 
                    AND created_at >= datetime('now', '-48 hours')
                ORDER BY updated_at DESC 
                LIMIT ?
            ''', (limit,))
            
            articles = [dict(row) for row in cursor.fetchall()]
            logger.info(f"Found {len(articles)} articles to review (within 48 hours)")
            return articles
    
    def prepare_article_for_evaluation(self, article: Dict[str, Any]) -> str:
        """Prepare article content for AI evaluation by replacing placeholders in editor prompt"""
        try:
            # Replace placeholders in editor prompt with actual article content
            evaluation_prompt = self.editor_prompt.replace('{TITLE}', article.get('title', 'N/A'))
            evaluation_prompt = evaluation_prompt.replace('{SUMMARY}', article.get('summary', 'N/A'))
            evaluation_prompt = evaluation_prompt.replace('{ARTICLE_TEXT}', article.get('body', 'N/A'))
            
            return evaluation_prompt
            
        except Exception as e:
            logger.error(f"Error preparing article for evaluation: {e}")
            return self.editor_prompt
    
    def evaluate_article_with_ai(self, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Evaluate article using Gemini AI"""
        try:
            # Prepare the evaluation prompt
            evaluation_prompt = self.prepare_article_for_evaluation(article)
            
            logger.info(f"Sending article {article['id']} to Gemini AI for evaluation...")
            
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=evaluation_prompt,
            )
            
            # Parse the AI response
            return self._parse_evaluation_response(response.text)
            
        except Exception as e:
            logger.error(f"Error evaluating article with AI: {e}")
            return None
    
    def _parse_evaluation_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse AI evaluation response and extract JSON"""
        try:
            # Clean the response text
            response_text = response_text.strip()
            
            # Handle markdown code blocks
            if '```json' in response_text:
                # Extract JSON from markdown code block
                json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1).strip()
            elif '```' in response_text:
                # Extract from generic code block
                json_match = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1).strip()
            
            # Try to parse as JSON
            evaluation_data = json.loads(response_text)
            
            # Validate required fields
            required_fields = [
                'word_count', 'readability_atesman_score', 'avg_sentence_length',
                'summary_coverage_score', 'summary_length_ratio', 'title_relevance_score',
                'title_length', 'topic_coherence_score', 'clarity_score',
                'active_voice_ratio', 'fact_density', 'engagement_tone_score',
                'total_score', 'status'
            ]
            
            missing_fields = [field for field in required_fields if field not in evaluation_data]
            if missing_fields:
                logger.warning(f"Missing required fields in evaluation: {missing_fields}")
                return None
            
            # Validate status
            if evaluation_data['status'] not in ['accepted', 'rejected']:
                logger.warning(f"Invalid status: {evaluation_data['status']}")
                return None
            
            # Validate total_score is integer
            if not isinstance(evaluation_data['total_score'], int):
                try:
                    evaluation_data['total_score'] = int(evaluation_data['total_score'])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid total_score: {evaluation_data['total_score']}")
                    return None
            
            logger.info(f"Successfully parsed evaluation: status={evaluation_data['status']}, score={evaluation_data['total_score']}")
            return evaluation_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from AI response: {e}")
            logger.debug(f"Response text: {response_text[:500]}...")
            return None
        except Exception as e:
            logger.error(f"Error parsing evaluation response: {e}")
            return None
    
    def update_article_status(self, article_id: int, status: str, editors_note_json: str, total_score: int) -> bool:
        """Update article status and evaluation results in database"""
        try:
            # Use Istanbul time for consistency
            istanbul_time = (datetime.utcnow() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
            
            with self.get_connection(self.our_articles_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE our_articles 
                    SET article_state = ?, 
                        editors_note = ?, 
                        review_count = review_count + 1,
                        updated_at = ?
                    WHERE id = ?
                ''', (status, editors_note_json, istanbul_time, article_id))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"✓ Updated article {article_id}: status={status}, score={total_score}")
                    return True
                else:
                    logger.warning(f"No rows updated for article {article_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating article {article_id}: {e}")
            return False
    
    def process_reviews(self, max_reviews: int = None):
        """
        Main processing function that evaluates articles.
        For each article:
        1. Get next unreviewed article from our_articles database
        2. Send to Gemini AI for evaluation
        3. Parse evaluation results
        4. Update article status and store evaluation data
        5. Continue until max_reviews articles are processed
        """
        # Use class-level review_count if max_reviews not provided
        if max_reviews is None:
            max_reviews = self.review_count
        
        logger.info(f"Starting AI article evaluation process...")
        logger.info(f"Target: Review {max_reviews} articles")
        
        reviewed_count = 0
        accepted_count = 0
        rejected_count = 0
        error_count = 0
        
        # Keep processing until we review the target number of articles
        while reviewed_count < max_reviews:
            # Get next batch of articles to review
            batch_size = max(5, max_reviews - reviewed_count)
            articles_to_review = self.get_articles_to_review(batch_size)
            
            if not articles_to_review:
                logger.info(f"✓ No more unreviewed articles found (reviewed {reviewed_count} articles)")
                break
            
            # Process articles until we reach our target
            for article in articles_to_review:
                if reviewed_count >= max_reviews:
                    break
                
                try:
                    article_id = article['id']
                    article_title = article['title'][:60]
                    
                    logger.info(f"\n{'='*80}")
                    logger.info(f"Reviewing article {article_id}: {article_title}...")
                    logger.info(f"Review {reviewed_count + 1}/{max_reviews}")
                    
                    # Evaluate article with AI
                    evaluation_result = self.evaluate_article_with_ai(article)
                    
                    if evaluation_result:
                        # Update article status with evaluation results
                        status = evaluation_result['status']
                        total_score = evaluation_result['total_score']
                        editors_note_json = json.dumps(evaluation_result, ensure_ascii=False)
                        
                        if self.update_article_status(article_id, status, editors_note_json, total_score):
                            reviewed_count += 1
                            if status == 'accepted':
                                accepted_count += 1
                            else:
                                rejected_count += 1
                            
                            logger.info(f"✓ Successfully reviewed article {reviewed_count}/{max_reviews} (ID: {article_id})")
                            logger.info(f"  - Status: {status}, Score: {total_score}")
                        else:
                            error_count += 1
                            logger.error(f"✗ Failed to update article {article_id}")
                    else:
                        error_count += 1
                        logger.error(f"✗ Failed to evaluate article {article_id}")
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"✗ Error reviewing article {article.get('id', 'unknown')}: {e}")
                    continue
        
        logger.info(f"\n{'='*80}")
        logger.info(f"AI evaluation process completed!")
        logger.info(f"  ✓ Articles reviewed: {reviewed_count}/{max_reviews}")
        logger.info(f"  ✓ Accepted: {accepted_count}")
        logger.info(f"  ✗ Rejected: {rejected_count}")
        logger.info(f"  ✗ Errors: {error_count}")
        logger.info(f"{'='*80}\n")
    
    def get_review_statistics(self) -> Dict[str, Any]:
        """Get statistics about the review process"""
        with self.get_connection(self.our_articles_db_path) as conn:
            cursor = conn.cursor()
            
            # Total articles
            cursor.execute('SELECT COUNT(*) FROM our_articles')
            total_count = cursor.fetchone()[0]
            
            # Not reviewed (within 48 hours)
            cursor.execute("SELECT COUNT(*) FROM our_articles WHERE article_state = 'not_reviewed' AND created_at >= datetime('now', '-48 hours')")
            not_reviewed_count = cursor.fetchone()[0]
            
            # Accepted
            cursor.execute("SELECT COUNT(*) FROM our_articles WHERE article_state = 'accepted'")
            accepted_count = cursor.fetchone()[0]
            
            # Rejected
            cursor.execute("SELECT COUNT(*) FROM our_articles WHERE article_state = 'rejected'")
            rejected_count = cursor.fetchone()[0]
            
            # Average review count
            cursor.execute('SELECT AVG(review_count) FROM our_articles WHERE review_count > 0')
            avg_review_count = cursor.fetchone()[0] or 0
        
        return {
            'total_articles': total_count,
            'not_reviewed': not_reviewed_count,
            'accepted': accepted_count,
            'rejected': rejected_count,
            'reviewed': accepted_count + rejected_count,
            'review_percentage': round((accepted_count + rejected_count) / total_count * 100, 2) if total_count > 0 else 0,
            'acceptance_rate': round(accepted_count / (accepted_count + rejected_count) * 100, 2) if (accepted_count + rejected_count) > 0 else 0,
            'avg_review_count': round(avg_review_count, 2)
        }
    
    def print_statistics(self):
        """Print review statistics"""
        stats = self.get_review_statistics()
        
        print("=" * 80)
        print("AI EDITOR STATISTICS")
        print("=" * 80)
        print(f"Total articles: {stats['total_articles']:,}")
        print(f"Not reviewed (within 48h): {stats['not_reviewed']:,}")
        print(f"Reviewed: {stats['reviewed']:,}")
        print(f"  - Accepted: {stats['accepted']:,}")
        print(f"  - Rejected: {stats['rejected']:,}")
        print(f"Review percentage: {stats['review_percentage']}%")
        print(f"Acceptance rate: {stats['acceptance_rate']}%")
        print(f"Average review count: {stats['avg_review_count']}")
        print("=" * 80)

def run(our_db: str = 'our_articles.db', stats_only: bool = False) -> int:
    """Run AI editor process with optional parameters"""
    editor = AIEditor(our_db)
    
    if stats_only:
        editor.print_statistics()
        return 0
    
    print("\n" + "="*80)
    print("INITIAL DATABASE STATUS")
    print("="*80)
    editor.print_statistics()
    
    editor.process_reviews()
    
    print("\n" + "="*80)
    print("FINAL DATABASE STATUS")
    print("="*80)
    editor.print_statistics()
    
    return 0

def main():
    """Main function for command line usage"""
    parser = argparse.ArgumentParser(
        description="AI Editor for Article Evaluation - Reviews articles using Gemini AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Configuration Settings (edit in ai_editor.py):
  REVIEW_COUNT = {REVIEW_COUNT}   (Number of articles to REVIEW per run)

Examples:
  python ai_editor.py                    # Review {REVIEW_COUNT} articles
  python ai_editor.py --stats            # Show statistics only
  python ai_editor.py --our-db custom.db # Use custom database
        """
    )
    
    parser.add_argument('--stats', action='store_true',
                       help='Show statistics only without processing')
    parser.add_argument('--our-db', default='our_articles.db',
                       help='Our articles database path (default: our_articles.db)')
    
    args = parser.parse_args()
    
    try:
        editor = AIEditor(args.our_db)
        
        if args.stats:
            # Show statistics only
            editor.print_statistics()
        else:
            # Show initial statistics
            print("\n" + "="*80)
            print("INITIAL DATABASE STATUS")
            print("="*80)
            editor.print_statistics()
            
            # Process reviews
            print()
            editor.process_reviews()
            
            # Show final statistics
            print("\n" + "="*80)
            print("FINAL DATABASE STATUS")
            print("="*80)
            editor.print_statistics()
            
    except KeyboardInterrupt:
        logger.info("\n\nProcess interrupted by user.")
        return 1
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
