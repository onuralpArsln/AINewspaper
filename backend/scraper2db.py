#!/usr/bin/env python3
"""
Web Scraper to Database Module
Scrapes articles from Turkish news websites and stores them in rss_articles.db
"""

import sqlite3
import hashlib
import json
import re
import time
import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Set, Tuple
import logging
from pathlib import Path
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup, FeatureNotFound
import html

# Import existing RSS classes
from rss2db import RSSArticle, RSSDatabase
# Optional parser detection: prefer lxml if available, else fallback to built-in html.parser
try:
    import lxml  # noqa: F401
    _HAS_LXML = True
except Exception:
    _HAS_LXML = False


# =============================================================================
# CONFIGURATION FLAGS
# =============================================================================

# Maximum number of articles to scrape per source
# Change this value to control how many articles are scraped from each source
MAX_ARTICLES_PER_SOURCE = 5  # Set to any positive integer (e.g., 10, 20, 50)

# Minimum content length threshold (in characters) for articles to be added to database
# Articles with content shorter than this will be skipped
MIN_CONTENT_LENGTH_THRESHOLD = 200  # Set to 0 to disable filtering


# =============================================================================

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WebScraper:
    """Main web scraper class with URL duplicate checking"""
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Logging data
        self.scraping_results = {
            'successful_sources': [],
            'failed_sources': [],
            'total_articles': 0,
            'articles_by_source': {},
            'processing_start_time': None,
            'processing_end_time': None
        }
    
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
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Fetching page: {url} (attempt {attempt + 1})")
                
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                
                # Parse with BeautifulSoup, robust fallback if lxml is unavailable
                if _HAS_LXML:
                    try:
                        return BeautifulSoup(response.content, 'lxml')
                    except (FeatureNotFound, Exception) as e:
                        logger.warning(f"lxml parser not usable; falling back to html.parser: {e}")
                        return BeautifulSoup(response.content, 'html.parser')
                else:
                    logger.warning("lxml parser not available; falling back to html.parser")
                    return BeautifulSoup(response.content, 'html.parser')
                
            except requests.exceptions.RequestException as e:
                error_msg = f"Network error fetching {url}: {e}"
                logger.error(error_msg)
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return None
            except Exception as e:
                error_msg = f"Error parsing page {url}: {e}"
                logger.error(error_msg)
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None
        
        return None
    
    def check_url_exists(self, url: str, db: RSSDatabase) -> bool:
        """Check if article URL already exists in database"""
        try:
            with sqlite3.connect(db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM articles WHERE link = ? OR guid = ?', (url, url))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking URL existence: {e}")
            return False

class SiteProfileManager:
    """Manage site-specific extraction profiles and configurations"""
    
    def __init__(self):
        self.profiles = {
            'internethaber.com': {
                'article_selectors': [
                    'a[href*="/haber/"]',
                    'a[href*="/gundem/"]',
                    'a[href*="/son-dakika/"]',
                    'a[href*="/sondakika/"]',
                    'a[href*="/guncel/"]',
                    '.news-item a',
                    '.article-item a',
                    '[class*="article"] a',
                    '[class*="news"] a',
                    '[class*="haber"] a',
                    '.item a',
                    '.post a',
                    '.entry a',
                    # Additional selectors for internethaber
                    '.content a',
                    '.main-content a',
                    '.news-list a',
                    '.article-list a',
                    # Son-dakika specific selectors
                    '.son-dakika a',
                    '.breaking-news a',
                    '.latest-news a',
                    # Generic news link patterns
                    'a[href*="haber-"]',
                    'a[href*="news-"]'
                ],
                'url_validation': 'permissive',
                'max_articles': 5,
                'content_selectors': [
                    '.article-content',
                    '.news-content',
                    '.post-content',
                    '.entry-content',
                    '[class*="content"]',
                    '[class*="article"]',
                    '[class*="news"]'
                ]
            },
            'yeniakit.com.tr': {
                'article_selectors': [
                    'a[href*="/haber/"]',
                    'a[href*="/gundem/"]',
                    'a[href*="/son-dakika/"]',
                    '.news-item a',
                    '.article-item a',
                    '[class*="article"] a',
                    '[class*="news"] a',
                    '[class*="haber"] a',
                    '.item a',
                    '.post a',
                    '.entry a'
                ],
                'url_validation': 'strict',
                'max_articles': 5,
                'content_selectors': [
                    '.article-content',
                    '.news-content',
                    '.post-content',
                    '.entry-content',
                    '[class*="content"]',
                    '[class*="article"]',
                    '[class*="news"]'
                ]
            },
            'yirmidort.tv': {
                'article_selectors': [
                    'a[href*="/haber/"]',
                    'a[href*="/gundem/"]',
                    'a[href*="/son-dakika/"]',
                    '.news-item a',
                    '.article-item a',
                    '[class*="article"] a',
                    '[class*="news"] a',
                    '[class*="haber"] a',
                    '.item a',
                    '.post a',
                    '.entry a'
                ],
                'url_validation': 'strict',
                'max_articles': 5,
                'content_selectors': [
                    '.article-content',
                    '.news-content',
                    '.post-content',
                    '.entry-content',
                    '[class*="content"]',
                    '[class*="article"]',
                    '[class*="news"]'
                ]
            }
        }
    
    def get_profile(self, domain: str) -> Dict[str, Any]:
        """Get site-specific profile or return default"""
        return self.profiles.get(domain, {
            'article_selectors': [
                'a[href*="/haber/"]',
                'a[href*="/gundem/"]',
                'a[href*="/son-dakika/"]',
                'a[href*="/article/"]',
                'a[href*="/news/"]',
                'article a',
                '.news-item a',
                '.article-item a',
                '[class*="article"] a',
                '[class*="news"] a',
                '[class*="haber"] a',
                '.item a',
                '.post a',
                '.entry a'
            ],
            'url_validation': 'strict',
            'max_articles': 5,
            'content_selectors': [
                '.article-content',
                '.news-content',
                '.post-content',
                '.entry-content',
                '[class*="content"]',
                '[class*="article"]',
                '[class*="news"]'
            ]
        })
    
    def get_validation_mode(self, domain: str) -> str:
        """Get URL validation mode for domain"""
        profile = self.get_profile(domain)
        return profile.get('url_validation', 'strict')

class ArticleListingParser:
    """Extract article URLs from listing pages"""
    
    def __init__(self, scraper: WebScraper):
        self.scraper = scraper
        self.profile_manager = SiteProfileManager()
    
    def extract_article_urls(self, soup: BeautifulSoup, base_url: str, max_articles: int = 5) -> List[str]:
        """Extract article URLs from a listing page using site-specific profiles"""
        article_urls = []
        domain = urlparse(base_url).netloc.lower()
        
        # Get site-specific profile
        profile = self.profile_manager.get_profile(domain)
        selectors = profile.get('article_selectors', [])
        site_max_articles = profile.get('max_articles', max_articles)
        actual_max = min(max_articles, site_max_articles)
        
        logger.info(f"Using {len(selectors)} selectors for domain: {domain}")
        
        for i, selector in enumerate(selectors):
            try:
                links = soup.select(selector)
                logger.debug(f"Selector {i+1}/{len(selectors)} '{selector}': found {len(links)} links")
                
                for link in links:
                    href = link.get('href')
                    if href:
                        # Use site-specific validation mode
                        validation_mode = self.profile_manager.get_validation_mode(domain)
                        if self._is_valid_article_url(href, base_url, validation_mode):
                            full_url = urljoin(base_url, href)
                            if full_url not in article_urls:
                                article_urls.append(full_url)
                                logger.debug(f"Added article URL: {full_url}")
                                
                            if len(article_urls) >= actual_max:
                                break
                
                if len(article_urls) >= actual_max:
                    logger.info(f"Found {len(article_urls)} articles, stopping at selector {i+1}")
                    break
                    
            except Exception as e:
                logger.warning(f"Error with selector '{selector}': {e}")
                continue
        
        # If no articles found with site-specific selectors, try generic fallbacks
        if len(article_urls) == 0:
            logger.warning(f"No articles found with site-specific selectors for {domain}, trying generic fallbacks")
            article_urls = self._extract_with_generic_fallbacks(soup, base_url, actual_max)
        
        logger.info(f"Total article URLs extracted: {len(article_urls)}")
        return article_urls[:actual_max]
    
    def _extract_with_generic_fallbacks(self, soup: BeautifulSoup, base_url: str, max_articles: int) -> List[str]:
        """Extract article URLs using generic fallback selectors"""
        article_urls = []
        domain = urlparse(base_url).netloc.lower()
        
        # Generic fallback selectors (more permissive)
        fallback_selectors = [
            'a[href]',  # All links
            'a',  # All anchor tags
            '[href]',  # All elements with href
        ]
        
        logger.info(f"Trying {len(fallback_selectors)} generic fallback selectors for {domain}")
        
        for i, selector in enumerate(fallback_selectors):
            try:
                links = soup.select(selector)
                logger.debug(f"Fallback selector {i+1}/{len(fallback_selectors)} '{selector}': found {len(links)} links")
                
                for link in links:
                    href = link.get('href')
                    if href:
                        # Use permissive validation for fallbacks
                        if self._is_valid_article_url(href, base_url, 'permissive'):
                            full_url = urljoin(base_url, href)
                            if full_url not in article_urls:
                                article_urls.append(full_url)
                                logger.debug(f"Added article URL via fallback: {full_url}")
                                
                            if len(article_urls) >= max_articles:
                                break
                
                if len(article_urls) >= max_articles:
                    logger.info(f"Found {len(article_urls)} articles via fallback selectors")
                    break
                    
            except Exception as e:
                logger.warning(f"Error with fallback selector '{selector}': {e}")
                continue
        
        return article_urls
    
    def _is_valid_article_url(self, href: str, base_url: str, validation_mode: str = 'strict') -> bool:
        """Check if URL looks like a valid article URL with flexible validation modes"""
        if not href:
            return False
        
        # Skip if it's just a fragment or javascript
        if href.startswith('#') or href.startswith('javascript:'):
            return False
        
        # Skip common non-article patterns
        skip_patterns = [
            '/category/',
            '/tag/',
            '/author/',
            '/page/',
            '/search',
            '/contact',
            '/about',
            '/privacy',
            '/terms',
            '/rss',
            '/feed',
            '/sitemap',
            '/login',
            '/register',
            '/social',
            '/share',
            '/comment',
            '/reply',
            '/edit',
            '/admin',
            '/wp-',
            '/api/',
            '/ajax/',
            '.pdf',
            '.jpg',
            '.png',
            '.gif',
            '.css',
            '.js'
        ]
        
        href_lower = href.lower()
        for pattern in skip_patterns:
            if pattern in href_lower:
                return False
        
        # Extract domain for site-specific validation
        domain = urlparse(base_url).netloc.lower()
        
        # Site-specific validation modes
        if validation_mode == 'permissive' or self._should_use_permissive_mode(domain):
            return self._permissive_url_validation(href, domain)
        else:
            return self._strict_url_validation(href)
    
    def _should_use_permissive_mode(self, domain: str) -> bool:
        """Determine if domain should use permissive URL validation"""
        permissive_domains = [
            'internethaber.com',
            'haberturk.com',
            'hurriyet.com.tr',
            'milliyet.com.tr',
            'sabah.com.tr',
            'sozcu.com.tr'
        ]
        return domain in permissive_domains
    
    def _strict_url_validation(self, href: str) -> bool:
        """Original strict validation requiring article keywords"""
        article_keywords = [
            'haber',
            'gundem',
            'son-dakika',
            'article',
            'news',
            'post',
            'entry'
        ]
        
        href_lower = href.lower()
        return any(keyword in href_lower for keyword in article_keywords)
    
    def _permissive_url_validation(self, href: str, domain: str) -> bool:
        """Permissive validation for sites with different URL patterns"""
        href_lower = href.lower()
        
        # Check for numeric ID patterns (common in Turkish news sites)
        import re
        numeric_id_patterns = [
            r'/\d{4,}',  # /123456 or longer
            r'/\d+[-_]',  # /123456-title or /123456_title
            r'/\d+\.html',  # /123456.html
        ]
        
        for pattern in numeric_id_patterns:
            if re.search(pattern, href_lower):
                logger.debug(f"URL accepted by numeric ID pattern: {href}")
                return True
        
        # Check for minimum path length (likely article if path is substantial)
        path = urlparse(href).path
        if len(path) > 20:  # Substantial path length
            # Additional checks to avoid false positives
            if not any(skip in href_lower for skip in ['/wp-content/', '/static/', '/assets/']):
                logger.debug(f"URL accepted by path length: {href}")
                return True
        
        # Domain-specific patterns
        domain_patterns = {
            'internethaber.com': [
                r'/\d{4}/\d{2}/\d{2}/',  # Date-based URLs
                r'/[a-z-]+-\d+',  # slug-number pattern
                r'/haber/[a-z0-9-]+',  # /haber/slug pattern
                r'/gundem/[a-z0-9-]+',  # /gundem/slug pattern
                r'/son-dakika/[a-z0-9-]+',  # /son-dakika/slug pattern
                r'/sondakika/[a-z0-9-]+',  # /sondakika/slug pattern
                r'/guncel/[a-z0-9-]+',  # /guncel/slug pattern
            ],
            'haberturk.com': [
                r'/haberler/\d+',  # /haberler/123456
                r'/\d{4}/\d{2}/\d{2}/',
            ]
        }
        
        if domain in domain_patterns:
            for pattern in domain_patterns[domain]:
                if re.search(pattern, href_lower):
                    logger.debug(f"URL accepted by domain pattern ({domain}): {href}")
                    return True
        
        # Fallback: check for article-like keywords (less strict)
        article_keywords = [
            'haber', 'gundem', 'son-dakika', 'article', 'news', 'post', 'entry',
            'detay', 'icerik', 'makale', 'yazi'  # Additional Turkish keywords
        ]
        
        if any(keyword in href_lower for keyword in article_keywords):
            logger.debug(f"URL accepted by keyword match: {href}")
            return True
        
        logger.debug(f"URL rejected by permissive validation: {href}")
        return False

class ArticleContentParser:
    """Extract title, content, and image from full articles"""
    
    def __init__(self, scraper: WebScraper):
        self.scraper = scraper
        self.profile_manager = SiteProfileManager()
    
    def extract_article_content(self, soup: BeautifulSoup, article_url: str) -> Dict[str, Any]:
        """Extract article content from a full article page with quality validation"""
        result = {
            'title': '',
            'content': '',
            'image_url': '',
            'published': None,
            'author': '',
            'category': '',
            'quality_validation': {}
        }
        
        # Extract title
        result['title'] = self._extract_title(soup)
        logger.debug(f"Extracted title: {result['title'][:50]}...")
        
        # Extract content
        result['content'] = self._extract_content(soup)
        logger.debug(f"Extracted content: {len(result['content'])} characters")
        
        # Validate content quality
        quality_validation = self._validate_content_quality(result['content'], result['title'])
        result['quality_validation'] = quality_validation
        
        if not quality_validation['is_valid']:
            logger.warning(f"Content quality issues for {article_url}: {quality_validation['issues']}")
        else:
            logger.debug(f"Content quality score: {quality_validation['quality_score']:.2f}")
        
        # Extract image
        result['image_url'] = self._extract_image(soup, article_url, result['title'])
        logger.debug(f"Extracted image: {result['image_url'][:50]}...")
        
        # Extract metadata
        result['published'] = self._extract_published_date(soup)
        result['author'] = self._extract_author(soup)
        result['category'] = self._extract_category(soup)
        
        return result
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract article title with multiple fallback strategies"""
        # Strategy 1: Open Graph title
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        if og_title and og_title.get('content'):
            return self.scraper.clean_text(og_title['content'])
        
        # Strategy 2: Twitter Card title
        twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
        if twitter_title and twitter_title.get('content'):
            return self.scraper.clean_text(twitter_title['content'])
        
        # Strategy 3: H1 tag
        h1 = soup.find('h1')
        if h1:
            title = self.scraper.clean_text(h1.get_text())
            if title and len(title) > 10:  # Reasonable title length
                return title
        
        # Strategy 4: Article title classes
        title_selectors = [
            '.article-title',
            '.news-title',
            '.post-title',
            '.entry-title',
            '[class*="title"]'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = self.scraper.clean_text(title_elem.get_text())
                if title and len(title) > 10:
                    return title
        
        # Strategy 5: Largest heading
        headings = soup.find_all(['h1', 'h2', 'h3'])
        if headings:
            largest_heading = max(headings, key=lambda h: len(h.get_text()))
            title = self.scraper.clean_text(largest_heading.get_text())
            if title and len(title) > 10:
                return title
        
        return ""
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract article content with multiple fallback strategies"""
        # Strategy 1: Article tag
        article = soup.find('article')
        if article:
            content = self._extract_text_from_element(article)
            if content and len(content) > 100:  # Reasonable content length
                return content
        
        # Strategy 2: Article content classes
        content_selectors = [
            '.article-content',
            '.news-content',
            '.post-content',
            '.entry-content',
            '[class*="content"]',
            '[class*="article"]',
            '[class*="news"]'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                content = self._extract_text_from_element(content_elem)
                if content and len(content) > 100:
                    return content
        
        # Strategy 3: Largest div with paragraphs
        divs_with_paragraphs = soup.find_all('div')
        content_divs = []
        
        for div in divs_with_paragraphs:
            paragraphs = div.find_all('p')
            if len(paragraphs) >= 3:  # At least 3 paragraphs
                content = self._extract_text_from_element(div)
                if content and len(content) > 100:
                    content_divs.append((content, len(content)))
        
        if content_divs:
            # Return content from div with most text
            content_divs.sort(key=lambda x: x[1], reverse=True)
            return content_divs[0][0]
        
        return ""
    
    def _extract_text_from_element(self, element) -> str:
        """Extract clean text from an HTML element"""
        if not element:
            return ""
        
        # Remove script and style elements
        for tag_name in ["script", "style", "nav", "footer", "header", "aside"]:
            for tag in element.find_all(tag_name):
                tag.decompose()
        
        # Get text and clean it
        text = element.get_text()
        return self.scraper.clean_text(text)
    
    def _extract_image(self, soup: BeautifulSoup, article_url: str, title: str = "") -> str:
        """Extract article image while avoiding default/placeholder images and preferring title-related ones"""
        # Strategy 1: Open Graph image
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        if og_image and og_image.get('content'):
            img_url = urljoin(article_url, og_image['content'])
            if self._is_valid_image_url(img_url) and not self._looks_like_default_image(img_url):
                if not title or self._is_related_to_title(img_url, title):
                    return img_url
        
        # Strategy 2: Twitter Card image
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            img_url = urljoin(article_url, twitter_image['content'])
            if self._is_valid_image_url(img_url) and not self._looks_like_default_image(img_url):
                if not title or self._is_related_to_title(img_url, title):
                    return img_url
        
        # Strategy 3: First large image in article content
        article = soup.find('article')
        if article:
            images = article.find_all('img')
            for img in images:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                if src and self._is_valid_image_url(src) and not self._looks_like_default_image(src):
                    # Check if image is reasonably sized (not a tiny icon)
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
                        # If no size info, assume it's okay if it's in article and looks related
                        if not title or self._is_related_to_title(src, title):
                            return urljoin(article_url, src)
        
        # Strategy 4: Schema.org image
        schema_image = soup.find('meta', attrs={'property': 'image'})
        if schema_image and schema_image.get('content'):
            img_url = urljoin(article_url, schema_image['content'])
            if self._is_valid_image_url(img_url) and not self._looks_like_default_image(img_url):
                if not title or self._is_related_to_title(img_url, title):
                    return img_url
        
        return ""
    
    def _is_valid_image_url(self, url: str) -> bool:
        """Check if URL looks like a valid image"""
        if not url:
            return False
        
        # Skip data URLs and very short URLs
        if url.startswith('data:') or len(url) < 10:
            return False
        
        # Skip common non-image and placeholder patterns
        skip_patterns = [
            'logo', 'icon', 'avatar', 'profile', 'banner', 'advertisement', 'ad-', 'ads/', 'sponsor',
            'social', 'share', 'button', 'arrow', 'bullet', 'dot', 'pixel', 'tracking', 'beacon',
            'placeholder', 'place-holder', 'noimage', 'no-image', 'default', 'dummy', 'blank', 'fallback',
            '/assets/web/images/default', '/defaults/', '/static/img/default', '/img/default'
        ]
        
        url_lower = url.lower()
        for pattern in skip_patterns:
            if pattern in url_lower:
                return False
        
        # Must be HTTP/HTTPS
        return url.startswith('http://') or url.startswith('https://')

    def _looks_like_default_image(self, url: str) -> bool:
        """Heuristic check for default/placeholder images by URL patterns"""
        u = url.lower()
        default_markers = [
            'default.png', 'default.jpg', 'placeholder', 'noimage', 'no-image', '/assets/web/images/default',
            '/img/default', '/images/default', '/static/default', 'generic', 'blank'
        ]
        return any(marker in u for marker in default_markers)

    def _is_related_to_title(self, url: str, title: str) -> bool:
        """Prefer images whose URL contains words from the title (>=4 chars). Not strict, used for ranking."""
        try:
            if not title:
                return True
            u = url.lower()
            # Extract candidate tokens from title
            tokens = [t for t in re.split(r"[^a-zA-ZçğıöşüÇĞİÖŞÜ0-9]+", title.lower()) if len(t) >= 4]
            if not tokens:
                return True
            return any(t in u for t in tokens)
        except Exception:
            return True
    
    def _extract_published_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract article publication date"""
        # Strategy 1: Open Graph published time
        og_published = soup.find('meta', attrs={'property': 'article:published_time'})
        if og_published and og_published.get('content'):
            try:
                return datetime.fromisoformat(og_published['content'].replace('Z', '+00:00'))
            except:
                pass
        
        # Strategy 2: Schema.org datePublished
        schema_date = soup.find('meta', attrs={'property': 'datePublished'})
        if schema_date and schema_date.get('content'):
            try:
                return datetime.fromisoformat(schema_date['content'].replace('Z', '+00:00'))
            except:
                pass
        
        # Strategy 3: Time tag
        time_tag = soup.find('time')
        if time_tag:
            datetime_attr = time_tag.get('datetime')
            if datetime_attr:
                try:
                    return datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                except:
                    pass
        
        return None
    
    def _extract_author(self, soup: BeautifulSoup) -> str:
        """Extract article author"""
        # Strategy 1: Open Graph author
        og_author = soup.find('meta', attrs={'property': 'article:author'})
        if og_author and og_author.get('content'):
            return self.scraper.clean_text(og_author['content'])
        
        # Strategy 2: Author classes
        author_selectors = [
            '.author',
            '.byline',
            '.writer',
            '[class*="author"]'
        ]
        
        for selector in author_selectors:
            author_elem = soup.select_one(selector)
            if author_elem:
                author = self.scraper.clean_text(author_elem.get_text())
                if author:
                    return author
        
        return ""
    
    def _extract_category(self, soup: BeautifulSoup) -> str:
        """Extract article category"""
        # Strategy 1: Open Graph section
        og_section = soup.find('meta', attrs={'property': 'article:section'})
        if og_section and og_section.get('content'):
            return self.scraper.clean_text(og_section['content'])
        
        # Strategy 2: Category classes
        category_selectors = [
            '.category',
            '.section',
            '.tag',
            '[class*="category"]'
        ]
        
        for selector in category_selectors:
            category_elem = soup.select_one(selector)
            if category_elem:
                category = self.scraper.clean_text(category_elem.get_text())
                if category:
                    return category
        
        return ""
    
    def _validate_content_quality(self, content: str, title: str = "") -> Dict[str, Any]:
        """Validate content quality and return quality metrics"""
        if not content:
            return {
                'is_valid': False,
                'quality_score': 0.0,
                'issues': ['Empty content'],
                'word_count': 0,
                'paragraph_count': 0
            }
        
        issues = []
        quality_score = 1.0
        
        # Word count validation
        words = content.split()
        word_count = len(words)
        
        if word_count < 50:
            issues.append(f'Too short: {word_count} words (minimum 50)')
            quality_score -= 0.4
        elif word_count < 100:
            issues.append(f'Short content: {word_count} words')
            quality_score -= 0.2
        
        # Paragraph count validation
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        paragraph_count = len(paragraphs)
        
        if paragraph_count < 2:
            issues.append(f'Too few paragraphs: {paragraph_count}')
            quality_score -= 0.3
        elif paragraph_count < 3:
            issues.append(f'Few paragraphs: {paragraph_count}')
            quality_score -= 0.1
        
        # Check for boilerplate text
        boilerplate_indicators = [
            'cookie policy',
            'privacy policy',
            'terms of service',
            'all rights reserved',
            'copyright',
            'follow us on',
            'subscribe to',
            'newsletter',
            'advertisement',
            'sponsored content'
        ]
        
        content_lower = content.lower()
        boilerplate_found = [indicator for indicator in boilerplate_indicators if indicator in content_lower]
        if boilerplate_found:
            issues.append(f'Contains boilerplate: {", ".join(boilerplate_found)}')
            quality_score -= 0.2
        
        # Check for repetitive content
        if len(set(words)) < len(words) * 0.3:  # Less than 30% unique words
            issues.append('High repetition in content')
            quality_score -= 0.2
        
        # Check if content seems to match title
        if title:
            title_words = set(title.lower().split())
            content_words = set(content.lower().split())
            common_words = title_words.intersection(content_words)
            if len(common_words) < 2:
                issues.append('Content may not match title')
                quality_score -= 0.1
        
        return {
            'is_valid': quality_score >= 0.5,
            'quality_score': max(0.0, quality_score),
            'issues': issues,
            'word_count': word_count,
            'paragraph_count': paragraph_count
        }

class ScraperToDatabase:
    """Main class for processing web scraping and storing in database"""
    
    def __init__(self, db_path: str = 'rss_articles.db'):
        # Resolve paths relative to script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        resolved_db_path = db_path if os.path.isabs(db_path) else os.path.join(script_dir, db_path)
        self.db = RSSDatabase(resolved_db_path)
        self.scraper = WebScraper()
        self.listing_parser = ArticleListingParser(self.scraper)
        self.content_parser = ArticleContentParser(self.scraper)
    
    def read_sources_from_file(self, file_path: str) -> List[str]:
        """Read scraper source URLs from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            logger.info(f"Loaded {len(urls)} scraper source URLs from {file_path}")
            return urls
        except Exception as e:
            logger.error(f"Error reading scraper list file {file_path}: {e}")
            return []
    
    def process_sources_to_database(self, sources_list_file: str = 'scrapeList.txt', max_articles_per_source: int = 5) -> Dict[str, Any]:
        """Process all scraper sources and store articles in database"""
        # Resolve sources_list_file path relative to script location
        if not os.path.isabs(sources_list_file):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            sources_list_file = os.path.join(script_dir, sources_list_file)
        
        logger.info(f"Starting web scraping to database processing (max {max_articles_per_source} articles per source)...")
        
        start_time = datetime.now()
        self.scraper.scraping_results['processing_start_time'] = start_time
        
        total_stats = {
            'sources_processed': 0,
            'sources_successful': 0,
            'sources_failed': 0,
            'total_articles_found': 0,
            'new_articles_added': 0,
            'duplicates_skipped': 0,
            'short_content_skipped': 0,
            'errors': 0,
            'processing_time': 0
        }
        
        try:
            # Get source URLs
            source_urls = self.read_sources_from_file(sources_list_file)
            total_stats['sources_processed'] = len(source_urls)
            
            logger.info(f"Processing {len(source_urls)} scraper sources...")
            
            for i, source_url in enumerate(source_urls, 1):
                source_start_time = datetime.now()
                logger.info(f"Processing source {i}/{len(source_urls)}: {source_url}")
                
                source_info = {
                    'url': source_url,
                    'attempts': 0,
                    'errors': [],
                    'status': None,
                    'article_count': 0,
                    'success': False
                }
                
                try:
                    # Fetch listing page
                    soup = self.scraper.fetch_page(source_url)
                    if not soup:
                        logger.error(f"Failed to fetch source: {source_url}")
                        total_stats['sources_failed'] += 1
                        source_info['errors'].append('Failed to fetch page')
                        self.scraper.scraping_results['failed_sources'].append(source_info)
                        continue
                    
                    # Extract article URLs
                    article_urls = self.listing_parser.extract_article_urls(soup, source_url, max_articles=max_articles_per_source)
                    total_stats['total_articles_found'] += len(article_urls)
                    
                    logger.info(f"Found {len(article_urls)} article URLs")
                    
                    # Process each article
                    articles_added = 0
                    duplicates_skipped = 0
                    short_content_skipped = 0
                    
                    for article_url in article_urls:
                        try:
                            # Check if URL already exists
                            if self.scraper.check_url_exists(article_url, self.db):
                                logger.debug(f"Article already exists, skipping: {article_url}")
                                duplicates_skipped += 1
                                continue
                            
                            # Fetch article page
                            article_soup = self.scraper.fetch_page(article_url)
                            if not article_soup:
                                logger.warning(f"Failed to fetch article: {article_url}")
                                continue
                            
                            # Extract article content
                            article_data = self.content_parser.extract_article_content(article_soup, article_url)
                            
                            # Check content length threshold
                            content_length = len(article_data['content'])
                            if MIN_CONTENT_LENGTH_THRESHOLD > 0 and content_length < MIN_CONTENT_LENGTH_THRESHOLD:
                                logger.warning(f"Skipping article due to short content ({content_length} chars < {MIN_CONTENT_LENGTH_THRESHOLD} threshold): {article_data['title'][:50]}...")
                                short_content_skipped += 1
                                continue
                            
                            # Create RSSArticle object
                            article = RSSArticle()
                            article.title = article_data['title']
                            article.content = article_data['content']
                            article.description = article_data['content'][:500] + "..." if len(article_data['content']) > 500 else article_data['content']
                            article.summary = article_data['content'][:200] + "..." if len(article_data['content']) > 200 else article_data['content']
                            article.link = article_url
                            article.guid = article_url  # Use URL as GUID for duplicate detection
                            article.published = article_data['published'] or datetime.now(timezone.utc)
                            article.author = article_data['author']
                            article.category = article_data['category']
                            article.image_url = article_data['image_url']
                            article.image_urls = [article_data['image_url']] if article_data['image_url'] else []
                            
                            # Set source information
                            domain = urlparse(source_url).netloc
                            article.source_name = f"SCRAPED: {domain}"
                            article.source_url = source_url
                            article.feed_url = article_url
                            
                            # Insert into database
                            if self.db.insert_article(article):
                                articles_added += 1
                                logger.info(f"Added article: {article.title[:50]}... ({content_length} chars)")
                            else:
                                duplicates_skipped += 1
                                logger.debug(f"Article already exists (content hash): {article.title[:50]}...")
                            
                        except Exception as e:
                            logger.error(f"Error processing article {article_url}: {e}")
                            total_stats['errors'] += 1
                            continue
                    
                    # Update statistics
                    total_stats['new_articles_added'] += articles_added
                    total_stats['duplicates_skipped'] += duplicates_skipped
                    total_stats['short_content_skipped'] += short_content_skipped
                    
                    # Update source info
                    source_info['article_count'] = articles_added
                    source_info['success'] = True
                    source_info['status'] = 200
                    self.scraper.scraping_results['successful_sources'].append(source_info)
                    
                    # Track articles by source
                    domain = urlparse(source_url).netloc
                    self.scraper.scraping_results['articles_by_source'][domain] = \
                        self.scraper.scraping_results['articles_by_source'].get(domain, 0) + articles_added
                    
                    total_stats['sources_successful'] += 1
                    
                    logger.info(f"Source {source_url}: {articles_added} new, {duplicates_skipped} duplicates, {short_content_skipped} short content skipped")
                    
                except Exception as e:
                    logger.error(f"Error processing source {source_url}: {e}")
                    total_stats['sources_failed'] += 1
                    source_info['errors'].append(str(e))
                    self.scraper.scraping_results['failed_sources'].append(source_info)
                    continue
                
                # Small delay between requests
                time.sleep(1)
            
            # Calculate total processing time
            total_stats['processing_time'] = (datetime.now() - start_time).total_seconds()
            self.scraper.scraping_results['processing_end_time'] = datetime.now()
            self.scraper.scraping_results['total_articles'] = total_stats['new_articles_added']
            
            logger.info("Web scraping to database processing completed!")
            return total_stats
            
        except Exception as e:
            logger.error(f"Error in web scraping to database processing: {e}")
            total_stats['processing_time'] = (datetime.now() - start_time).total_seconds()
            return total_stats
    
    def print_processing_summary(self, stats: Dict[str, Any]):
        """Print processing summary"""
        print(f"\n{'='*60}")
        print(f"WEB SCRAPING TO DATABASE PROCESSING SUMMARY")
        print(f"{'='*60}")
        print(f"Sources processed: {stats['sources_processed']}")
        print(f"Successful sources: {stats['sources_successful']}")
        print(f"Failed sources: {stats['sources_failed']}")
        print(f"Total articles found: {stats['total_articles_found']}")
        print(f"New articles added: {stats['new_articles_added']}")
        print(f"Duplicates skipped: {stats['duplicates_skipped']}")
        print(f"Short content skipped: {stats['short_content_skipped']}")
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
        
        # Recent articles
        recent_articles = self.db.get_recent_articles(5)
        if recent_articles:
            print(f"\nRecent articles (last 5):")
            print(f"{'='*40}")
            for i, article in enumerate(recent_articles, 1):
                print(f"{i}. {article['title'][:60]}...")
                print(f"   Source: {article['source_name']}")
                print(f"   Added: {article['created_at']}")
                print()

def run(sources_list_file: str = 'scrapeList.txt', db_path: str = 'rss_articles.db', max_articles_per_source: int = None) -> Dict[str, Any]:
    """Run web scraping to database processing with optional parameters"""
    if max_articles_per_source is None:
        max_articles_per_source = MAX_ARTICLES_PER_SOURCE
    scraper2db = ScraperToDatabase(db_path)
    stats = scraper2db.process_sources_to_database(sources_list_file, max_articles_per_source=max_articles_per_source)
    scraper2db.print_processing_summary(stats)
    return stats

def main():
    """Main function to run web scraping to database processing"""
    import sys
    
    # Parse command line arguments (optional override)
    max_articles = MAX_ARTICLES_PER_SOURCE  # Use configuration flag by default
    if len(sys.argv) > 1:
        try:
            max_articles = int(sys.argv[1])
            if max_articles < 1:
                print(f"Warning: max_articles must be >= 1. Using configured value of {MAX_ARTICLES_PER_SOURCE}.")
                max_articles = MAX_ARTICLES_PER_SOURCE
            else:
                print(f"Using command-line override: {max_articles} articles per source")
        except ValueError:
            print(f"Warning: '{sys.argv[1]}' is not a valid integer. Using configured value of {MAX_ARTICLES_PER_SOURCE}.")
            max_articles = MAX_ARTICLES_PER_SOURCE
    else:
        print(f"Using configuration flag: {MAX_ARTICLES_PER_SOURCE} articles per source")
        print("(Edit MAX_ARTICLES_PER_SOURCE at line 42 to change this)")
    
    scraper2db = ScraperToDatabase()
    
    # Process sources and store in database
    stats = scraper2db.process_sources_to_database(max_articles_per_source=max_articles)
    
    # Print summary
    scraper2db.print_processing_summary(stats)
    
    # Show some recent articles
    recent_articles = scraper2db.db.get_recent_articles(3)
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
            
            # Display image URLs
            if article.get('image_urls'):
                try:
                    image_urls = json.loads(article['image_urls'])
                    if image_urls:
                        print(f"Images found: {len(image_urls)}")
                        for idx, img_url in enumerate(image_urls[:2], 1):  # Show first 2
                            print(f"  Image {idx}: {img_url[:80]}...")
                except:
                    pass

if __name__ == "__main__":
    main()
