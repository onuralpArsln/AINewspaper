#!/usr/bin/env python3
"""
Test Script for scraper2db.py
Validates extraction accuracy by comparing automated scraping results with manual analysis
"""

import sqlite3
import json
import time
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import logging
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
import html
import re

# Import the scraper classes
from scraper2db import ScraperToDatabase, WebScraper, ArticleListingParser, ArticleContentParser
from db_query import RSSDatabaseQuery

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ScraperTestRunner:
    """Execute scraper and capture detailed results for comparison"""
    
    def __init__(self, db_path: str = 'rss_articles.db'):
        self.db_path = db_path
        self.scraper_results = []
        self.source_urls = []
        self.article_urls_found = {}
        self.extraction_results = {}
        
    def run_scraper_test(self, sources_list_file: str = 'scrapeList.txt') -> Dict[str, Any]:
        """Run the scraper and capture all results"""
        logger.info("Starting scraper test execution...")
        
        # Initialize scraper
        scraper2db = ScraperToDatabase(self.db_path)
        
        # Read source URLs
        self.source_urls = scraper2db.read_sources_from_file(sources_list_file)
        logger.info(f"Found {len(self.source_urls)} source URLs to test")
        
        # Process each source and capture detailed results
        for i, source_url in enumerate(self.source_urls, 1):
            logger.info(f"Processing source {i}/{len(self.source_urls)}: {source_url}")
            
            source_result = {
                'source_url': source_url,
                'article_urls': [],
                'extraction_results': [],
                'errors': [],
                'success': False
            }
            
            try:
                # Fetch listing page
                soup = scraper2db.scraper.fetch_page(source_url)
                if not soup:
                    source_result['errors'].append('Failed to fetch listing page')
                    self.scraper_results.append(source_result)
                    continue
                
                # Extract article URLs
                article_urls = scraper2db.listing_parser.extract_article_urls(soup, source_url, max_articles=5)
                source_result['article_urls'] = article_urls
                self.article_urls_found[source_url] = article_urls
                
                logger.info(f"Found {len(article_urls)} article URLs from {source_url}")
                
                # Process each article URL
                for article_url in article_urls:
                    try:
                        # Check if URL already exists in database
                        if scraper2db.scraper.check_url_exists(article_url, scraper2db.db):
                            logger.debug(f"Article already exists, skipping: {article_url}")
                            continue
                        
                        # Fetch article page
                        article_soup = scraper2db.scraper.fetch_page(article_url)
                        if not article_soup:
                            source_result['errors'].append(f'Failed to fetch article: {article_url}')
                            continue
                        
                        # Extract article content
                        article_data = scraper2db.content_parser.extract_article_content(article_soup, article_url)
                        
                        # Store extraction result
                        extraction_result = {
                            'article_url': article_url,
                            'title': article_data['title'],
                            'content': article_data['content'],
                            'content_length': len(article_data['content']),
                            'image_url': article_data['image_url'],
                            'published': article_data['published'],
                            'author': article_data['author'],
                            'category': article_data['category'],
                            'extraction_timestamp': datetime.now(timezone.utc)
                        }
                        
                        source_result['extraction_results'].append(extraction_result)
                        self.extraction_results[article_url] = extraction_result
                        
                        logger.info(f"Extracted: {article_data['title'][:50]}...")
                        
                    except Exception as e:
                        error_msg = f"Error processing article {article_url}: {e}"
                        logger.error(error_msg)
                        source_result['errors'].append(error_msg)
                        continue
                
                source_result['success'] = len(source_result['extraction_results']) > 0
                self.scraper_results.append(source_result)
                
            except Exception as e:
                error_msg = f"Error processing source {source_url}: {e}"
                logger.error(error_msg)
                source_result['errors'].append(error_msg)
                self.scraper_results.append(source_result)
                continue
        
        # Generate summary
        total_articles = sum(len(result['extraction_results']) for result in self.scraper_results)
        successful_sources = sum(1 for result in self.scraper_results if result['success'])
        
        summary = {
            'total_sources': len(self.source_urls),
            'successful_sources': successful_sources,
            'total_articles_extracted': total_articles,
            'extraction_results': self.extraction_results,
            'source_results': self.scraper_results
        }
        
        logger.info(f"Scraper test completed: {successful_sources}/{len(self.source_urls)} sources successful, {total_articles} articles extracted")
        return summary

