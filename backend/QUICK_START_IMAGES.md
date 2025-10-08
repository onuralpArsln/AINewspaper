# Quick Start Guide - New Image Handling

## 🚀 Quick Start (TL;DR)

### Everything is Ready!
Your database has been automatically migrated. Just use it normally:

```bash
# Collect RSS articles (images automatically extracted)
python rss2db.py

# That's it! Images are now in the unified image_urls column
```

---

## 📋 Accessing Images (Python)

### Simple Example
```python
from rss2db import RSSDatabase
import json

db = RSSDatabase('rss_articles.db')
articles = db.get_recent_articles(10)

for article in articles:
    # ONE simple line to get ALL images!
    images = json.loads(article['image_urls']) if article.get('image_urls') else []
    
    print(f"{article['title']}: {len(images)} images")
```

### Get Statistics
```python
from rss2db import RSSDatabase

db = RSSDatabase('rss_articles.db')
stats = db.get_image_statistics()

print(f"Total images: {stats['total_images']}")
print(f"Articles with images: {stats['articles_with_images']}")
```

---

## 📊 SQL Queries

### Get All Images from an Article
```sql
SELECT title, image_urls FROM articles WHERE id = 1;
```

### Find Articles with Images
```sql
SELECT title, image_urls 
FROM articles 
WHERE image_urls IS NOT NULL 
  AND image_urls != '[]';
```

### Count Images per Article
```sql
SELECT 
    title,
    json_array_length(image_urls) as image_count
FROM articles 
WHERE image_urls IS NOT NULL;
```

---

## 🔄 What Changed?

### Before (Complex):
```python
# Had to check multiple places
images = []
if article.get('image_url'):
    images.append(article['image_url'])
if article.get('image_urls'):
    images.extend(json.loads(article['image_urls']))
if article.get('content'):
    # Parse HTML to find images
    ...
```

### After (Simple):
```python
# ONE place to check!
images = json.loads(article['image_urls']) if article.get('image_urls') else []
```

---

## 📝 Your Database Stats

```
✅ Total articles: 1,305
✅ Articles with images: 1,018 (78%)
✅ Total images extracted: 1,775
✅ Average images per article: 1.74
✅ Best article: 38 images!
```

---

## 🎯 Key Points

1. **One Column**: All images in `image_urls` (JSON array)
2. **Comprehensive**: Extracts from HTML, RSS, media, everywhere
3. **Automatic**: No manual work needed
4. **Clean**: Validated, deduplicated, no tracking pixels
5. **Simple**: Easy to use and access

---

## 📚 More Info

- **Full Docs**: `RSS2DB_IMAGE_OVERHAUL.md`
- **Summary**: `OVERHAUL_SUMMARY.md`
- **Main README**: `README.md`

---

## ❓ Common Questions

**Q: Do I need to do anything?**  
A: No! Your database was already migrated. Just use it normally.

**Q: What about old code that used `image_url`?**  
A: It's been updated. Everything now uses `image_urls`.

**Q: How do I get images in JavaScript/frontend?**  
A: Same as before - the backend API returns the data. Just parse `image_urls` as JSON.

**Q: Can I re-run the migration?**  
A: Yes! Run `python migrate_images.py` anytime (it's safe).

**Q: Where are the images stored?**  
A: In the `image_urls` column as a JSON array of URL strings.

---

## 🎉 You're All Set!

Everything is ready to use. The image handling is now:
- ✅ Simpler
- ✅ More comprehensive  
- ✅ Better organized
- ✅ Easier to maintain

Just continue using `rss2db.py` as you always have!

