#!/usr/bin/env python3
"""
Image Data Migration Script
Consolidates scattered image URLs from old database schema into unified image_urls column
Run this script to migrate existing databases to the new consolidated image structure
"""

import sqlite3
import json
import re
import logging
from typing import List, Set
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ImageMigrator:
    """Migrates image data from old scattered structure to consolidated image_urls column"""
    
    def __init__(self, db_path: str = 'rss_articles.db'):
        self.db_path = db_path
    
    def _extract_images_from_html(self, html_content: str) -> Set[str]:
        """Extract all image URLs from HTML content"""
        if not html_content:
            return set()
        
        image_urls = set()
        
        # Comprehensive image patterns
        patterns = [
            r'<img[^>]+src=["\']([^"\']+)["\']',
            r'<img[^>]+data-src=["\']([^"\']+)["\']',
            r'<img[^>]+data-lazy=["\']([^"\']+)["\']',
            r'<img[^>]+data-original=["\']([^"\']+)["\']',
            r'background-image:\s*url\(["\']?([^"\'()]+)["\']?\)',
            r'<figure[^>]*>.*?<img[^>]+src=["\']([^"\']+)["\']',
            r'srcset=["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                if 'srcset' in pattern:
                    urls = re.findall(r'(https?://[^\s,]+)', match)
                    image_urls.update(urls)
                else:
                    cleaned_url = self._clean_image_url(match)
                    if cleaned_url:
                        image_urls.add(cleaned_url)
        
        return image_urls
    
    def _clean_image_url(self, url: str) -> str:
        """Clean and normalize image URL"""
        if not url:
            return ""
        
        import html as html_lib
        url = html_lib.unescape(url)
        url = re.sub(r'&amp;', '&', url)
        url = url.strip()
        
        if not (url.startswith('http://') or url.startswith('https://')):
            return ""
        
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return ""
        except:
            return ""
        
        # Filter out tracking pixels
        if any(x in url.lower() for x in ['1x1', 'pixel', 'tracking', 'beacon']):
            return ""
        
        return url
    
    def _validate_and_filter_urls(self, urls: List[str]) -> List[str]:
        """Validate and filter image URLs"""
        seen = set()
        validated = []
        
        for url in urls:
            if not url:
                continue
            cleaned = self._clean_image_url(url)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                validated.append(cleaned)
        
        return validated
    
    def migrate(self) -> dict:
        """Perform the migration"""
        stats = {
            'total_articles': 0,
            'migrated_articles': 0,
            'total_images_found': 0,
            'articles_with_new_images': 0,
            'errors': 0
        }
        
        logger.info(f"Starting image migration for database: {self.db_path}")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if old schema exists
                cursor.execute("PRAGMA table_info(articles)")
                columns = [col[1] for col in cursor.fetchall()]
                
                has_old_image_url = 'image_url' in columns
                has_image_urls = 'image_urls' in columns
                
                if not has_image_urls:
                    logger.error("image_urls column not found. Please run the updated rss2db.py first.")
                    return stats
                
                logger.info(f"Old image_url column exists: {has_old_image_url}")
                logger.info(f"New image_urls column exists: {has_image_urls}")
                
                # Build the select query based on available columns
                select_cols = ['id', 'content', 'description', 'enclosures', 'media_content', 'image_urls']
                if has_old_image_url:
                    select_cols.insert(1, 'image_url')
                
                cursor.execute(f"SELECT {', '.join(select_cols)} FROM articles")
                articles = cursor.fetchall()
                
                stats['total_articles'] = len(articles)
                logger.info(f"Found {len(articles)} articles to process")
                
                for row in articles:
                    try:
                        all_images = set()
                        
                        # Parse row based on available columns
                        idx = 0
                        article_id = row[idx]
                        idx += 1
                        
                        old_image_url = row[idx] if has_old_image_url else None
                        if has_old_image_url:
                            idx += 1
                        
                        content = row[idx]
                        idx += 1
                        description = row[idx]
                        idx += 1
                        enclosures = row[idx]
                        idx += 1
                        media_content = row[idx]
                        idx += 1
                        existing_image_urls = row[idx]
                        
                        # Collect from old image_url
                        if old_image_url:
                            all_images.add(old_image_url)
                        
                        # Collect from existing image_urls
                        if existing_image_urls:
                            try:
                                urls = json.loads(existing_image_urls)
                                if isinstance(urls, list):
                                    all_images.update(urls)
                            except:
                                pass
                        
                        # Extract from content
                        if content:
                            all_images.update(self._extract_images_from_html(content))
                        
                        # Extract from description
                        if description:
                            all_images.update(self._extract_images_from_html(description))
                        
                        # Extract from enclosures
                        if enclosures:
                            try:
                                enc_list = json.loads(enclosures)
                                for enc in enc_list:
                                    if isinstance(enc, dict):
                                        enc_type = enc.get('type', '')
                                        if enc_type.startswith('image/'):
                                            url = enc.get('url', enc.get('href', ''))
                                            if url:
                                                all_images.add(url)
                            except:
                                pass
                        
                        # Extract from media_content
                        if media_content:
                            try:
                                media_list = json.loads(media_content)
                                for media in media_list:
                                    if isinstance(media, dict):
                                        media_type = media.get('type', '')
                                        if media_type.startswith('image/') or 'image' in media_type.lower():
                                            url = media.get('url', '')
                                            if url:
                                                all_images.add(url)
                            except:
                                pass
                        
                        # Validate and update
                        validated_images = self._validate_and_filter_urls(list(all_images))
                        
                        if validated_images:
                            # Check if this adds new images
                            existing_count = 0
                            if existing_image_urls:
                                try:
                                    existing = json.loads(existing_image_urls)
                                    existing_count = len(existing) if isinstance(existing, list) else 0
                                except:
                                    pass
                            
                            new_count = len(validated_images)
                            if new_count > existing_count:
                                stats['articles_with_new_images'] += 1
                            
                            cursor.execute(
                                'UPDATE articles SET image_urls = ? WHERE id = ?',
                                (json.dumps(validated_images), article_id)
                            )
                            stats['migrated_articles'] += 1
                            stats['total_images_found'] += len(validated_images)
                    
                    except Exception as e:
                        logger.error(f"Error processing article {article_id}: {e}")
                        stats['errors'] += 1
                
                conn.commit()
                logger.info("Migration completed successfully!")
        
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            stats['errors'] += 1
        
        return stats
    
    def print_stats(self, stats: dict):
        """Print migration statistics"""
        print(f"\n{'='*60}")
        print("IMAGE MIGRATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total articles processed: {stats['total_articles']}")
        print(f"Articles migrated: {stats['migrated_articles']}")
        print(f"Articles with new images found: {stats['articles_with_new_images']}")
        print(f"Total images extracted: {stats['total_images_found']}")
        print(f"Errors: {stats['errors']}")
        
        if stats['migrated_articles'] > 0:
            avg_images = stats['total_images_found'] / stats['migrated_articles']
            print(f"Average images per article: {avg_images:.2f}")
        
        print(f"{'='*60}")


def main():
    """Main migration function"""
    import sys
    
    db_path = 'rss_articles.db'
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print(f"Migrating database: {db_path}")
    print("This will consolidate all image URLs into the unified image_urls column.")
    
    response = input("Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Migration cancelled.")
        return
    
    migrator = ImageMigrator(db_path)
    stats = migrator.migrate()
    migrator.print_stats(stats)
    
    print("\nMigration complete!")
    print("All image URLs are now consolidated in the 'image_urls' column.")


if __name__ == "__main__":
    main()