class ManualAnalyzer:
    """Manually analyze the same URLs to establish ground truth"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        # Decode HTML entities
        text = html.unescape(text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a web page"""
        try:
            logger.info(f"Manually fetching: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            return soup
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def extract_title_manual(self, soup: BeautifulSoup) -> str:
        """Extract title using comprehensive manual strategies"""
        # Strategy 1: Open Graph title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return self.clean_text(og_title['content'])
        
        # Strategy 2: Twitter Card title
        twitter_title = soup.find('meta', name='twitter:title')
        if twitter_title and twitter_title.get('content'):
            return self.clean_text(twitter_title['content'])
        
        # Strategy 3: H1 tag
        h1 = soup.find('h1')
        if h1:
            title = self.clean_text(h1.get_text())
            if title and len(title) > 10:
                return title
        
        # Strategy 4: Article title classes (comprehensive list)
        title_selectors = [
            '.article-title', '.news-title', '.post-title', '.entry-title',
            '.headline', '.title', '.article-headline', '.news-headline',
            '[class*="title"]', '[class*="headline"]', '[class*="article"] h1',
            '[class*="news"] h1', '[class*="post"] h1', '[class*="entry"] h1'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = self.clean_text(title_elem.get_text())
                if title and len(title) > 10:
                    return title
        
        # Strategy 5: Largest heading
        headings = soup.find_all(['h1', 'h2', 'h3'])
        if headings:
            largest_heading = max(headings, key=lambda h: len(h.get_text()))
            title = self.clean_text(largest_heading.get_text())
            if title and len(title) > 10:
                return title
        
        # Strategy 6: Page title tag
        title_tag = soup.find('title')
        if title_tag:
            title = self.clean_text(title_tag.get_text())
            if title and len(title) > 10:
                return title
        
        return ""
    
    def extract_content_manual(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract content using comprehensive manual strategies"""
        content_result = {
            'content': '',
            'paragraph_count': 0,
            'word_count': 0,
            'character_count': 0,
            'extraction_method': ''
        }
        
        # Strategy 1: Article tag
        article = soup.find('article')
        if article:
            content = self._extract_text_from_element(article)
            if content and len(content) > 100:
                content_result.update({
                    'content': content,
                    'paragraph_count': len(article.find_all('p')),
                    'word_count': len(content.split()),
                    'character_count': len(content),
                    'extraction_method': 'article_tag'
                })
                return content_result
        
        # Strategy 2: Article content classes (comprehensive list)
        content_selectors = [
            '.article-content', '.news-content', '.post-content', '.entry-content',
            '.content', '.article-body', '.news-body', '.post-body', '.entry-body',
            '.article-text', '.news-text', '.post-text', '.entry-text',
            '[class*="content"]', '[class*="article"]', '[class*="news"]',
            '[class*="post"]', '[class*="entry"]', '[class*="body"]'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                content = self._extract_text_from_element(content_elem)
                if content and len(content) > 100:
                    content_result.update({
                        'content': content,
                        'paragraph_count': len(content_elem.find_all('p')),
                        'word_count': len(content.split()),
                        'character_count': len(content),
                        'extraction_method': f'selector_{selector}'
                    })
                    return content_result
        
        # Strategy 3: Largest div with paragraphs
        divs_with_paragraphs = soup.find_all('div')
        content_divs = []
        
        for div in divs_with_paragraphs:
            paragraphs = div.find_all('p')
            if len(paragraphs) >= 3:
                content = self._extract_text_from_element(div)
                if content and len(content) > 100:
                    content_divs.append((content, len(content), len(paragraphs)))
        
        if content_divs:
            # Return content from div with most text
            content_divs.sort(key=lambda x: x[1], reverse=True)
            best_content, char_count, para_count = content_divs[0]
            content_result.update({
                'content': best_content,
                'paragraph_count': para_count,
                'word_count': len(best_content.split()),
                'character_count': char_count,
                'extraction_method': 'largest_div_with_paragraphs'
            })
            return content_result
        
        return content_result
    
    def _extract_text_from_element(self, element) -> str:
        """Extract clean text from an HTML element"""
        if not element:
            return ""
        
        # Remove script and style elements
        for script in element(["script", "style", "nav", "footer", "header", "aside", "advertisement", "ads"]):
            script.decompose()
        
        # Get text and clean it
        text = element.get_text()
        return self.clean_text(text)
    
    def extract_image_manual(self, soup: BeautifulSoup, article_url: str) -> str:
        """Extract primary image using comprehensive manual strategies"""
        # Strategy 1: Open Graph image
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            img_url = og_image['content']
            if self._is_valid_image_url(img_url):
                return urljoin(article_url, img_url)
        
        # Strategy 2: Twitter Card image
        twitter_image = soup.find('meta', name='twitter:image')
        if twitter_image and twitter_image.get('content'):
            img_url = twitter_image['content']
            if self._is_valid_image_url(img_url):
                return urljoin(article_url, img_url)
        
        # Strategy 3: First large image in article content
        article = soup.find('article')
        if article:
            images = article.find_all('img')
            for img in images:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                if src and self._is_valid_image_url(src):
                    # Check if image is reasonably sized
                    width = img.get('width')
                    height = img.get('height')
                    if width and height:
                        try:
                            w, h = int(width), int(height)
                            if w >= 200 and h >= 200:
                                return urljoin(article_url, src)
                        except ValueError:
                            pass
                    else:
                        # If no size info, assume it's okay if it's in article
                        return urljoin(article_url, src)
        
        # Strategy 4: Schema.org image
        schema_image = soup.find('meta', property='image')
        if schema_image and schema_image.get('content'):
            img_url = schema_image['content']
            if self._is_valid_image_url(img_url):
                return urljoin(article_url, img_url)
        
        # Strategy 5: First image in main content area
        main_content = soup.find('main') or soup.find('div', class_=re.compile(r'content|article|news|post'))
        if main_content:
            images = main_content.find_all('img')
            for img in images:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                if src and self._is_valid_image_url(src):
                    return urljoin(article_url, src)
        
        return ""
    
    def _is_valid_image_url(self, url: str) -> bool:
        """Check if URL looks like a valid image"""
        if not url:
            return False
        
        # Skip data URLs and very short URLs
        if url.startswith('data:') or len(url) < 10:
            return False
        
        # Skip common non-image patterns
        skip_patterns = [
            'logo', 'icon', 'avatar', 'profile', 'banner', 'advertisement',
            'ad-', 'sponsor', 'social', 'share', 'button', 'arrow', 'bullet',
            'dot', 'pixel', 'tracking', 'beacon', 'favicon'
        ]
        
        url_lower = url.lower()
        for pattern in skip_patterns:
            if pattern in url_lower:
                return False
        
        # Must be HTTP/HTTPS
        return url.startswith('http://') or url.startswith('https://')
    
    def analyze_article_manual(self, article_url: str) -> Dict[str, Any]:
        """Manually analyze a single article URL"""
        soup = self.fetch_page(article_url)
        if not soup:
            return {
                'article_url': article_url,
                'success': False,
                'error': 'Failed to fetch page'
            }
        
        # Extract all components
        title = self.extract_title_manual(soup)
        content_data = self.extract_content_manual(soup)
        image_url = self.extract_image_manual(soup, article_url)
        
        return {
            'article_url': article_url,
            'success': True,
            'title': title,
            'content': content_data['content'],
            'content_length': content_data['character_count'],
            'paragraph_count': content_data['paragraph_count'],
            'word_count': content_data['word_count'],
            'extraction_method': content_data['extraction_method'],
            'image_url': image_url,
            'analysis_timestamp': datetime.now(timezone.utc)
        }

class ComparisonEngine:
    """Compare scraped results with manual analysis"""
    
    def __init__(self):
        self.comparison_results = []
        self.summary_stats = {}
    
    def compare_results(self, scraper_results: Dict[str, Any], manual_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare scraped vs manual results"""
        logger.info("Starting comparison of scraped vs manual results...")
        
        # Create lookup for manual results
        manual_lookup = {result['article_url']: result for result in manual_results if result['success']}
        
        comparison_results = []
        total_articles = 0
        successful_comparisons = 0
        
        # Compare each scraped article
        for article_url, scraped_data in scraper_results['extraction_results'].items():
            total_articles += 1
            
            if article_url not in manual_lookup:
                comparison_results.append({
                    'article_url': article_url,
                    'comparison_success': False,
                    'error': 'Manual analysis failed for this URL',
                    'scraped_data': scraped_data
                })
                continue
            
            manual_data = manual_lookup[article_url]
            comparison = self._compare_single_article(scraped_data, manual_data)
            comparison_results.append(comparison)
            
            if comparison['comparison_success']:
                successful_comparisons += 1
        
        # Generate summary statistics
        self.summary_stats = self._generate_summary_stats(comparison_results)
        
        return {
            'total_articles_compared': total_articles,
            'successful_comparisons': successful_comparisons,
            'comparison_results': comparison_results,
            'summary_stats': self.summary_stats
        }
    
    def _compare_single_article(self, scraped_data: Dict[str, Any], manual_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compare a single article's scraped vs manual results"""
        comparison = {
            'article_url': scraped_data['article_url'],
            'comparison_success': True,
            'title_comparison': self._compare_titles(scraped_data['title'], manual_data['title']),
            'content_comparison': self._compare_content(scraped_data['content'], manual_data['content']),
            'image_comparison': self._compare_images(scraped_data['image_url'], manual_data['image_url']),
            'scraped_data': scraped_data,
            'manual_data': manual_data
        }
        
        # Overall success if all major components are reasonably accurate
        title_ok = comparison['title_comparison']['accuracy_score'] >= 0.7
        content_ok = comparison['content_comparison']['accuracy_score'] >= 0.6
        image_ok = comparison['image_comparison']['accuracy_score'] >= 0.5
        
        comparison['overall_accuracy'] = (title_ok and content_ok and image_ok)
        
        return comparison
    
    def _compare_titles(self, scraped_title: str, manual_title: str) -> Dict[str, Any]:
        """Compare title extraction accuracy"""
        if not scraped_title and not manual_title:
            return {'accuracy_score': 1.0, 'status': 'both_empty', 'details': 'Both titles empty'}
        
        if not scraped_title or not manual_title:
            return {'accuracy_score': 0.0, 'status': 'one_empty', 'details': f'Scraped: "{scraped_title}", Manual: "{manual_title}"'}
        
        # Exact match
        if scraped_title.strip() == manual_title.strip():
            return {'accuracy_score': 1.0, 'status': 'exact_match', 'details': 'Titles match exactly'}
        
        # Case-insensitive match
        if scraped_title.lower().strip() == manual_title.lower().strip():
            return {'accuracy_score': 0.95, 'status': 'case_insensitive_match', 'details': 'Titles match (case insensitive)'}
        
        # Similarity check (basic)
        scraped_words = set(scraped_title.lower().split())
        manual_words = set(manual_title.lower().split())
        
        if len(scraped_words) == 0 or len(manual_words) == 0:
            return {'accuracy_score': 0.0, 'status': 'no_common_words', 'details': 'No common words found'}
        
        common_words = scraped_words.intersection(manual_words)
        similarity = len(common_words) / max(len(scraped_words), len(manual_words))
        
        if similarity >= 0.8:
            return {'accuracy_score': 0.8, 'status': 'high_similarity', 'details': f'High similarity: {similarity:.2f}'}
        elif similarity >= 0.5:
            return {'accuracy_score': 0.5, 'status': 'medium_similarity', 'details': f'Medium similarity: {similarity:.2f}'}
        else:
            return {'accuracy_score': 0.0, 'status': 'low_similarity', 'details': f'Low similarity: {similarity:.2f}'}
    
    def _compare_content(self, scraped_content: str, manual_content: str) -> Dict[str, Any]:
        """Compare content extraction accuracy"""
        scraped_len = len(scraped_content) if scraped_content else 0
        manual_len = len(manual_content) if manual_content else 0
        
        if scraped_len == 0 and manual_len == 0:
            return {'accuracy_score': 1.0, 'status': 'both_empty', 'details': 'Both content empty'}
        
        if scraped_len == 0 or manual_len == 0:
            return {'accuracy_score': 0.0, 'status': 'one_empty', 'details': f'Scraped: {scraped_len} chars, Manual: {manual_len} chars'}
        
        # Length comparison
        length_ratio = min(scraped_len, manual_len) / max(scraped_len, manual_len)
        
        # Content quality thresholds
        min_acceptable_length = 200
        scraped_adequate = scraped_len >= min_acceptable_length
        manual_adequate = manual_len >= min_acceptable_length
        
        if length_ratio >= 0.8 and scraped_adequate and manual_adequate:
            return {'accuracy_score': 0.9, 'status': 'excellent', 'details': f'Both adequate length, ratio: {length_ratio:.2f}'}
        elif length_ratio >= 0.6 and scraped_adequate:
            return {'accuracy_score': 0.7, 'status': 'good', 'details': f'Scraped adequate, ratio: {length_ratio:.2f}'}
        elif scraped_adequate:
            return {'accuracy_score': 0.5, 'status': 'acceptable', 'details': f'Scraped adequate but different length, ratio: {length_ratio:.2f}'}
        else:
            return {'accuracy_score': 0.2, 'status': 'poor', 'details': f'Scraped too short: {scraped_len} chars, ratio: {length_ratio:.2f}'}
    
    def _compare_images(self, scraped_image: str, manual_image: str) -> Dict[str, Any]:
        """Compare image extraction accuracy"""
        if not scraped_image and not manual_image:
            return {'accuracy_score': 1.0, 'status': 'both_empty', 'details': 'Both images empty'}
        
        if not scraped_image or not manual_image:
            return {'accuracy_score': 0.0, 'status': 'one_empty', 'details': f'Scraped: {bool(scraped_image)}, Manual: {bool(manual_image)}'}
        
        # Exact match
        if scraped_image == manual_image:
            return {'accuracy_score': 1.0, 'status': 'exact_match', 'details': 'Images match exactly'}
        
        # Same domain/path
        scraped_domain = urlparse(scraped_image).netloc
        manual_domain = urlparse(manual_image).netloc
        
        if scraped_domain == manual_domain:
            return {'accuracy_score': 0.8, 'status': 'same_domain', 'details': 'Images from same domain'}
        
        # Both valid URLs
        if scraped_image.startswith('http') and manual_image.startswith('http'):
            return {'accuracy_score': 0.6, 'status': 'both_valid', 'details': 'Both are valid image URLs'}
        
        return {'accuracy_score': 0.3, 'status': 'different', 'details': 'Different images found'}
    
    def _generate_summary_stats(self, comparison_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics from comparison results"""
        total = len(comparison_results)
        if total == 0:
            return {}
        
        # Title accuracy
        title_scores = [r['title_comparison']['accuracy_score'] for r in comparison_results]
        title_avg = sum(title_scores) / len(title_scores)
        title_good = sum(1 for score in title_scores if score >= 0.7)
        
        # Content accuracy
        content_scores = [r['content_comparison']['accuracy_score'] for r in comparison_results]
        content_avg = sum(content_scores) / len(content_scores)
        content_good = sum(1 for score in content_scores if score >= 0.6)
        
        # Image accuracy
        image_scores = [r['image_comparison']['accuracy_score'] for r in comparison_results]
        image_avg = sum(image_scores) / len(image_scores)
        image_good = sum(1 for score in image_scores if score >= 0.5)
        
        # Overall accuracy
        overall_good = sum(1 for r in comparison_results if r['overall_accuracy'])
        
        return {
            'total_articles': total,
            'title_accuracy': {
                'average_score': round(title_avg, 3),
                'good_extractions': title_good,
                'good_percentage': round(title_good / total * 100, 1)
            },
            'content_accuracy': {
                'average_score': round(content_avg, 3),
                'good_extractions': content_good,
                'good_percentage': round(content_good / total * 100, 1)
            },
            'image_accuracy': {
                'average_score': round(image_avg, 3),
                'good_extractions': image_good,
                'good_percentage': round(image_good / total * 100, 1)
            },
            'overall_accuracy': {
                'good_extractions': overall_good,
                'good_percentage': round(overall_good / total * 100, 1)
            }
        }

class ReportGenerator:
    """Generate detailed comparison report"""
    
    def __init__(self):
        self.report_sections = []
    
    def generate_report(self, comparison_data: Dict[str, Any]) -> str:
        """Generate comprehensive comparison report"""
        logger.info("Generating detailed comparison report...")
        
        report = []
        report.append("=" * 80)
        report.append("SCRAPER2DB EXTRACTION ACCURACY TEST REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Summary section
        report.extend(self._generate_summary_section(comparison_data))
        
        # Detailed per-article analysis
        report.extend(self._generate_detailed_analysis(comparison_data))
        
        # Improvement recommendations
        report.extend(self._generate_improvement_recommendations(comparison_data))
        
        return "\n".join(report)
    
    def _generate_summary_section(self, comparison_data: Dict[str, Any]) -> List[str]:
        """Generate summary statistics section"""
        summary = []
        summary.append("SUMMARY STATISTICS")
        summary.append("-" * 40)
        
        stats = comparison_data['summary_stats']
        summary.append(f"Total articles analyzed: {stats['total_articles']}")
        summary.append("")
        
        # Title accuracy
        title_stats = stats['title_accuracy']
        summary.append(f"Title Extraction Accuracy:")
        summary.append(f"  Average score: {title_stats['average_score']}")
        summary.append(f"  Good extractions: {title_stats['good_extractions']}/{stats['total_articles']} ({title_stats['good_percentage']}%)")
        summary.append("")
        
        # Content accuracy
        content_stats = stats['content_accuracy']
        summary.append(f"Content Extraction Accuracy:")
        summary.append(f"  Average score: {content_stats['average_score']}")
        summary.append(f"  Good extractions: {content_stats['good_extractions']}/{stats['total_articles']} ({content_stats['good_percentage']}%)")
        summary.append("")
        
        # Image accuracy
        image_stats = stats['image_accuracy']
        summary.append(f"Image Extraction Accuracy:")
        summary.append(f"  Average score: {image_stats['average_score']}")
        summary.append(f"  Good extractions: {image_stats['good_extractions']}/{stats['total_articles']} ({image_stats['good_percentage']}%)")
        summary.append("")
        
        # Overall accuracy
        overall_stats = stats['overall_accuracy']
        summary.append(f"Overall Extraction Accuracy:")
        summary.append(f"  Good extractions: {overall_stats['good_extractions']}/{stats['total_articles']} ({overall_stats['good_percentage']}%)")
        summary.append("")
        
        return summary
    
    def _generate_detailed_analysis(self, comparison_data: Dict[str, Any]) -> List[str]:
        """Generate detailed per-article analysis"""
        analysis = []
        analysis.append("DETAILED PER-ARTICLE ANALYSIS")
        analysis.append("-" * 40)
        
        for i, result in enumerate(comparison_data['comparison_results'], 1):
            analysis.append(f"\nArticle {i}: {result['article_url']}")
            analysis.append(f"Overall Accuracy: {'✓' if result['overall_accuracy'] else '✗'}")
            
            # Title comparison
            title_comp = result['title_comparison']
            analysis.append(f"  Title: {title_comp['status']} (score: {title_comp['accuracy_score']:.2f})")
            analysis.append(f"    Scraped: {result['scraped_data']['title'][:60]}...")
            analysis.append(f"    Manual:  {result['manual_data']['title'][:60]}...")
            
            # Content comparison
            content_comp = result['content_comparison']
            analysis.append(f"  Content: {content_comp['status']} (score: {content_comp['accuracy_score']:.2f})")
            analysis.append(f"    Scraped: {result['scraped_data']['content_length']} chars")
            analysis.append(f"    Manual:  {result['manual_data']['content_length']} chars")
            
            # Image comparison
            image_comp = result['image_comparison']
            analysis.append(f"  Image: {image_comp['status']} (score: {image_comp['accuracy_score']:.2f})")
            analysis.append(f"    Scraped: {result['scraped_data']['image_url'][:60]}...")
            analysis.append(f"    Manual:  {result['manual_data']['image_url'][:60]}...")
        
        return analysis
    
    def _generate_improvement_recommendations(self, comparison_data: Dict[str, Any]) -> List[str]:
        """Generate improvement recommendations based on analysis"""
        recommendations = []
        recommendations.append("\nIMPROVEMENT RECOMMENDATIONS")
        recommendations.append("-" * 40)
        
        stats = comparison_data['summary_stats']
        
        # Title improvements
        if stats['title_accuracy']['good_percentage'] < 80:
            recommendations.append("Title Extraction Issues:")
            recommendations.append("  - Consider adding more title selectors")
            recommendations.append("  - Implement fuzzy matching for similar titles")
            recommendations.append("  - Add fallback to page title tag")
            recommendations.append("")
        
        # Content improvements
        if stats['content_accuracy']['good_percentage'] < 70:
            recommendations.append("Content Extraction Issues:")
            recommendations.append("  - Expand content selector patterns")
            recommendations.append("  - Improve text cleaning and normalization")
            recommendations.append("  - Add minimum content length validation")
            recommendations.append("")
        
        # Image improvements
        if stats['image_accuracy']['good_percentage'] < 60:
            recommendations.append("Image Extraction Issues:")
            recommendations.append("  - Add more image source strategies")
            recommendations.append("  - Improve image URL validation")
            recommendations.append("  - Consider lazy-loaded image detection")
            recommendations.append("")
        
        # General recommendations
        recommendations.append("General Improvements:")
        recommendations.append("  - Add retry logic for failed page fetches")
        recommendations.append("  - Implement better error handling and logging")
        recommendations.append("  - Consider adding content quality scoring")
        recommendations.append("  - Add support for more Turkish news site patterns")
        
        return recommendations

def main():
    """Main test execution function"""
    logger.info("Starting scraper2db.py extraction accuracy test...")
    
    # Phase 1: Run scraper and capture results
    logger.info("Phase 1: Running scraper and capturing results...")
    test_runner = ScraperTestRunner()
    scraper_results = test_runner.run_scraper_test()
    
    if scraper_results['total_articles_extracted'] == 0:
        logger.error("No articles were extracted by the scraper. Cannot proceed with comparison.")
        return
    
    # Phase 2: Manual analysis of same URLs
    logger.info("Phase 2: Performing manual analysis of same URLs...")
    manual_analyzer = ManualAnalyzer()
    manual_results = []
    
    for article_url in scraper_results['extraction_results'].keys():
        manual_result = manual_analyzer.analyze_article_manual(article_url)
        manual_results.append(manual_result)
        time.sleep(1)  # Be respectful to servers
    
    # Phase 3: Compare results
    logger.info("Phase 3: Comparing scraped vs manual results...")
    comparison_engine = ComparisonEngine()
    comparison_data = comparison_engine.compare_results(scraper_results, manual_results)
    
    # Phase 4: Generate report
    logger.info("Phase 4: Generating detailed comparison report...")
    report_generator = ReportGenerator()
    report = report_generator.generate_report(comparison_data)
    
    # Save report to file
    report_filename = f"scraper_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # Print report to console
    print(report)
    
    logger.info(f"Test completed. Report saved to: {report_filename}")
    
    return comparison_data

if __name__ == "__main__":
    main()
