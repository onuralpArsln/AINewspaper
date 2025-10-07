#!/usr/bin/env python3
"""
Article Grouping Script
Scans the RSS articles database and groups similar articles from different sources
"""

import argparse
import sys
from datetime import datetime
from typing import Dict, Any

from article_similarity import ArticleSimilarityDetector
from db_query import RSSDatabaseQuery

class ArticleGrouper:
    """Main class for grouping similar articles"""
    
    def __init__(self, db_path: str = 'rss_articles.db'):
        self.detector = ArticleSimilarityDetector(db_path)
        self.db_query = RSSDatabaseQuery(db_path)
    
    def print_database_status(self):
        """Print current database status"""
        print("=" * 80)
        print("DATABASE STATUS")
        print("=" * 80)
        
        total_articles = self.db_query.get_total_articles()
        sources = self.db_query.get_articles_by_source()
        
        print(f"Total articles: {total_articles:,}")
        print(f"Number of sources: {len(sources)}")
        
        print(f"\nTop 10 sources:")
        for source, count in list(sources.items())[:10]:
            print(f"  {source}: {count:,} articles")
        
        # Check how many articles are already grouped
        try:
            with self.detector.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) as grouped_count
                    FROM articles 
                    WHERE event_group_id IS NOT NULL AND event_group_id > 0
                ''')
                grouped_count = cursor.fetchone()[0]
                
                cursor.execute('''
                    SELECT COUNT(DISTINCT event_group_id) as group_count
                    FROM articles 
                    WHERE event_group_id IS NOT NULL AND event_group_id > 0
                ''')
                group_count = cursor.fetchone()[0]
                
                print(f"\nGrouping Status:")
                print(f"  Articles already grouped: {grouped_count:,}")
                print(f"  Total event groups: {group_count}")
                print(f"  Ungrouped articles: {total_articles - grouped_count:,}")
        
        except Exception as e:
            print(f"Error checking grouping status: {e}")
    
    def run_grouping(self, similarity_threshold: float = 0.3, days_back: int = 7, 
                    min_group_size: int = 2, max_time_diff_days: int = 2, verbose: bool = False) -> Dict[str, Any]:
        """Run the article grouping process"""
        print("=" * 80)
        print("STARTING ARTICLE GROUPING PROCESS")
        print("=" * 80)
        
        print(f"Parameters:")
        print(f"  Similarity threshold: {similarity_threshold}")
        print(f"  Days back: {days_back}")
        print(f"  Minimum group size: {min_group_size}")
        print(f"  Max time difference: {max_time_diff_days} days")
        
        if not verbose:
            # Reduce logging verbosity for cleaner output
            import logging
            logging.getLogger().setLevel(logging.WARNING)
        
        # Run grouping
        stats = self.detector.group_similar_articles(
            similarity_threshold=similarity_threshold,
            days_back=days_back,
            min_group_size=min_group_size,
            max_time_diff_days=max_time_diff_days
        )
        
        return stats
    
    def print_grouping_results(self, stats: Dict[str, Any]):
        """Print grouping results"""
        print("\n" + "=" * 80)
        print("GROUPING RESULTS")
        print("=" * 80)
        
        print(f"Articles processed: {stats['articles_processed']:,}")
        print(f"Groups created: {stats['groups_created']}")
        print(f"Articles grouped: {stats['articles_grouped']:,}")
        print(f"Processing time: {stats['processing_time']:.2f} seconds")
        
        if stats['groups_created'] > 0:
            avg_group_size = stats['articles_grouped'] / stats['groups_created']
            print(f"Average group size: {avg_group_size:.1f} articles")
    
    def show_sample_groups(self, limit: int = 5):
        """Show sample event groups"""
        print("\n" + "=" * 80)
        print(f"SAMPLE EVENT GROUPS (Top {limit})")
        print("=" * 80)
        
        groups = self.detector.get_all_groups(limit)
        
        if not groups:
            print("No event groups found.")
            return
        
        for i, group in enumerate(groups, 1):
            print(f"\nGroup {group['event_group_id']} ({group['article_count']} articles):")
            print("-" * 60)
            
            for j, article in enumerate(group['articles'][:3], 1):  # Show first 3 articles
                print(f"  {j}. {article['title'][:70]}...")
                print(f"     Source: {article['source_name']}")
                print(f"     Published: {article['published'] or 'N/A'}")
                if article.get('similarity_score'):
                    print(f"     Similarity: {article['similarity_score']:.3f}")
                print()
            
            if len(group['articles']) > 3:
                print(f"  ... and {len(group['articles']) - 3} more articles")
    
    def search_groups(self, search_term: str, limit: int = 10):
        """Search for groups containing specific terms"""
        print(f"\nSearching for groups containing '{search_term}'...")
        
        try:
            with self.detector.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT DISTINCT event_group_id, COUNT(*) as article_count
                    FROM articles 
                    WHERE event_group_id IS NOT NULL 
                    AND event_group_id > 0
                    AND (title LIKE ? OR description LIKE ?)
                    GROUP BY event_group_id
                    ORDER BY article_count DESC
                    LIMIT ?
                ''', (f'%{search_term}%', f'%{search_term}%', limit))
                
                group_ids = cursor.fetchall()
                
                if not group_ids:
                    print("No groups found containing the search term.")
                    return
                
                print(f"Found {len(group_ids)} groups:")
                print("-" * 60)
                
                for group_id, count in group_ids:
                    articles = self.detector.get_grouped_articles(group_id)
                    print(f"\nGroup {group_id} ({count} articles):")
                    
                    for article in articles[:2]:  # Show first 2 articles
                        print(f"  - {article['title'][:60]}... (Source: {article['source_name']})")
                    
                    if len(articles) > 2:
                        print(f"  ... and {len(articles) - 2} more")
        
        except Exception as e:
            print(f"Error searching groups: {e}")
    
    def reset_grouping(self):
        """Reset all event group assignments"""
        print("Resetting all event group assignments...")
        
        try:
            with self.detector.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE articles SET event_group_id = NULL')
                conn.commit()
                
                print("All event group assignments have been reset.")
        
        except Exception as e:
            print(f"Error resetting grouping: {e}")

