#!/usr/bin/env python3
"""
Simple script to inspect RSS articles and their images in the database.
Shows article details and extracted images to verify the filtering is working correctly.
"""

import sqlite3
import json
import sys
import os
from typing import List, Dict, Any

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def connect_to_database(db_path: str = 'rss_articles.db') -> sqlite3.Connection:
    """Connect to the RSS articles database"""
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        print("Run the RSS processing first to create the database.")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_article_count(conn: sqlite3.Connection) -> int:
    """Get total number of articles in database"""
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM articles')
    return cursor.fetchone()[0]

def get_articles_with_images(conn: sqlite3.Connection, limit: int = 10) -> List[Dict[str, Any]]:
    """Get articles that have images"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, source_name, link, published, image_urls, created_at
        FROM articles 
        WHERE image_urls IS NOT NULL AND image_urls != '[]' AND image_urls != 'null'
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (limit,))
    return [dict(row) for row in cursor.fetchall()]

def get_articles_without_images(conn: sqlite3.Connection, limit: int = 10) -> List[Dict[str, Any]]:
    """Get articles that don't have images"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, source_name, link, published, created_at
        FROM articles 
        WHERE image_urls IS NULL OR image_urls = '[]' OR image_urls = 'null'
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (limit,))
    return [dict(row) for row in cursor.fetchall()]

