# 🌐 AI Newspaper Frontend

> **Modern, responsive news website** built with Express.js and EJS templates

[![Node.js](https://img.shields.io/badge/Node.js-16+-green.svg)](https://nodejs.org)
[![Express](https://img.shields.io/badge/Express-4.18+-blue.svg)](https://expressjs.com)
[![EJS](https://img.shields.io/badge/EJS-3.1+-orange.svg)](https://ejs.co)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)](https://github.com)

## ✨ Features

- 📰 **Beautiful News Grid** - Responsive card-based layout
- 📖 **Individual Article Pages** - Full content with rich media
- 🎨 **Dynamic Color System** - HSL-based theme customization
- 🖼️ **Smart Image Handling** - Fallback support and optimization
- 🔗 **Source Attribution** - Links to original news sources
- ⚡ **Performance Optimized** - Fast loading with caching
- 📱 **Mobile Responsive** - Perfect on all devices
- 🎯 **Turkish Language** - Localized for Turkish news

## 🚀 Quick Start

### Prerequisites
- Node.js 16+ 
- Backend FastAPI server running on port 8000

### Installation
```bash
# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Environment Configuration
```env
PORT=3000
BACKEND_URL=http://localhost:8000
```

## 🏃‍♂️ Running the Application

### Development Mode (Recommended)
```bash
npm run dev
```
- **Auto-reload** with nodemon [[memory:3122819]]
- **Hot reloading** for instant changes
- **Error handling** with detailed logs

### Production Mode
```bash
npm start
```

### Access Points
- **Frontend**: `http://localhost:3000`
- **Backend API**: `http://localhost:8000`
- **Health Check**: `http://localhost:3000/api/health`

## 📁 Project Structure

```
frontend/
├── server.js              # Express server configuration
├── package.json           # Dependencies and scripts
├── .env                   # Environment variables
├── views/                 # EJS templates
│   ├── index.ejs         # Main page (news grid)
│   ├── news.ejs          # Individual article page
│   ├── error.ejs         # Error page
│   └── index.ejs.backup  # Backup template
└── public/               # Static assets
    ├── css/
    │   └── style.css     # Dynamic color system CSS
    └── images/
        ├── logo.png      # Site logo
        └── logo-placeholder.txt
```

## 🎨 Dynamic Color System

The frontend features a sophisticated HSL-based color system:

### 🎯 Color Customization
```css
:root {
  --base-hue: 190;        /* Change this (0-360) for new theme */
  --base-saturation: 60%; /* Color intensity */
  --base-lightness: 45%;  /* Brightness */
}
```

### 🌈 Color Examples
- **Blue**: `--base-hue: 210` (current)
- **Red**: `--base-hue: 0`
- **Green**: `--base-hue: 120`
- **Purple**: `--base-hue: 270`
- **Orange**: `--base-hue: 30`

## 🌐 API Endpoints

### 🎯 Frontend Routes
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | 📰 Main page with news grid |
| `/news/:id` | GET | 📖 Individual article page |
| `/api/news` | GET | 📄 JSON endpoint for cached news |
| `/api/fetch-more` | GET | ➕ Fetch additional articles |

### 🔧 Navigation System
The frontend includes a configurable navigation system with Turkish news categories:
- **Anasayfa** - Home page
- **Son Dakika** - Breaking news
- **Spor** - Sports news
- **Canlı Yayın** - Live broadcast
- **Cumhurbaşkanı Erdoğan Konuşuyor** - President Erdoğan speeches
- **Devlet Bahçeli Konuşuyor** - Devlet Bahçeli speeches
- **Özgür Özel Konuşuyor** - Özgür Özel speeches
- **Deprem** - Earthquake news

## ⚙️ How It Works

### 🔄 Data Flow
1. **Startup**: Server fetches 20 articles from backend API
2. **Caching**: Articles stored in memory for fast access
3. **Display**: Responsive grid layout with cards
4. **Navigation**: Click any article for full content
5. **Dynamic Loading**: Fetch more articles on demand

### 🎨 Rendering System
- **EJS Templates**: Server-side rendering with dynamic data
- **Responsive Design**: Mobile-first approach
- **Image Optimization**: Automatic fallback handling
- **Performance**: In-memory caching for speed

## 🔗 Backend Integration

### 📡 API Communication
The frontend connects to the FastAPI backend via HTTP requests:

```javascript
// Fetch news from backend
const response = await axios.get(`${BACKEND_URL}/getOneNew`);
const newsItem = response.data.news;
```

### 📊 Data Structure
Each news item contains:
```json
{
  "id": 123,
  "title": "Article Title",
  "summary": "Brief description",
  "content": "Full article content (HTML)",
  "tags": "category, location, keywords",
  "published": "2025-01-08T14:38:00+03:00",
  "image": "https://example.com/image.jpg",
  "images": ["https://example.com/image1.jpg", "..."],
  "link": "https://original-source.com/article"
}
```

### 🔄 Error Handling
- **Connection Failures**: Graceful fallback to cached content
- **API Errors**: User-friendly error messages
- **Image Failures**: Automatic fallback to placeholder

## 🛠️ Development

### 📦 Dependencies
```json
{
  "dependencies": {
    "axios": "^1.6.0",      // HTTP client
    "dotenv": "^16.3.1",    // Environment variables
    "ejs": "^3.1.9",        // Template engine
    "express": "^4.18.2"    // Web framework
  },
  "devDependencies": {
    "nodemon": "^3.1.10"    // Auto-reload
  }
}
```

### 🎯 Customization
- **Navigation**: Edit `navigationConfig` in `server.js`
- **Colors**: Modify CSS custom properties in `style.css`
- **Layout**: Update EJS templates in `views/`
- **Styling**: Customize CSS in `public/css/style.css`

## 🚀 Performance Features

- **In-Memory Caching**: Fast article access
- **Responsive Images**: Optimized loading
- **Minimal Dependencies**: Lightweight footprint
- **Auto-Reload**: Development efficiency
- **Error Recovery**: Robust error handling

