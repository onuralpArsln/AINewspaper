#!/usr/bin/env python3
"""
AI Writer for RSS Articles
Uses Gemini AI to rewrite and unify articles from rss_articles.db

WORKFLOW:
1. Generates a target number of OUTPUT articles (set by ARTICLE_COUNT or --max-articles)
2. For each OUTPUT article:
   - Gets next unread article from rss_articles.db (newest first)
   - Checks if it has images (if ONLY_IMAGES flag is True)
   - If article is in a group, reads ALL articles in that group (e.g., 12 articles)
   - Merges all articles in the group and sends to Gemini AI
   - Follows rules from writer_prompt.txt
   - Generates 1 OUTPUT article: Title, Description, Body, Tags (categories + locations)
   - Marks ALL source articles as read (is_read = 1)
3. Continues until target number of OUTPUT articles is generated
4. Tracks processed groups to avoid duplicates

IMPORTANT: ARTICLE_COUNT = number of OUTPUT articles to GENERATE, not input articles to process
Example: If ARTICLE_COUNT=10, you get 10 articles in our_articles.db
         Even if a group contains 12 source articles, it generates 1 output article

IMAGE HANDLING:
- Checks all image sources: image_urls (consolidated), enclosures, media_content
- Collects unique images from all sources
- Validates and filters image URLs

USAGE:
    python ai_writer.py                    # Generate ARTICLE_COUNT output articles
    python ai_writer.py --max-articles 20  # Generate 20 output articles
    python ai_writer.py --stats            # Show statistics only
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from google import genai
import logging
import requests
from PIL import Image
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION FLAGS - Modify these to control AI writer behavior
# ============================================================================
ONLY_IMAGES = True  # Set to True to only process articles with images
ARTICLE_COUNT = 5   # Number of articles to produce per run
# Validation mode: when False (default), allow semantic rephrasing and rely on prompt; keep minimal safeguards
STRICT_FACT_VALIDATION = False
# ============================================================================

class AIWriter:
    """AI-powered article writer using Gemini"""
    
    def __init__(self, rss_db_path: str = 'rss_articles.db', our_articles_db_path: str = 'our_articles.db'):
        # Resolve paths relative to script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.rss_db_path = rss_db_path if os.path.isabs(rss_db_path) else os.path.join(script_dir, rss_db_path)
        self.our_articles_db_path = our_articles_db_path if os.path.isabs(our_articles_db_path) else os.path.join(script_dir, our_articles_db_path)
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
            script_dir = os.path.dirname(os.path.abspath(__file__))
            prompt_path = os.path.join(script_dir, 'writer_prompt.txt')
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error("writer_prompt.txt not found!")
            return "You are a seasoned journalist. Rewrite the given news articles in a professional tone."
    
    def _init_databases(self):
        """Initialize both databases with required schemas"""
        # Initialize RSS database with read status and event grouping
        with sqlite3.connect(self.rss_db_path) as conn:
            cursor = conn.cursor()
            
            # Check existing columns
            cursor.execute("PRAGMA table_info(articles)")
            existing_columns = [column[1] for column in cursor.fetchall()]
            
            # Add read status column if it doesn't exist
            if 'is_read' not in existing_columns:
                try:
                    cursor.execute('ALTER TABLE articles ADD COLUMN is_read BOOLEAN DEFAULT 0')
                    logger.info("Added is_read column to RSS articles table")
                    conn.commit()
                except sqlite3.OperationalError as e:
                    logger.debug(f"is_read column might already exist: {e}")
            
            # Add event_group_id column if it doesn't exist
            if 'event_group_id' not in existing_columns:
                try:
                    cursor.execute('ALTER TABLE articles ADD COLUMN event_group_id INTEGER')
                    logger.info("Added event_group_id column to RSS articles table")
                    conn.commit()
                except sqlite3.OperationalError as e:
                    logger.debug(f"event_group_id column might already exist: {e}")
            
            # Add indexes for performance
            try:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_read ON articles(is_read, created_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_group_read ON articles(event_group_id, is_read)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_group_id ON articles(event_group_id)')
                conn.commit()
            except sqlite3.OperationalError as e:
                logger.debug(f"Indexes might already exist: {e}")
        
        # Initialize our articles database
        with sqlite3.connect(self.our_articles_db_path) as conn:
            cursor = conn.cursor()
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
            
            # Add category column if it doesn't exist (for existing databases)
            try:
                cursor.execute('ALTER TABLE our_articles ADD COLUMN category TEXT')
                logger.info("Added category column to our_articles table")
                conn.commit()
            except sqlite3.OperationalError as e:
                logger.debug(f"category column might already exist: {e}")
            
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
                # Only get articles with images (check all possible image columns)
                cursor.execute('''
                    SELECT * FROM articles 
                    WHERE is_read = 0 
                        AND (
                            (image_urls IS NOT NULL AND image_urls != '[]' AND image_urls != 'null' AND image_urls != '')
                            OR (media_content IS NOT NULL AND media_content != '[]' AND media_content != 'null' AND media_content != '')
                            OR (enclosures IS NOT NULL AND enclosures != '[]' AND enclosures != 'null' AND enclosures != '')
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
        """Check if at least one article in the group has images (checks all image sources)"""
        with self.get_connection(self.rss_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM articles 
                WHERE event_group_id = ? 
                    AND is_read = 0
                    AND (
                        (image_urls IS NOT NULL AND image_urls != '[]' AND image_urls != 'null' AND image_urls != '')
                        OR (media_content IS NOT NULL AND media_content != '[]' AND media_content != 'null' AND media_content != '')
                        OR (enclosures IS NOT NULL AND enclosures != '[]' AND enclosures != 'null' AND enclosures != '')
                    )
            ''', (group_id,))
            count = cursor.fetchone()[0]
            return count > 0
    
    def _collect_images_from_articles(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Collect all unique images from source articles (from all image sources)"""
        all_images = []
        
        for article in articles:
            # 1. Get images from unified image_urls column (primary source - already consolidated)
            if article.get('image_urls'):
                try:
                    image_urls = json.loads(article['image_urls'])
                    if isinstance(image_urls, list):
                        for img_url in image_urls:
                            if img_url and img_url.strip() and img_url not in all_images:
                                all_images.append(img_url)
                except (json.JSONDecodeError, TypeError):
                    logger.debug(f"Could not parse image_urls for article {article.get('id', 'unknown')}")
            
            # 2. Check enclosures (may contain image attachments)
            if article.get('enclosures'):
                try:
                    enclosures = json.loads(article['enclosures'])
                    if isinstance(enclosures, list):
                        for enclosure in enclosures:
                            if isinstance(enclosure, dict):
                                enc_type = enclosure.get('type', '')
                                if enc_type.startswith('image/'):
                                    img_url = enclosure.get('url', enclosure.get('href', ''))
                                    if img_url and img_url.strip() and img_url not in all_images:
                                        all_images.append(img_url)
                except (json.JSONDecodeError, TypeError):
                    logger.debug(f"Could not parse enclosures for article {article.get('id', 'unknown')}")
            
            # 3. Check media_content (JSON array with media information)
            if article.get('media_content'):
                try:
                    media_content = json.loads(article['media_content'])
                    if isinstance(media_content, list):
                        for media in media_content:
                            if isinstance(media, dict):
                                media_type = media.get('type', '')
                                if media_type.startswith('image/') or 'image' in media_type.lower():
                                    img_url = media.get('url', '')
                                    if img_url and img_url.strip() and img_url not in all_images:
                                        all_images.append(img_url)
                except (json.JSONDecodeError, TypeError):
                    logger.debug(f"Could not parse media_content for article {article.get('id', 'unknown')}")
        
        logger.info(f"Collected {len(all_images)} unique images from {len(articles)} articles")
        return all_images
    
    def _get_image_resolution(self, image_url: str, timeout: int = 5) -> Tuple[Optional[int], Optional[int]]:
        """
        Get image resolution (width, height) from URL
        Returns (width, height) or (None, None) if failed
        """
        try:
            # Fetch image with timeout
            response = requests.get(image_url, timeout=timeout, stream=True)
            response.raise_for_status()
            
            # Open image and get dimensions
            img = Image.open(BytesIO(response.content))
            width, height = img.size
            logger.debug(f"Image resolution: {width}x{height} - {image_url[:60]}...")
            return width, height
            
        except requests.exceptions.Timeout:
            logger.debug(f"Timeout fetching image: {image_url[:60]}...")
            return None, None
        except requests.exceptions.RequestException as e:
            logger.debug(f"Error fetching image: {e} - {image_url[:60]}...")
            return None, None
        except Exception as e:
            logger.debug(f"Error processing image: {e} - {image_url[:60]}...")
            return None, None
    
    def _sort_images_by_resolution(self, image_urls: List[str], min_resolution: int = 40000) -> List[str]:
        """
        Sort images by resolution (highest first) and filter out small images
        
        Args:
            image_urls: List of image URLs
            min_resolution: Minimum resolution (width * height) to keep (default: 40000 = 200x200)
        
        Returns:
            List of image URLs sorted by resolution (highest to lowest)
        """
        if not image_urls:
            return []
        
        logger.info(f"Sorting {len(image_urls)} images by resolution...")
        
        # Get resolution for each image
        image_data = []
        for url in image_urls:
            width, height = self._get_image_resolution(url)
            if width and height:
                resolution = width * height
                # Only keep images that meet minimum resolution
                if resolution >= min_resolution:
                    image_data.append({
                        'url': url,
                        'width': width,
                        'height': height,
                        'resolution': resolution
                    })
                else:
                    logger.debug(f"Filtered out low-res image ({width}x{height}): {url[:60]}...")
            else:
                logger.debug(f"Could not get resolution for: {url[:60]}...")
        
        # Sort by resolution (highest first)
        image_data.sort(key=lambda x: x['resolution'], reverse=True)
        
        # Extract sorted URLs
        sorted_urls = [img['url'] for img in image_data]
        
        if sorted_urls:
            logger.info(f"Sorted images: kept {len(sorted_urls)}/{len(image_urls)} images")
            logger.info(f"Best image: {image_data[0]['width']}x{image_data[0]['height']} ({image_data[0]['resolution']:,} pixels)")
            if len(image_data) > 1:
                logger.info(f"Worst image: {image_data[-1]['width']}x{image_data[-1]['height']} ({image_data[-1]['resolution']:,} pixels)")
        else:
            logger.warning(f"No valid images found after resolution sorting")
        
        return sorted_urls
    
    def prepare_articles_for_ai(self, articles: List[Dict[str, Any]]) -> str:
        """Prepare articles text for AI processing with enhanced source tracking"""
        if not articles:
            return ""
        
        if len(articles) == 1:
            # Single article
            article = articles[0]
            return f"""
SOURCE ARTICLE (ID: {article.get('id', 'N/A')}):
Title: {article.get('title', 'N/A')}
Source: {article.get('source_name', 'N/A')}
Published: {article.get('published', 'N/A')}
Content: {article.get('description', article.get('content', 'N/A'))}
Link: {article.get('link', 'N/A')}

IMPORTANT: Use ONLY the information provided above. Do not add any facts, details, or information not explicitly stated in this source article.
"""
        else:
            # Multiple articles (group)
            text = f"MULTIPLE SOURCE ARTICLES about the same event (Group ID: {articles[0]['event_group_id']}):\n\n"
            for i, article in enumerate(articles, 1):
                text += f"SOURCE ARTICLE {i} (ID: {article.get('id', 'N/A')}):\n"
                text += f"Title: {article.get('title', 'N/A')}\n"
                text += f"Source: {article.get('source_name', 'N/A')}\n"
                text += f"Published: {article.get('published', 'N/A')}\n"
                text += f"Content: {article.get('description', article.get('content', 'N/A'))}\n"
                text += f"Link: {article.get('link', 'N/A')}\n\n"
            
            text += "IMPORTANT: Use ONLY the information provided in the source articles above. Do not add any facts, details, or information not explicitly stated in these source articles. If sources conflict, present both versions clearly."
            return text
    
    def generate_article_with_ai(self, articles_text: str) -> Optional[Dict[str, str]]:
        """Generate article using Gemini AI with enhanced prompt for category and tags"""
        try:
            # Enhanced prompt to specifically request category selection and tags
            enhanced_prompt = f"""{self.writer_prompt}

CRITICAL ANTI-HALLUCINATION INSTRUCTIONS:
- You MUST only use information explicitly provided in the source articles above
- Do NOT add any facts, numbers, dates, names, or details not present in the source material
- Do NOT speculate, infer, or make assumptions beyond what is directly stated
- If information is missing, write "bilgi mevcut değil" (information not available)
- Preserve all specific details exactly as provided in the source articles
- If sources conflict, present both versions clearly

IMPORTANT CATEGORY AND TAGS FORMAT:
- Select ONE main category from: gündem, ekonomi, spor, siyaset, magazin, yaşam, eğitim, sağlık, astroloji
- Generate additional tags as a JSON array (not comma-separated)
- Include geographic location (city or country mentioned in the article)
- Include other relevant keywords
- Example output:
  Category: spor
  Tags: ["futbol", "İstanbul", "şampiyonluk", "galatasaray", "derbi"]

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
    
    def _validate_factual_accuracy(self, article_data: Dict[str, str], source_articles: List[Dict[str, Any]]) -> bool:
        """Minimal-safe validation: allow semantic rephrasing; block only explicit hallucination patterns.

        In non-strict mode (STRICT_FACT_VALIDATION=False):
        - Do not compare large sets of words/entities/numbers.
        - Fail only if forbidden phrases appear that are not in sources.
        - Warn (do not fail) if title anchor entities seem missing.
        """
        try:
            import re

            if not STRICT_FACT_VALIDATION:
                # Merge source text for phrase checks
                source_text = " ".join([
                    f"{a.get('title','')} {a.get('description','')} {a.get('content','')}" for a in source_articles
                ]).lower()

                generated_content = f"{article_data.get('title','')} {article_data.get('summary','')} {article_data.get('body','')}".lower()

                # Forbidden hallucination cues that must not appear unless present in sources
                forbidden_phrases = [
                    "kaynaklara göre", "uzmanlara göre", "iddialara göre", "henüz doğrulanmayan",
                    "resmi olmayan", "güvenilir kaynaklar", "kulislere göre"
                ]

                for phrase in forbidden_phrases:
                    if phrase in generated_content and phrase not in source_text:
                        logger.warning(f"Generated article contains forbidden phrase not in sources: '{phrase}'")
                        return False

                # Warn-only: ensure title anchor tokens present
                titles = " ".join([a.get('title','') for a in source_articles])
                # Extract simple anchor tokens from titles (capitalized words, >=3 chars)
                title_tokens = set(re.findall(r"\b[A-ZÇĞIİÖŞÜ][a-zçğıiöşü]{2,}\b", titles))
                missing = []
                for tok in title_tokens:
                    if tok.lower() not in generated_content:
                        missing.append(tok)
                if len(missing) > 0:
                    logger.info(f"Title anchor tokens possibly missing (warn-only): {missing[:5]}")

                return True

            # STRICT mode (debug): basic check only; still avoid broad count diffs
            source_text = " ".join([
                f"{a.get('title','')} {a.get('description','')} {a.get('content','')}" for a in source_articles
            ]).lower()
            generated_content = f"{article_data.get('title','')} {article_data.get('summary','')} {article_data.get('body','')}".lower()
            forbidden_phrases = []
            
            for phrase in forbidden_phrases:
                if phrase in generated_content and phrase not in source_text:
                    logger.warning(f"[STRICT] Forbidden phrase not in sources: '{phrase}'")
                    return False
            return True

        except Exception as e:
            logger.error(f"Error validating factual accuracy: {e}")
            return True  # Allow article if validation fails
    
    def _parse_ai_response(self, response_text: str) -> Optional[Dict[str, str]]:
        """Parse AI response into structured format with category and tags"""
        try:
            import re
            lines = response_text.strip().split('\n')
            article_data = {}
            facts_used = []
            
            current_section = None
            current_content = []
            
            # Helper function to check if line matches field patterns
            def matches_field(line, field_name, turkish_name=None):
                # Remove markdown artifacts and normalize
                clean_line = re.sub(r'^\*+\s*|\s*\*+$|^`+\s*|\s*`+$', '', line.strip())
                # Check for various patterns: "Title:", "Title -", "**Title:**", "Başlık:", etc.
                patterns = [
                    rf'^\*?\*?\s*{field_name}\s*[:\\-]\s*',
                    rf'^\*?\*?\s*{field_name}\s*[:\\-]\s*',
                ]
                if turkish_name:
                    patterns.extend([
                        rf'^\*?\*?\s*{turkish_name}\s*[:\\-]\s*',
                        rf'^\*?\*?\s*{turkish_name}\s*[:\\-]\s*',
                    ])
                
                for pattern in patterns:
                    if re.match(pattern, clean_line, re.IGNORECASE):
                        return True, clean_line
                return False, clean_line
            
            for line in lines:
                line = line.strip()
                # Capture optional self-audit facts section
                if line.startswith('Facts Used'):
                    # Accumulate the JSON block on the same or following lines
                    current_section = 'facts'
                    current_content = [line.split(':',1)[1].strip()] if ':' in line else []
                elif current_section == 'facts' and (line.startswith('[') or line.startswith('{') or line.endswith(']') or line.endswith('}')):
                    current_content.append(line)
                elif current_section == 'facts' and line and not any(matches_field(line, field)[0] for field in ['Title', 'Summary', 'Body', 'Category', 'Tags']):
                    current_content.append(line)
                elif matches_field(line, 'Title', 'Başlık')[0]:
                    if current_section and current_content:
                        if current_section == 'facts':
                            try:
                                facts_text = '\n'.join(current_content).strip()
                                facts_used = json.loads(facts_text)
                            except Exception:
                                facts_used = []
                        else:
                            article_data[current_section] = '\n'.join(current_content).strip()
                    current_section = 'title'
                    # Extract content after the field marker
                    _, clean_line = matches_field(line, 'Title', 'Başlık')
                    content = re.sub(r'^(title|başlık)\s*[:\\-]\s*', '', clean_line, flags=re.IGNORECASE).strip()
                    current_content = [content] if content else []
                elif matches_field(line, 'Summary', 'Özet')[0]:
                    if current_section and current_content:
                        if current_section == 'facts':
                            try:
                                facts_text = '\n'.join(current_content).strip()
                                facts_used = json.loads(facts_text)
                            except Exception:
                                facts_used = []
                        else:
                            article_data[current_section] = '\n'.join(current_content).strip()
                    current_section = 'summary'
                    # Extract content after the field marker
                    _, clean_line = matches_field(line, 'Summary', 'Özet')
                    content = re.sub(r'^(summary|özet)\s*[:\\-]\s*', '', clean_line, flags=re.IGNORECASE).strip()
                    current_content = [content] if content else []
                elif matches_field(line, 'Body', 'İçerik')[0]:
                    if current_section and current_content:
                        if current_section == 'facts':
                            try:
                                facts_text = '\n'.join(current_content).strip()
                                facts_used = json.loads(facts_text)
                            except Exception:
                                facts_used = []
                        else:
                            article_data[current_section] = '\n'.join(current_content).strip()
                    current_section = 'body'
                    # Extract content after the field marker
                    _, clean_line = matches_field(line, 'Body', 'İçerik')
                    content = re.sub(r'^(body|içerik)\s*[:\\-]\s*', '', clean_line, flags=re.IGNORECASE).strip()
                    current_content = [content] if content else []
                elif matches_field(line, 'Category', 'Kategori')[0]:
                    if current_section and current_content:
                        if current_section == 'facts':
                            try:
                                facts_text = '\n'.join(current_content).strip()
                                facts_used = json.loads(facts_text)
                            except Exception:
                                facts_used = []
                        else:
                            article_data[current_section] = '\n'.join(current_content).strip()
                    current_section = 'category'
                    # Extract content after the field marker
                    _, clean_line = matches_field(line, 'Category', 'Kategori')
                    content = re.sub(r'^(category|kategori)\s*[:\\-]\s*', '', clean_line, flags=re.IGNORECASE).strip()
                    current_content = [content] if content else []
                elif matches_field(line, 'Tags', 'Etiketler')[0]:
                    if current_section and current_content:
                        if current_section == 'facts':
                            try:
                                facts_text = '\n'.join(current_content).strip()
                                facts_used = json.loads(facts_text)
                            except Exception:
                                facts_used = []
                        else:
                            article_data[current_section] = '\n'.join(current_content).strip()
                    current_section = 'tags'
                    # Extract content after the field marker
                    _, clean_line = matches_field(line, 'Tags', 'Etiketler')
                    content = re.sub(r'^(tags|etiketler)\s*[:\\-]\s*', '', clean_line, flags=re.IGNORECASE).strip()
                    current_content = [content] if content else []
                elif line and current_section:
                    current_content.append(line)
            
            # Add the last section
            if current_section and current_content:
                if current_section == 'facts':
                    try:
                        facts_text = '\n'.join(current_content).strip()
                        facts_used = json.loads(facts_text)
                    except Exception:
                        facts_used = []
                else:
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
            
            # Log self-audit facts if provided
            if facts_used:
                try:
                    sample = facts_used[:5] if isinstance(facts_used, list) else str(facts_used)[:200]
                    logger.info(f"Self-audit facts used (sample): {sample}")
                except Exception:
                    pass

            # Validate and normalize category to canonical capitalized set
            canonical_categories = {
                'gündem': 'Gündem',
                'ekonomi': 'Ekonomi',
                'spor': 'Spor',
                'siyaset': 'Siyaset',
                'magazin': 'Magazin',
                'yaşam': 'Yaşam',
                'eğitim': 'Eğitim',
                'sağlık': 'Sağlık',
                'astroloji': 'Astroloji'
            }
            if 'category' in article_data and article_data['category']:
                raw_category = str(article_data['category']).strip().lower()
                article_data['category'] = canonical_categories.get(raw_category, 'Gündem')
                if article_data['category'] == 'Gündem' and raw_category not in canonical_categories:
                    logger.warning(f"Invalid category '{raw_category}', defaulting to 'Gündem'")
            else:
                # Default category if not provided
                article_data['category'] = 'Gündem'
            
            # Validate required fields (category is auto-fallbacked to 'Gündem')
            required_fields = ['title', 'body']
            missing_fields = [f for f in required_fields if not article_data.get(f) or not str(article_data.get(f)).strip()]
            if len(missing_fields) == 0:
                return article_data
            else:
                logger.warning(f"AI response missing required fields: {missing_fields}")
                # Log raw response and parsed data for debugging
                logger.warning(f"Raw AI response (first 500 chars): {response_text[:500]}")
                logger.warning(f"Parsed article_data keys: {list(article_data.keys())}")
                logger.warning(f"Parsed article_data values: {[(k, str(v)[:100] + '...' if len(str(v)) > 100 else v) for k, v in article_data.items()]}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            # Log raw response for debugging when parsing completely fails
            logger.error(f"Raw AI response (first 500 chars): {response_text[:500]}")
            return None
    
    def save_article(self, article_data: Dict[str, str], source_articles: List[Dict[str, Any]]) -> int:
        """Save generated article to our_articles database with all metadata"""
        with self.get_connection(self.our_articles_db_path) as conn:
            cursor = conn.cursor()
            
            # Prepare source tracking data
            source_group_id = source_articles[0].get('event_group_id') if source_articles[0].get('event_group_id') else None
            source_article_ids = [str(article['id']) for article in source_articles]
            source_ids_str = ','.join(source_article_ids)
            
            # Publication date: always use AI writer creation time in Istanbul (GMT+3)
            pub_date = (datetime.utcnow() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
            
            # Collect all images from source articles (from all three image columns)
            all_images = self._collect_images_from_articles(source_articles)
            
            # Sort images by resolution (highest first) with lenient filtering
            # min_resolution=0 keeps all images, just sorts them by quality
            if all_images:
                all_images = self._sort_images_by_resolution(all_images, min_resolution=0)
            
            images_json = json.dumps(all_images) if all_images else None
            
            # Extract data from AI response
            title = article_data.get('title', '')
            summary = article_data.get('summary', '')
            body = article_data.get('body', '')
            category = article_data.get('category', 'Gündem')
            tags = article_data.get('tags', '[]')
            
            # Insert into our_articles
            cursor.execute('''
                INSERT INTO our_articles 
                (title, summary, body, category, tags, images, date, source_group_id, source_article_ids, article_state, review_count, editors_note, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                title,
                summary,
                body,
                category,
                tags,
                images_json,
                pub_date,
                source_group_id,
                source_ids_str,
                'not_reviewed',  # article_state
                0,               # review_count
                None             # editors_note
            ))
            
            article_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"✓ Saved article ID {article_id}: '{title[:50]}...'")
            logger.info(f"  - Category: {category}, Tags: {tags}, Images: {len(all_images)}, Source IDs: {source_ids_str}")
            
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
        Main processing function that generates a target number of OUTPUT articles.
        For each output article:
        1. Get next unread article from RSS database
        2. Check if it's part of a group - if yes, read all articles in the group
        3. Send to Gemini AI for rewriting
        4. Save to our_articles.db (1 output article)
        5. Mark all source articles as read
        6. Continue until max_articles OUTPUT articles are generated
        
        Note: max_articles = number of OUTPUT articles to generate, not input articles to process
        """
        # Use class-level article_count if max_articles not provided
        if max_articles is None:
            max_articles = self.article_count
        
        mode_str = "ONLY IMAGES mode" if self.only_images else "ALL ARTICLES mode"
        logger.info(f"Starting AI article writing process ({mode_str})...")
        logger.info(f"Target: Generate {max_articles} OUTPUT articles")
        
        generated_count = 0  # Number of output articles generated
        skipped_count = 0
        processed_groups = set()  # Track processed groups to avoid duplicates
        
        # Keep processing until we generate the target number of output articles
        while generated_count < max_articles:
            # Get next batch of unread articles (fetch more than needed to handle groups)
            batch_size = max(10, (max_articles - generated_count) * 2)
            articles_to_check = self.get_next_articles_to_process(batch_size)
            
            if not articles_to_check:
                logger.info(f"✓ No more unread articles found (generated {generated_count} articles)")
                break
            
            # Process articles until we reach our target
            article_processed_in_batch = False
            
            for article in articles_to_check:
                if generated_count >= max_articles:
                    break
                
                try:
                    article_id = article['id']
                    article_title = article['title'][:60]
                    group_id = article.get('event_group_id')
                    
                    # Skip if this group was already processed
                    if group_id and group_id > 0 and group_id in processed_groups:
                        logger.debug(f"Skipping article {article_id} - group {group_id} already processed")
                        continue
                    
                    # Skip if article is already read (might happen with groups)
                    if article.get('is_read'):
                        logger.debug(f"Skipping article {article_id} - already marked as read")
                        continue
                    
                    logger.info(f"\n{'='*80}")
                    logger.info(f"Processing article {article_id}: {article_title}...")
                    logger.info(f"Output article {generated_count + 1}/{max_articles}")
                    
                    # Check if article is part of a group
                    if group_id and group_id > 0:
                        # Article is part of a group - get ALL articles in the group
                        logger.info(f"Article is part of group {group_id}")
                        source_articles = self.get_group_articles(group_id)
                        logger.info(f"Merging {len(source_articles)} articles from group {group_id}")
                        processed_groups.add(group_id)  # Mark group as processed
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
                        # Validate factual accuracy before saving
                        logger.info("Validating factual accuracy...")
                        if self._validate_factual_accuracy(ai_article, source_articles):
                            # Save generated article with all images and metadata
                            saved_id = self.save_article(ai_article, source_articles)
                            
                            # Mark source articles as read
                            self.mark_articles_as_read(source_articles)
                            
                            generated_count += 1
                            article_processed_in_batch = True
                            logger.info(f"✓ Successfully generated output article {generated_count}/{max_articles} (ID: {saved_id})")
                            logger.info(f"  - Used {len(source_articles)} source article(s)")
                        else:
                            logger.warning("✗ Article failed factual accuracy validation - skipping")
                            skipped_count += 1
                    else:
                        logger.error("✗ Failed to generate article with AI")
                        skipped_count += 1
                        
                except Exception as e:
                    logger.error(f"✗ Error processing article {article.get('id', 'unknown')}: {e}")
                    skipped_count += 1
                    continue
            
            # If no articles were processed in this batch, we're done
            if not article_processed_in_batch:
                logger.info(f"No more processable articles found (generated {generated_count} articles)")
                break
        
        logger.info(f"\n{'='*80}")
        logger.info(f"AI writing process completed!")
        logger.info(f"  ✓ OUTPUT articles generated: {generated_count}/{max_articles}")
        logger.info(f"  ✗ Skipped/Failed: {skipped_count}")
        logger.info(f"  📊 Processed groups: {len(processed_groups)}")
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

