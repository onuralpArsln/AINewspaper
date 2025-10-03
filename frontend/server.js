const express = require('express');
const axios = require('axios');
const path = require('path');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

// Set EJS as templating engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Serve static files (CSS, images, etc.)
app.use(express.static(path.join(__dirname, 'public')));

// In-memory storage for fetched news
let newsCache = [];

// Fetch news from backend
async function fetchNewsFromBackend() {
    try {
        const response = await axios.get(`${BACKEND_URL}/getOneNew`);
        const newsItem = response.data.news;

        // Check if we reached end of line
        if (newsItem.title === "endofline") {
            return null;
        }

        return newsItem;
    } catch (error) {
        console.error('Error fetching news from backend:', error.message);
        return null;
    }
}

// Fetch multiple news items on startup
async function initializeNewsCache() {
    console.log('Fetching news from backend...');
    for (let i = 0; i < 20; i++) {
        const newsItem = await fetchNewsFromBackend();
        if (newsItem) {
            newsCache.push(newsItem);
        } else {
            break;
        }
    }
    console.log(`Loaded ${newsCache.length} news items`);
}

// Routes

// Main page - Display all news
app.get('/', (req, res) => {
    res.render('index', {
        news: newsCache,
        title: 'AI Newspaper - Latest News'
    });
});

// Individual news page
app.get('/news/:id', (req, res) => {
    const newsId = parseInt(req.params.id);

    if (newsId >= 0 && newsId < newsCache.length) {
        const newsItem = newsCache[newsId];
        res.render('news', {
            news: newsItem,
            newsId: newsId,
            title: newsItem.title
        });
    } else {
        res.status(404).render('error', {
            message: 'News not found',
            title: 'Error 404'
        });
    }
});

// API endpoint to get all news (JSON)
app.get('/api/news', (req, res) => {
    res.json({ news: newsCache });
});

// API endpoint to fetch more news from backend
app.get('/api/fetch-more', async (req, res) => {
    const newsItem = await fetchNewsFromBackend();
    if (newsItem) {
        newsCache.push(newsItem);
        res.json({ success: true, news: newsItem });
    } else {
        res.json({ success: false, message: 'No more news available' });
    }
});

// 404 handler
app.use((req, res) => {
    res.status(404).render('error', {
        message: 'Page not found',
        title: 'Error 404'
    });
});

// Start server
app.listen(PORT, async () => {
    console.log(`Frontend server running on http://localhost:${PORT}`);
    await initializeNewsCache();
});

