const Parser = require('rss-parser');
const axios = require('axios');
const fs = require('fs');
const path = require('path');

// --- CONFIGURATION ---
// Please fill in your Whapi.cloud credentials here
const WHAPI_TOKEN = 'ZiRh4pzfMYjXNwd1fzdPjmNH9Dn6pTqK';
const WHAPI_DESTINATION = '120363423920732166@newsletter'; // Verified Channel ID
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

async function checkFeed() {
    try {
        console.log(`[${new Date().toISOString()}] Checking for new articles...`);
        const feed = await parser.parseURL(RSS_URL);
        const memory = getMemory();

        if (!feed.items || feed.items.length === 0) {
            console.log("No items found in RSS feed.");
            return;
        }

        // Check only the newest article (first item)
        const latestItem = feed.items[0];
        const identifier = latestItem.guid || latestItem.link;

        if (!memory.includes(identifier)) {
            console.log(`New Article found: ${latestItem.title}`);

            // Send to WhatsApp
            const sent = await sendToWhapi(latestItem);

            if (sent) {
                // Add to memory and save
                memory.push(identifier);
                // Optional: Trim memory to keep it from growing indefinitely (keep last 500)
                if (memory.length > 500) memory.shift();
                saveMemory(memory);
            }
        } else {
            console.log("No new articles (newest already seen).");
        }

    } catch (err) {
        console.error("Error in checkFeed:", err.message);
    }
}

// Run immediately on start
checkFeed();

// Run every 60 seconds (1 minute)
setInterval(checkFeed, 60 * 1000);
