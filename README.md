# AI Newspaper

A modern news aggregation platform that fetches RSS feeds and displays them in a beautiful, responsive web interface. Built with FastAPI backend and Express.js + EJS frontend.

## 🏗️ Project Structure

```
AINewspaper/
├── backend/                    # FastAPI backend server
│   ├── aiConnection.py        # AI integration (Google Gemini)
│   ├── backendServer.py       # FastAPI server with RSS feed parser
│   └── testGrounds.ipynb      # Testing notebook
│
└── frontend/                  # Express.js frontend
    ├── server.js              # Express server
    ├── package.json           # Node.js dependencies
    ├── views/                 # EJS templates
    │   ├── index.ejs         # Main news page
    │   ├── news.ejs          # Individual article page
    │   └── error.ejs         # Error page
    └── public/               # Static assets
        ├── css/
        │   └── style.css     # Styles
        └── images/
```

## 📋 Features

- 📡 **RSS Feed Integration** - Fetches news from RSS feeds
- 🎨 **Modern UI** - Beautiful, responsive design with gradient themes
- 📰 **News Grid Layout** - Card-based news display
- 📖 **Full Article View** - Detailed news pages with images
- 🔄 **Real-time Updates** - Automatic news synchronization
- 🖼️ **Image Support** - Displays thumbnails and full images
- 🔗 **Source Links** - Links to original articles

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Node.js 16+
- npm or yarn

### Backend Setup (FastAPI)

1. **Navigate to backend directory:**
```bash
cd backend
```

2. **Install Python dependencies:**
```bash
pip install fastapi uvicorn feedparser python-dotenv google-genai
```

Or create a `requirements.txt`:
```bash
pip install -r requirements.txt
```

3. **Create `.env` file** (if using AI features):
```env
GEMINI_FREE_API=your_api_key_here
```

4. **Start the FastAPI server with uvicorn:**
```bash
uvicorn backendServer:app --reload
```

Or specify host and port:
```bash
uvicorn backendServer:app --host 0.0.0.0 --port 8000 --reload
```

The backend API will be available at `http://localhost:8000`

**Backend API Endpoints:**
- `GET /getOneNew` - Returns one unserved news item and marks it as served

### Frontend Setup (Express.js)

1. **Navigate to frontend directory:**
```bash
cd frontend
```

2. **Install Node.js dependencies:**
```bash
npm install
```

3. **Create `.env` file:**
```env
PORT=3000
BACKEND_URL=http://localhost:8000
```

4. **Start the frontend server:**

**Development mode** (with auto-reload):
```bash
npm run dev
```

**Production mode:**
```bash
npm start
```

The frontend will be available at `http://localhost:3000`

## 🔧 Running the Full Application

### Option 1: Quick Start Scripts (Recommended)

**Windows - Batch File (start.bat):**
```cmd
start.bat
```
- Starts both servers in minimized windows
- **Closing the main window stops ALL servers automatically**
- Press any key in the window to stop servers and exit

**Windows - PowerShell (start.ps1):**
```powershell
powershell -ExecutionPolicy Bypass -File start.ps1
```
- Better process management
- **Closing the window or Ctrl+C stops ALL servers automatically**
- Recommended for better cleanup

**Linux/Mac (start.sh):**
```bash
chmod +x start.sh
./start.sh
```
- Starts both servers
- **Ctrl+C stops ALL servers automatically**

### Option 2: Separate Terminals (Manual)

