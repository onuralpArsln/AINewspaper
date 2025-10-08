# AI Newspaper Backend

## 📚 Documentation

All documentation is in **`DOCUMENTATION.md`** - A comprehensive guide covering:

- 🚀 Quick Start (4-step workflow)
- 🔄 Complete Workflow with image sorting
- 🖼️ Image handling & resolution sorting (**NEW!**)
- 📊 Article grouping
- 🤖 AI article generation
- 🌐 Backend server API
- 🐛 Troubleshooting

## ⚡ Quick Commands

```bash
# Use Python 3.11 virtual environment
cd /home/onuralp/project/AINewspaper/backend

# 1. Collect RSS articles
venv/bin/python rss2db.py

# 2. Group similar articles
venv/bin/python group_articles.py --threshold 0.3

# 3. Generate articles (with sorted images!)
venv/bin/python ai_writer.py --max-articles 10

# 4. Start server
venv/bin/python -m uvicorn backendServer:app --reload
```

## 🎯 What's New: Image Sorting

Images are now automatically:
- ✅ Sorted by resolution (highest first)
- ✅ Filtered (removes <200×200 pixels)
- ✅ Best quality image always at `images[0]`

**Workflow:** rss2db → group_articles → **ai_writer (sorts images)** → our_articles.db → backendServer

## 📖 See DOCUMENTATION.md for Full Details