def run(max_articles: int = None, rss_db: str = 'rss_articles.db', 
        our_db: str = 'our_articles.db', stats_only: bool = False) -> int:
    """Run AI writer process with optional parameters"""
    if max_articles is None:
        max_articles = ARTICLE_COUNT
    
    writer = AIWriter(rss_db, our_db)
    
    if stats_only:
        writer.print_statistics()
        return 0
    
    print("\n" + "="*80)
    print("INITIAL DATABASE STATUS")
    print("="*80)
    writer.print_statistics()
    
    writer.process_articles(max_articles)
    
    print("\n" + "="*80)
    print("FINAL DATABASE STATUS")
    print("="*80)
    writer.print_statistics()
    
    return 0

def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="AI Writer for RSS Articles - Rewrites news using Gemini AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Configuration Settings (edit in ai_writer.py):
  ONLY_IMAGES   = {ONLY_IMAGES}   (Process only articles with images)
  ARTICLE_COUNT = {ARTICLE_COUNT}   (Number of OUTPUT articles to GENERATE per run)

IMPORTANT: ARTICLE_COUNT is the number of OUTPUT articles to generate.
  - If a group has 12 source articles, it generates 1 OUTPUT article
  - ARTICLE_COUNT=10 means you get 10 articles in our_articles.db

Examples:
  python ai_writer.py                    # Generate {ARTICLE_COUNT} output articles
  python ai_writer.py --max-articles 20  # Generate 20 output articles
  python ai_writer.py --stats            # Show statistics only
        """
    )
    
    parser.add_argument('--max-articles', type=int, 
                       help=f'Number of OUTPUT articles to generate (default: {ARTICLE_COUNT})')
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
