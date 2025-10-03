# AI Newspaper Frontend

A modern, responsive news website built with Express.js and EJS templates.

## Features

- 📰 Beautiful news grid layout on the main page
- 📖 Individual news article pages with full content
- 🎨 Modern, responsive design
- 🖼️ Image support with fallback for broken images
- 🔗 Links to original news sources
- ⚡ Fast and lightweight

## Installation

1. Install dependencies:
```bash
npm install
```

2. Configure environment variables in `.env`:
```
PORT=3000
BACKEND_URL=http://localhost:8000
```

3. Make sure the backend FastAPI server is running on port 8000

## Running the Application

### Development mode (with auto-reload):
```bash
npm run dev
```

### Production mode:
```bash
npm start
```

The frontend will be available at `http://localhost:3000`

## Project Structure

```
frontend/
├── server.js           # Express server configuration
├── package.json        # Dependencies
├── .env               # Environment variables
├── views/             # EJS templates
│   ├── index.ejs      # Main page (news list)
│   ├── news.ejs       # Individual news article page
│   └── error.ejs      # Error page
└── public/            # Static assets
    └── css/
        └── style.css  # Main stylesheet
```

## API Endpoints

- `GET /` - Main page with all news articles
- `GET /news/:id` - Individual news article page
- `GET /api/news` - JSON endpoint for all cached news
- `GET /api/fetch-more` - Fetch more news from backend

## How It Works

1. On startup, the server fetches 20 news articles from the FastAPI backend
2. News articles are cached in memory for fast access
3. The main page displays all cached news in a responsive grid
4. Clicking on any article opens the full article page
5. You can fetch more articles using the `/api/fetch-more` endpoint

## Backend Integration

This frontend connects to the FastAPI backend running at `http://localhost:8000` and calls the `/getOneNew` endpoint to fetch news articles.

Each news item has the following structure:
- `title`: Article title
- `link`: Original article URL
- `published`: Publication date
- `summary`: Brief summary
- `content`: Full article content (HTML)
- `image`: Main image URL
- `thumbnail`: Thumbnail image URL