def get_image_statistics(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Get comprehensive image statistics"""
    cursor = conn.cursor()
    
    stats = {
        'total_articles': 0,
        'articles_with_images': 0,
        'articles_without_images': 0,
        'total_images': 0,
        'average_images_per_article': 0,
        'max_images_in_article': 0,
        'sources_with_images': {},
        'sources_without_images': {}
    }
    
    # Get total articles
    cursor.execute('SELECT COUNT(*) FROM articles')
    stats['total_articles'] = cursor.fetchone()[0]
    
    # Get articles with images
    cursor.execute('''
        SELECT COUNT(*) FROM articles 
        WHERE image_urls IS NOT NULL AND image_urls != '[]' AND image_urls != 'null'
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
    
    # Get statistics by source
    cursor.execute('''
        SELECT source_name, 
               COUNT(*) as total,
               SUM(CASE WHEN image_urls IS NOT NULL AND image_urls != '[]' AND image_urls != 'null' THEN 1 ELSE 0 END) as with_images
        FROM articles 
        GROUP BY source_name 
        ORDER BY COUNT(*) DESC
        LIMIT 10
    ''')
    
    for row in cursor.fetchall():
        source = row['source_name'] or 'Unknown'
        total = row['total']
        with_images = row['with_images']
        stats['sources_with_images'][source] = with_images
        stats['sources_without_images'][source] = total - with_images
    
    return stats

def display_article_details(article: Dict[str, Any], show_full_urls: bool = False):
    """Display detailed information about an article"""
    print(f"\n{'='*80}")
    print(f"📰 ARTICLE #{article['id']}")
    print(f"{'='*80}")
    print(f"Title: {article['title']}")
    print(f"Source: {article['source_name']}")
    print(f"Published: {article['published']}")
    print(f"Added to DB: {article['created_at']}")
    print(f"Link: {article['link']}")
    
    # Display images
    if 'image_urls' in article and article['image_urls']:
        try:
            image_urls = json.loads(article['image_urls'])
            if isinstance(image_urls, list) and image_urls:
                print(f"\n🖼️  IMAGES ({len(image_urls)}):")
                for i, img_url in enumerate(image_urls, 1):
                    if show_full_urls:
                        print(f"  {i}. {img_url}")
                    else:
                        # Show truncated URL for readability
                        truncated = img_url[:80] + "..." if len(img_url) > 80 else img_url
                        print(f"  {i}. {truncated}")
            else:
                print("\n❌ No valid images found")
        except Exception as e:
            print(f"\n❌ Error parsing images: {e}")
    else:
        print("\n❌ No images in this article")

def display_statistics(stats: Dict[str, Any]):
    """Display comprehensive statistics"""
    print(f"\n{'='*60}")
    print(f"📊 DATABASE STATISTICS")
    print(f"{'='*60}")
    print(f"Total Articles: {stats['total_articles']}")
    print(f"Articles with Images: {stats['articles_with_images']}")
    print(f"Articles without Images: {stats['articles_without_images']}")
    print(f"Total Images: {stats['total_images']}")
    print(f"Average Images per Article: {stats['average_images_per_article']}")
    print(f"Max Images in Single Article: {stats['max_images_in_article']}")
    
    if stats['total_articles'] > 0:
        image_percentage = round((stats['articles_with_images'] / stats['total_articles']) * 100, 1)
        print(f"Articles with Images: {image_percentage}%")
    
    print(f"\n📈 TOP SOURCES:")
    for source, with_images in list(stats['sources_with_images'].items())[:5]:
        without_images = stats['sources_without_images'].get(source, 0)
        total = with_images + without_images
        if total > 0:
            percentage = round((with_images / total) * 100, 1)
            print(f"  {source}: {with_images}/{total} articles have images ({percentage}%)")

def main():
    """Main function"""
    print("🔍 RSS ARTICLES & IMAGES INSPECTOR")
    print("=" * 50)
    
    # Connect to database
    try:
        conn = connect_to_database()
        print(f"✅ Connected to database: rss_articles.db")
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        return
    
    # Get statistics
    stats = get_image_statistics(conn)
    display_statistics(stats)
    
    # Show menu
    while True:
        print(f"\n{'='*60}")
        print("📋 MENU OPTIONS:")
        print("1. Show articles WITH images (recent 10)")
        print("2. Show articles WITHOUT images (recent 10)")
        print("3. Show detailed view of specific article")
        print("4. Show full URLs in image listings")
        print("5. Refresh statistics")
        print("6. Exit")
        print(f"{'='*60}")
        
        try:
            choice = input("Enter your choice (1-6): ").strip()
            
            if choice == '1':
                print(f"\n📰 ARTICLES WITH IMAGES (Recent 10):")
                articles = get_articles_with_images(conn, 10)
                if not articles:
                    print("❌ No articles with images found")
                else:
                    for article in articles:
                        display_article_details(article, show_full_urls=False)
                        input("\nPress Enter to continue...")
            
            elif choice == '2':
                print(f"\n📰 ARTICLES WITHOUT IMAGES (Recent 10):")
                articles = get_articles_without_images(conn, 10)
                if not articles:
                    print("✅ All articles have images!")
                else:
                    for i, article in enumerate(articles, 1):
                        print(f"\n{i}. {article['title'][:60]}...")
                        print(f"   Source: {article['source_name']}")
                        print(f"   Link: {article['link'][:60]}...")
                        if i % 5 == 0:
                            input("\nPress Enter to continue...")
            
            elif choice == '3':
                article_id = input("Enter article ID: ").strip()
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT * FROM articles WHERE id = ?
                    ''', (int(article_id),))
                    article = cursor.fetchone()
                    if article:
                        display_article_details(dict(article), show_full_urls=True)
                    else:
                        print(f"❌ Article with ID {article_id} not found")
                except ValueError:
                    print("❌ Please enter a valid article ID number")
                except Exception as e:
                    print(f"❌ Error: {e}")
            
            elif choice == '4':
                print(f"\n📰 ARTICLES WITH FULL IMAGE URLS:")
                articles = get_articles_with_images(conn, 5)
                for article in articles:
                    display_article_details(article, show_full_urls=True)
                    input("\nPress Enter to continue...")
            
            elif choice == '5':
                stats = get_image_statistics(conn)
                display_statistics(stats)
            
            elif choice == '6':
                print("👋 Goodbye!")
                break
            
            else:
                print("❌ Invalid choice. Please enter 1-6.")
        
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
    
    conn.close()

if __name__ == "__main__":
    main()
