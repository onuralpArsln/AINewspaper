const Parser = require('rss-parser');
const axios = require('axios');
const fs = require('fs');
const path = require('path');

// --- CONFIGURATION ---
// Please fill in your Whapi.cloud credentials here
const WHAPI_TOKEN = 'YOUR_WHAPI_TOKEN';
const WHAPI_DESTINATION = 'YOUR_DESTINATION_NUMBER'; // Format: 1234567890 (no plus sign)
const RSS_URL = 'https://www.uygurhaberajansi.com/rss';
// ---------------------

const parser = new Parser();
const MEMORY_FILE = path.join(__dirname, 'memory.json');

// Ensure memory file exists
function getMemory() {
    if (!fs.existsSync(MEMORY_FILE)) {
        return [];
    }
    const data = fs.readFileSync(MEMORY_FILE, 'utf8');
    try {
        return JSON.parse(data);
    } catch (err) {
        console.error("Error parsing memory file, starting fresh:", err);
        return [];
    }
}

function saveMemory(memory) {
    fs.writeFileSync(MEMORY_FILE, JSON.stringify(memory, null, 2));
}

async function sendToWhapi(article) {
    if (WHAPI_TOKEN === 'YOUR_WHAPI_TOKEN' || WHAPI_DESTINATION === 'YOUR_DESTINATION_NUMBER') {
        console.warn("Whapi credentials not set. Skipping WhatsApp message.");
        return false;
    }

    const messageBody = `${article.title}\n\n${article.contentSnippet || article.summary || article.content}\n\n${article.link}`;

    try {
        await axios.post('https://gate.whapi.cloud/messages/text', {
            to: WHAPI_DESTINATION,
            body: messageBody
        }, {
            headers: {
                'Authorization': `Bearer ${WHAPI_TOKEN}`,
                'Content-Type': 'application/json'
            }
        });
        console.log(`Sent to WhatsApp: ${article.title}`);
        return true;
    } catch (error) {
        console.error(`Failed to send - ${article.title}:`, error.response ? error.response.data : error.message);
        return false;
    }
}

(async () => {
    try {
        console.log("Checking for new articles...");
        const feed = await parser.parseURL(RSS_URL);
        const memory = getMemory();
        let newArticlesCount = 0;

        // Process items. RSS feeds usually give newest first.
        // We iterate and check if seen.

        for (const item of feed.items) {
            const identifier = item.guid || item.link;

            if (!memory.includes(identifier)) {
                // It's a new article
                console.log(`New Article: ${item.title}`);

                // Send to WhatsApp
                await sendToWhapi(item);

                // Add to memory
                memory.push(identifier);
                newArticlesCount++;
            }
        }

        if (newArticlesCount > 0) {
            saveMemory(memory);
            console.log(`\nProcessed ${newArticlesCount} new articles.`);
        } else {
            console.log("No new articles found.");
        }

    } catch (err) {
        console.error("Error fetching or parsing RSS:", err);
    }
})();
