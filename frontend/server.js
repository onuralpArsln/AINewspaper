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

// Navigation configuration - Tabs Names
// To modify navigation tabs, simply update this configuration:
const navigationConfig = {
    tabs: [
        { name: 'Anasayfa', url: '/', pageTitle: 'Uygur Haber Ajansı', active: false },
        { name: 'Son Dakika', url: '/#breaking', pageTitle: 'UHA Son Dakika', active: false },
        { name: 'Spor', url: '/#spor', pageTitle: 'UHA Spor Haberleri', active: false },
        { name: 'Canlı Yayın', url: '/#live', pageTitle: 'UHACanlı Yayın', active: false },
        { name: 'Cumhurbaşkanı Erdoğan Konuşuyor', url: '/#erdogan', pageTitle: 'UHA Cumhurbaşkanı Erdoğan', active: false },
        { name: 'Devlet Bahçeli Konuşuyor', url: '/#bahceli', pageTitle: 'UHA Devlet Bahçeli', active: false },
        { name: 'Özgür Özel Konuşuyor', url: '/#ozel', pageTitle: 'UHA Özgür Özel', active: false },
        { name: 'Deprem', url: '/#deprem', pageTitle: 'UHA Deprem Haberleri', active: false }
        // Add more tabs by adding objects with name, url, pageTitle, and active properties
        // Example: { name: 'Contact', url: '/contact', pageTitle: 'Contact Us', active: false }
    ]
};

// Helper function to get navigation with active tab set
function getNavigation(activeUrl = '/') {
    return {
        tabs: navigationConfig.tabs.map(tab => ({
            ...tab,
            active: tab.url === activeUrl
        }))
    };
}

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
        title: 'AI Gazetesi - Son Haberler',
        navigation: getNavigation('/')
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
            title: newsItem.title,
            navigation: getNavigation('/')
        });
    } else {
        res.status(404).render('error', {
            message: 'Haber bulunamadı',
            title: 'Hata 404',
            navigation: getNavigation('/')
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
        res.json({ success: false, message: 'Daha fazla haber mevcut değil' });
    }
});

// 404 handler
app.use((req, res) => {
    res.status(404).render('error', {
        message: 'Sayfa bulunamadı',
        title: 'Hata 404',
        navigation: getNavigation('/')
    });
});

// Start server
app.listen(PORT, async () => {
    console.log(`Frontend server running on http://localhost:${PORT}`);
    await initializeNewsCache();
});