def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description='Group similar RSS articles')
    parser.add_argument('--db', default='rss_articles.db', help='Database file path')
    parser.add_argument('--threshold', type=float, default=0.3, 
                       help='Similarity threshold (0.0-1.0)')
    parser.add_argument('--days', type=int, default=7, 
                       help='Number of days back to process')
    parser.add_argument('--min-group-size', type=int, default=2,
                       help='Minimum number of articles per group')
    parser.add_argument('--max-time-diff', type=int, default=2,
                       help='Maximum time difference in days for grouping articles')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--status', action='store_true',
                       help='Show database status only')
    parser.add_argument('--show-groups', type=int, metavar='N',
                       help='Show top N event groups')
    parser.add_argument('--search', type=str,
                       help='Search for groups containing term')
    parser.add_argument('--reset', action='store_true',
                       help='Reset all event group assignments')
    
    args = parser.parse_args()
    
    try:
        grouper = ArticleGrouper(args.db)
        
        # Show status only
        if args.status:
            grouper.print_database_status()
            return
        
        # Reset grouping
        if args.reset:
            grouper.reset_grouping()
            return
        
        # Show existing groups
        if args.show_groups:
            grouper.show_sample_groups(args.show_groups)
            return
        
        # Search groups
        if args.search:
            grouper.search_groups(args.search)
            return
        
        # Show initial status
        grouper.print_database_status()
        
        # Run grouping
        stats = grouper.run_grouping(
            similarity_threshold=args.threshold,
            days_back=args.days,
            min_group_size=args.min_group_size,
            max_time_diff_days=args.max_time_diff,
            verbose=args.verbose
        )
        
        # Show results
        grouper.print_grouping_results(stats)
        
        # Show sample groups if any were created
        if stats['groups_created'] > 0:
            grouper.show_sample_groups(3)
        
        print("\n" + "=" * 80)
        print("GROUPING PROCESS COMPLETED")
        print("=" * 80)
    
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
