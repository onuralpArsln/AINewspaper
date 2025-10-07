#!/usr/bin/env python3
"""
Article Similarity Detection Module
Detects similar news articles from different sources using various text similarity algorithms
"""

import re
import math
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Set, Optional
from collections import defaultdict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ArticleSimilarityDetector:
    """Detects similar articles using multiple text similarity algorithms"""
    
    def __init__(self, db_path: str = 'rss_articles.db'):
        self.db_path = db_path
        
        # Turkish stop words for better similarity detection
        self.turkish_stop_words = {
            've', 'bir', 'bu', 'da', 'de', 'için', 'olan', 'ile', 'gibi', 'çok', 
            'daha', 'en', 'şu', 'o', 'ben', 'sen', 'biz', 'siz', 'onlar', 'ki',
            'mi', 'mı', 'mu', 'mü', 'ne', 'nasıl', 'niçin', 'neden', 'hangi',
            'kim', 'kime', 'kimin', 'kimde', 'kimden', 'kimi', 'kimle', 'kiminle',
            'nere', 'nerede', 'nereden', 'nereye', 'ne', 'nasıl', 'ne zaman',
            'ama', 'ancak', 'fakat', 'lakin', 'yoksa', 'ya da', 'veya', 'hem',
            'gerek', 'hem de', 'sadece', 'yalnız', 'sadece', 'bile', 'dahi',
            'için', 'göre', 'karşı', 'doğru', 'kadar', 'sonra', 'önce', 'önceki',
            'sonraki', 'beri', 'den', 'dan', 'e', 'a', 'i', 'u', 'ü', 'ı', 'ö',
            'var', 'yok', 'olmak', 'etmek', 'yapmak', 'gelmek', 'gitmek',
            'almak', 'vermek', 'görmek', 'bilmek', 'demek', 'söylemek'
        }
    
    def get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def preprocess_text(self, text: str) -> str:
        """Preprocess text for better similarity detection"""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters but keep Turkish characters
        text = re.sub(r'[^\w\sçğıöşüâêîôû]', ' ', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def extract_keywords(self, text: str, min_length: int = 3) -> Set[str]:
        """Extract keywords from text, removing stop words"""
        if not text:
            return set()
        
        text = self.preprocess_text(text)
        words = text.split()
        
        # Filter out stop words and short words
        keywords = {
            word for word in words 
            if len(word) >= min_length and word not in self.turkish_stop_words
        }
        
        return keywords
    
    def jaccard_similarity(self, set1: Set[str], set2: Set[str]) -> float:
        """Calculate Jaccard similarity between two sets"""
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def cosine_similarity(self, set1: Set[str], set2: Set[str]) -> float:
        """Calculate cosine similarity between two sets of keywords"""
        if not set1 or not set2:
            return 0.0
        
        intersection = set1.intersection(set2)
        if not intersection:
            return 0.0
        
        # Simple cosine similarity for sets
        return len(intersection) / (math.sqrt(len(set1)) * math.sqrt(len(set2)))
    
    def title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two article titles"""
        if not title1 or not title2:
            return 0.0
        
        # Extract keywords from titles
        keywords1 = self.extract_keywords(title1)
        keywords2 = self.extract_keywords(title2)
        
        # Calculate both Jaccard and cosine similarity
        jaccard_sim = self.jaccard_similarity(keywords1, keywords2)
        cosine_sim = self.cosine_similarity(keywords1, keywords2)
        
        # Use the maximum of both similarities
        return max(jaccard_sim, cosine_sim)
    
    def content_similarity(self, content1: str, content2: str, max_length: int = 1000) -> float:
        """Calculate similarity between article content/description"""
        if not content1 or not content2:
            return 0.0
        
        # Limit content length for performance
        content1 = content1[:max_length] if content1 else ""
        content2 = content2[:max_length] if content2 else ""
        
        keywords1 = self.extract_keywords(content1)
        keywords2 = self.extract_keywords(content2)
        
        # Use Jaccard similarity for content
        return self.jaccard_similarity(keywords1, keywords2)
    
    def overall_similarity(self, article1: Dict, article2: Dict) -> float:
        """Calculate overall similarity between two articles"""
        title_sim = self.title_similarity(article1.get('title', ''), article2.get('title', ''))
        
        # Get content from description or content field
        content1 = article1.get('description', '') or article1.get('content', '') or article1.get('summary', '')
        content2 = article2.get('description', '') or article2.get('content', '') or article2.get('summary', '')
        content_sim = self.content_similarity(content1, content2)
        
        # Weighted combination: title similarity is more important
        overall_sim = (title_sim * 0.7) + (content_sim * 0.3)
        
        return overall_sim
    
    def are_articles_similar(self, article1: Dict, article2: Dict, 
                           similarity_threshold: float = 0.3, 
                           max_time_diff_days: int = 2) -> bool:
        """Check if two articles are similar enough to be grouped"""
        # Skip if same article
        if article1['id'] == article2['id']:
            return False
        
        # Skip if same source (we want to group articles from different sources)
        if article1.get('source_name') == article2.get('source_name'):
            return False
        
        # Check temporal proximity - articles must be published within max_time_diff_days
        if not self.are_articles_temporally_close(article1, article2, max_time_diff_days):
            return False
        
        # Calculate overall similarity
        similarity = self.overall_similarity(article1, article2)
        
        return similarity >= similarity_threshold
    
    def are_articles_temporally_close(self, article1: Dict, article2: Dict, 
                                    max_days: int = 2) -> bool:
        """Check if two articles are published within the specified time period"""
        try:
            # Get published dates
            pub1 = article1.get('published')
            pub2 = article2.get('published')
            
            # If either article doesn't have a published date, use created_at
            if not pub1:
                pub1 = article1.get('created_at')
            if not pub2:
                pub2 = article2.get('created_at')
            
            # If still no dates, skip temporal check (allow grouping)
            if not pub1 or not pub2:
                logger.warning(f"Missing publication dates for articles {article1['id']} and {article2['id']}")
                return True
            
            # Parse dates
            if isinstance(pub1, str):
                pub1 = datetime.fromisoformat(pub1.replace('Z', '+00:00'))
            if isinstance(pub2, str):
                pub2 = datetime.fromisoformat(pub2.replace('Z', '+00:00'))
            
            # Convert to naive datetime for comparison if needed
            if pub1.tzinfo is not None and pub2.tzinfo is None:
                pub2 = pub2.replace(tzinfo=pub1.tzinfo)
            elif pub2.tzinfo is not None and pub1.tzinfo is None:
                pub1 = pub1.replace(tzinfo=pub2.tzinfo)
            elif pub1.tzinfo is not None and pub2.tzinfo is not None:
                # Both have timezone info, convert to UTC for comparison
                pub1 = pub1.astimezone().replace(tzinfo=None)
                pub2 = pub2.astimezone().replace(tzinfo=None)
            
            # Calculate time difference
            time_diff = abs((pub1 - pub2).days)
            
            # Check if within the allowed time period
            is_close = time_diff <= max_days
            
            if not is_close:
                logger.debug(f"Articles {article1['id']} and {article2['id']} too far apart: {time_diff} days")
            
            return is_close
            
        except Exception as e:
            logger.error(f"Error checking temporal proximity: {e}")
            # If there's an error, allow grouping (don't block due to date parsing issues)
            return True
    
    def get_articles_for_grouping(self, days_back: int = 7, limit: int = 1000) -> List[Dict]:
        """Get articles that need to be grouped (recent articles without group_id)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get recent articles that don't have event_group_id assigned
                cursor.execute('''
                    SELECT id, title, description, content, summary, source_name, 
                           published, created_at
                    FROM articles 
                    WHERE (event_group_id IS NULL OR event_group_id = 0)
                    AND created_at >= datetime('now', '-{} days')
                    ORDER BY created_at DESC
                    LIMIT ?
                '''.format(days_back), (limit,))
                
                articles = []
                for row in cursor.fetchall():
                    articles.append(dict(row))
                
                logger.info(f"Found {len(articles)} articles for similarity grouping")
                return articles
                
        except Exception as e:
            logger.error(f"Error getting articles for grouping: {e}")
            return []
    
    def find_similar_articles(self, target_article: Dict, candidate_articles: List[Dict],
                            similarity_threshold: float = 0.3, max_time_diff_days: int = 2) -> List[Dict]:
        """Find articles similar to the target article"""
        similar_articles = []
        
        for candidate in candidate_articles:
            if self.are_articles_similar(target_article, candidate, similarity_threshold, max_time_diff_days):
                similarity = self.overall_similarity(target_article, candidate)
                candidate['similarity_score'] = similarity
                similar_articles.append(candidate)
        
        # Sort by similarity score (highest first)
        similar_articles.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        return similar_articles
    
    def create_event_group(self, articles: List[Dict]) -> int:
        """Create a new event group and assign group ID to articles"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get the next available group ID
                cursor.execute('SELECT COALESCE(MAX(event_group_id), 0) + 1 FROM articles')
                group_id = cursor.fetchone()[0]
                
                # Update all articles with the new group ID
                article_ids = [str(article['id']) for article in articles]
                placeholders = ','.join(['?' for _ in article_ids])
                
                cursor.execute(f'''
                    UPDATE articles 
                    SET event_group_id = ? 
                    WHERE id IN ({placeholders})
                ''', [group_id] + article_ids)
                
                conn.commit()
                
                logger.info(f"Created event group {group_id} with {len(articles)} articles")
                return group_id
                
        except Exception as e:
            logger.error(f"Error creating event group: {e}")
            return 0
    
    def group_similar_articles(self, similarity_threshold: float = 0.3,
                             days_back: int = 7, min_group_size: int = 2, 
                             max_time_diff_days: int = 2) -> Dict[str, int]:
        """Group similar articles and assign event group IDs"""
        logger.info("Starting article similarity grouping...")
        
        stats = {
            'articles_processed': 0,
            'groups_created': 0,
            'articles_grouped': 0,
            'processing_time': 0
        }
        
        start_time = datetime.now()
        
        try:
            # Get articles that need grouping
            articles = self.get_articles_for_grouping(days_back)
            stats['articles_processed'] = len(articles)
            
            if not articles:
                logger.info("No articles found for grouping")
                return stats
            
            processed_articles = set()
            group_count = 0
            
            for i, article in enumerate(articles):
                if article['id'] in processed_articles:
                    continue
                
                logger.info(f"Processing article {i+1}/{len(articles)}: {article['title'][:50]}...")
                
                # Find similar articles
                similar_articles = self.find_similar_articles(
                    article, articles[i+1:], similarity_threshold, max_time_diff_days
                )
                
                # Create group if we found similar articles
                if len(similar_articles) >= min_group_size - 1:  # -1 because we include the target article
                    group_articles = [article] + similar_articles
                    
                    # Create event group
                    group_id = self.create_event_group(group_articles)
                    
                    if group_id > 0:
                        group_count += 1
                        stats['articles_grouped'] += len(group_articles)
                        
                        # Mark articles as processed
                        for art in group_articles:
                            processed_articles.add(art['id'])
                        
                        logger.info(f"Created group {group_id} with {len(group_articles)} articles")
                        for art in group_articles:
                            logger.info(f"  - {art['title'][:60]}... (Source: {art['source_name']})")
                    else:
                        # If group creation failed, mark only the target article as processed
                        processed_articles.add(article['id'])
                else:
                    # No similar articles found, mark as processed
                    processed_articles.add(article['id'])
            
            stats['groups_created'] = group_count
            
        except Exception as e:
            logger.error(f"Error in article grouping: {e}")
        
        finally:
            stats['processing_time'] = (datetime.now() - start_time).total_seconds()
        
        logger.info("Article similarity grouping completed!")
        return stats
    
    def get_grouped_articles(self, group_id: int) -> List[Dict]:
        """Get all articles in a specific event group"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, title, description, source_name, published, created_at, link
                    FROM articles 
                    WHERE event_group_id = ?
                    ORDER BY created_at DESC
                ''', (group_id,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting grouped articles: {e}")
            return []
    
    def get_all_groups(self, limit: int = 50) -> List[Dict]:
        """Get all event groups with their articles"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT event_group_id, COUNT(*) as article_count,
                           MIN(created_at) as first_article,
                           MAX(created_at) as last_article
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
                
        except Exception as e:
            logger.error(f"Error getting all groups: {e}")
            return []

def main():
    """Main function for testing similarity detection"""
    detector = ArticleSimilarityDetector()
    
    print("=" * 80)
    print("ARTICLE SIMILARITY DETECTION AND GROUPING")
    print("=" * 80)
    
    # Run similarity grouping
    stats = detector.group_similar_articles(
        similarity_threshold=0.3,
        days_back=7,
        min_group_size=2
    )
    
    print(f"\nGrouping Results:")
    print(f"  Articles processed: {stats['articles_processed']}")
    print(f"  Groups created: {stats['groups_created']}")
    print(f"  Articles grouped: {stats['articles_grouped']}")
    print(f"  Processing time: {stats['processing_time']:.2f} seconds")
    
    # Show some groups
    groups = detector.get_all_groups(5)
    if groups:
        print(f"\nTop 5 Event Groups:")
        print("-" * 60)
        
        for i, group in enumerate(groups, 1):
            print(f"\nGroup {group['event_group_id']} ({group['article_count']} articles):")
            for article in group['articles'][:3]:  # Show first 3 articles
                print(f"  - {article['title'][:60]}... (Source: {article['source_name']})")
            if len(group['articles']) > 3:
                print(f"  ... and {len(group['articles']) - 3} more articles")

if __name__ == "__main__":
    main()
