const Parser = require('rss-parser');
const fs = require('fs');
const path = require('path');

const parser = new Parser();
const RSS_URL = 'https://www.uygurhaberajansi.com/rss';
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

(async () => {
    try {
        const feed = await parser.parseURL(RSS_URL);
        const memory = getMemory();
        let newArticlesCount = 0;

        // Iterate through items in reverse to process older items first if needed, 
        // or normal order. RSS usually puts newest first.
        // We want to see if it's new.
        
        feed.items.forEach(item => {
            // Identifier can be guid or link.
            const identifier = item.guid || item.link;

            if (!memory.includes(identifier)) {
                // It's a new article
                
                // "link text then description text"
                // Assuming 'link text' refers to the title of the link, or the URL itself?
                // The request says: "sharing must be link text then description text"
                // Usually "link text" means the anchor text, which corresponds to the Title.
                // Let's print Title then Description.
                
                console.log(`${item.title}\n${item.contentSnippet || item.summary || item.content}\n-----------------------------------`);
                
                memory.push(identifier);
                newArticlesCount++;
            }
        });

        if (newArticlesCount > 0) {
            saveMemory(memory);
            console.log(`\nFound and saved ${newArticlesCount} new articles.`);
        } else {
            console.log("No new articles found.");
        }

    } catch (err) {
        console.error("Error fetching or parsing RSS:", err);
    }
})();