**Terminal 1 - Backend:**
```bash
cd backend
uvicorn backendServer:app --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

## 📊 How It Works

### Backend Flow

1. **RSS Feed Parsing**: 
   - `fetch_incoming()` - Fetches news from RSS URL
   - Parses: title, link, published date, summary, content, images

2. **News Management**:
   - `newsSelector()` - Compares incoming news with stored news
   - Only adds new articles to prevent duplicates
   - Maintains newest-first order

3. **API Service**:
   - `/getOneNew` endpoint serves oldest unserved news
   - Marks news as "served" to avoid repetition
   - Returns "endofline" when no unserved news available

### Frontend Flow

1. **Initialization**:
   - On startup, fetches 20 news articles from backend
   - Caches news in memory for fast access

2. **Main Page** (`/`):
   - Displays all cached news in responsive grid
   - Shows thumbnails, titles, summaries, dates
   - Click any card to view full article

3. **News Page** (`/news/:id`):
   - Displays full article with images
   - Shows complete content and source link
   - Easy navigation back to main page

4. **API Endpoints**:
   - `GET /api/news` - Returns all cached news as JSON
   - `GET /api/fetch-more` - Fetches additional news from backend

## 📝 Data Structure

Each news item has the following structure:

```javascript
{
  "title": "News Title",
  "link": "https://original-source.com/article",
  "published": "Thu, 02 Oct 2025 17:42:47 +0300",
  "summary": "Brief summary of the article",
  "content": "<p>Full HTML content...</p>",
  "image": "https://example.com/image.jpg",
  "thumbnail": "https://example.com/thumb.jpg",
  "served": 0  // 0 = unserved, 1 = served
}
```

## 🎨 Customization

### Change RSS Feed Source

Edit `backend/backendServer.py`:
```python
RSS_URL = "https://your-rss-feed-url.com/rss.xml"
```

### Customize Frontend Styling

Edit `frontend/public/css/style.css` to change:
- Color scheme (currently purple gradient)
- Layout dimensions
- Fonts and typography
- Responsive breakpoints

### Modify News Fetch Count

Edit `frontend/server.js`:
```javascript
// Change the number from 20 to your desired amount
for (let i = 0; i < 20; i++) {
    const newsItem = await fetchNewsFromBackend();
    // ...
}
```

## 🐛 Troubleshooting

### Backend Issues

**Port already in use:**
```bash
# Use a different port
uvicorn backendServer:app --port 8001 --reload
```

**ModuleNotFoundError:**
```bash
# Install missing dependencies
pip install fastapi uvicorn feedparser
```

### Frontend Issues

**Cannot connect to backend:**
- Ensure backend is running on port 8000
- Check `BACKEND_URL` in `.env` file
- Verify no firewall blocking the connection

**No news displayed:**
- Check backend console for errors
- Verify RSS feed URL is accessible
- Check browser console for API errors

**Port 3000 already in use:**
- Change `PORT` in `.env` file
- Or stop other applications using port 3000

## 📦 Dependencies

### Backend (Python)
- `fastapi` - Modern web framework
- `uvicorn` - ASGI server
- `feedparser` - RSS feed parsing
- `python-dotenv` - Environment variables
- `google-genai` - AI integration (optional)

### Frontend (Node.js)
- `express` - Web server framework
- `ejs` - Template engine
- `axios` - HTTP client
- `dotenv` - Environment variables
- `nodemon` - Development auto-reload (dev dependency)

## 🔐 Environment Variables

### Backend `.env`
```env
GEMINI_FREE_API=your_gemini_api_key_here
```

### Frontend `.env`
```env
PORT=3000
BACKEND_URL=http://localhost:8000
```

## 🚦 API Documentation

### Backend API

**GET /getOneNew**
- Returns: Single news object
- Response when news available:
```json
{
  "news": {
    "title": "...",
    "link": "...",
    ...
  }
}
```
- Response when no news available:
```json
{
  "news": {
    "title": "endofline",
    ...
  }
}
```

### Frontend API

**GET /**
- Returns: HTML page with news grid

**GET /news/:id**
- Params: `id` (integer) - Index of news article
- Returns: HTML page with full article

**GET /api/news**
- Returns: JSON array of all cached news

**GET /api/fetch-more**
- Returns: Newly fetched news item

## 📄 License

This project is open source and available under the MIT License.

## 👨‍💻 Development

### Adding New Features

1. **Backend**: Edit `backend/backendServer.py`
2. **Frontend**: Edit `frontend/server.js` and templates in `views/`
3. **Styling**: Edit `frontend/public/css/style.css`

### Testing Backend Separately

```bash
cd backend
python -c "from backendServer import fetch_incoming; fetch_incoming(); print('Success!')"
```

Or use the Jupyter notebook:
```bash
jupyter notebook testGrounds.ipynb
```

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest new features
- Submit pull requests

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review backend/frontend console logs
3. Verify all dependencies are installed
4. Ensure both servers are running

---

**Happy News Reading! 📰**

