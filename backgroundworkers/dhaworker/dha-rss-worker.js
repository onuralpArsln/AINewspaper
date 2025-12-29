#!/usr/bin/env node
/**
 * Standalone worker that fetches the DHA RSS feed and stores the latest 3 articles
 * in a local JSON file.
 */

const https = require('https');
const { promisify } = require('util');
const xml2js = require('xml2js');
const crypto = require('crypto');
const path = require('path');
const fs = require('fs');
const stream = require('stream');
const sharp = require('sharp');
const { sanitizeDhaHtml } = require('./dha-sanitize');

/**
 * Edit SETTINGS below to control how the RSS worker behaves.
 */
const SETTINGS = {
  writerName: 'UHA İzmir',
  maxImages: 100, // Download all images as requested
  maxVideos: 1,
  fallbackCategory: 'Gündem',
  bannedTopics: ["Yurt Haber", "Ek fotoğraflar", '(2)'],
  removeWords: ['FOTOĞRAFLI'],
  defaultLimit: 20, // Fetch more to safely find top 3 valid ones
  defaultFeedUrl: 'https://dhaabone.dha.com.tr/rss/1719/k9quL7DqdugGLn4kKrTMzmHbRWQN5JQZ4wfCwMuJiOE64o3-B7R_qu33sYG8kMYZHDqtewhItlDOPuc=',
  defaultLogFile: null,
  defaultDryRun: false,
  maxVideoBytes: 50 * 1024 * 1024, // 50 MB
  skipNoImages: true
};

const parser = new xml2js.Parser({ explicitArray: false, mergeAttrs: true });
const parseXml = promisify(parser.parseString);
const pipeline = promisify(stream.pipeline);
const normalizedBannedTopics = (Array.isArray(SETTINGS.bannedTopics) ? SETTINGS.bannedTopics : [])
  .map((topic) => (topic || '').toString().trim().toLowerCase())
  .filter(Boolean);

// Constants
const DATA_DIR = path.join(__dirname, 'data'); // Adjustable path
const JSON_STORAGE_FILE = path.join(DATA_DIR, 'dha-latest-news.json');
const RSS_MEDIA_DIR = path.join(DATA_DIR, 'media');
const RSS_MEDIA_WEB_PATH = 'media';
const RSS_VIDEO_DIR = path.join(RSS_MEDIA_DIR, 'videos');
const RSS_VIDEO_WEB_PATH = `${RSS_MEDIA_WEB_PATH}/videos`;
const RSS_VIDEO_THUMB_DIR = path.join(RSS_MEDIA_DIR, 'video-thumbnails');
const RSS_VIDEO_THUMB_WEB_PATH = `${RSS_MEDIA_WEB_PATH}/video-thumbnails`;
const MAX_VIDEO_BYTES = SETTINGS.maxVideoBytes;
const REQUEST_HEADERS = {
  'User-Agent': 'UHA-RSS-Worker/1.0 (+uha)',
  Accept: 'image/*,*/*;q=0.8'
};
const MAX_IMAGE_REDIRECTS = 3;
const IMAGE_DOWNLOAD_RETRIES = 3;

const isLocalPath = (url) => typeof url === 'string' && url.startsWith('media/');

function processArgs(argv) {
  const options = {
    limit: SETTINGS.defaultLimit,
    dryRun: SETTINGS.defaultDryRun,
    logFile: SETTINGS.defaultLogFile,
    feedUrl: SETTINGS.defaultFeedUrl
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--limit' && argv[i + 1]) {
      options.limit = parseInt(argv[i + 1], 10);
      i += 1;
    } else if (arg === '--dry-run') {
      options.dryRun = true;
    } else if (arg === '--log' && argv[i + 1]) {
      options.logFile = path.resolve(argv[i + 1]);
      i += 1;
    } else if (arg === '--feed' && argv[i + 1]) {
      options.feedUrl = argv[i + 1];
      i += 1;
    }
  }
  return options;
}

function fetchFeed(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      if (res.statusCode !== 200) {
        reject(new Error(`Unexpected status code ${res.statusCode}`));
        return;
      }
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
    }).on('error', reject);
  });
}

const stripHtml = (value = '') => value.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();

function summarizeHead(descriptionText) {
  const sentence = descriptionText.split(/(?<=\.)\s/)[0];
  return sentence || descriptionText.slice(0, 140);
}

function summarizeBody(descriptionText) {
  const max = 300;
  if (descriptionText.length <= max) return descriptionText;
  return `${descriptionText.slice(0, max - 1)}…`;
}

const ensureArray = (value) => {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
};

function containsBannedContent(item) {
  if (!normalizedBannedTopics.length) {
    return { matched: false, term: null };
  }

  const fields = [
    item?.title,
    item?.description,
    item?.summary,
    item?.body,
    item?.content
  ]
    .filter(Boolean)
    .map((value) => (typeof value === 'string' ? value : JSON.stringify(value)))
    .join(' ')
    .toLowerCase();

  const term = normalizedBannedTopics.find((topic) => fields.includes(topic));
  return { matched: Boolean(term), term: term || null };
}

function extractMedia(item) {
  const mediaEntries = ensureArray(item.mediaList?.media).map((media) => ({
    type: media.type || 'UNKNOWN',
    link: media.link
  })).filter((media) => !!media.link);

  const images = mediaEntries
    .filter((m) => m.type === 'IMAGE')
    .slice(0, SETTINGS.maxImages);
  const videos = mediaEntries
    .filter((m) => m.type === 'VIDEO')
    .slice(0, SETTINGS.maxVideos);

  return {
    images,
    videos
  };
}

function ensureDirectory(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

function buildImageFilename(item, index, imageUrl) {
  let ext = '.jpg';
  try {
    const urlObj = new URL(imageUrl);
    const pathname = urlObj.pathname || '';
    const candidate = path.extname(pathname);
    if (candidate) {
      ext = candidate.split('?')[0] || ext;
    }
  } catch (error) {
    // ignore
  }

  const safeExt = ext && ext.length <= 5 ? ext : '.jpg';
  const base = (item.newsId || `rss-${Date.now()}`).toString().replace(/[^a-zA-Z0-9-_]/g, '');
  return `${base}-${index}${safeExt}`;
}

function fetchWithRedirects(url, attempt = 0) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: REQUEST_HEADERS }, (res) => {
      const { statusCode, headers } = res;

      if (statusCode >= 300 && statusCode < 400 && headers.location) {
        if (attempt >= MAX_IMAGE_REDIRECTS) {
          res.resume();
          reject(new Error(`Too many redirects for ${url}`));
          return;
        }
        const nextUrl = new URL(headers.location, url).toString();
        res.resume();
        resolve(fetchWithRedirects(nextUrl, attempt + 1));
        return;
      }

      if (statusCode !== 200) {
        res.resume();
        reject(new Error(`Download failed (${statusCode}) for ${url}`));
        return;
      }

      resolve(res);
    }).on('error', reject);
  });
}

async function downloadImageAsset(imageUrl, diskPath) {
  let lastError;
  for (let attempt = 1; attempt <= IMAGE_DOWNLOAD_RETRIES; attempt += 1) {
    try {
      const response = await fetchWithRedirects(imageUrl);
      await pipeline(response, fs.createWriteStream(diskPath));
      return;
    } catch (error) {
      lastError = error;
      if (attempt === IMAGE_DOWNLOAD_RETRIES) break;
    }
  }
  throw lastError;
}

async function processImageEntry(item, imageUrl, index, downloadAssets) {
  const commonMeta = {
    alt: stripHtml(item.title || ''),
    title: stripHtml(item.title || '')
  };

  if (!downloadAssets) return null;

  ensureDirectory(RSS_MEDIA_DIR);
  const filename = buildImageFilename(item, index, imageUrl);
  const diskPath = path.join(RSS_MEDIA_DIR, filename);

  try {
    if (!fs.existsSync(diskPath)) {
      await downloadImageAsset(imageUrl, diskPath);
    }

    let metadata = {};
    try {
      metadata = await sharp(diskPath).metadata();
    } catch (error) { }

    const relativePath = `${RSS_MEDIA_WEB_PATH}/${filename}`;
    return {
      url: relativePath,
      lowRes: relativePath,
      highRes: relativePath,
      width: metadata.width || 800,
      height: metadata.height || 600,
      ...commonMeta
    };
  } catch (error) {
    return null;
  }
}

async function prepareImages(item, mediaImages, downloadAssets) {
  if (!mediaImages.length) return [];
  const processed = await Promise.all(
    mediaImages.map((img, index) => processImageEntry(item, img.link, index, downloadAssets))
  );
  return processed.filter(Boolean);
}

function buildVideoFilename(item, index, videoUrl) {
  let ext = '.mp4';
  try {
    const urlObj = new URL(videoUrl);
    const pathname = urlObj.pathname || '';
    const candidate = path.extname(pathname);
    if (candidate) {
      ext = candidate.split('?')[0] || ext;
    }
  } catch (error) {
    // ignore
  }

  const safeExt = ext && ext.length <= 5 ? ext : '.mp4';
  const base = (item.newsId || `rss-${Date.now()}`).toString().replace(/[^a-zA-Z0-9-_]/g, '');
  return `${base}-${index}${safeExt}`;
}

async function downloadVideoAsset(videoUrl, diskPath) {
  return new Promise((resolve, reject) => {
    https.get(videoUrl, (res) => {
      if (res.statusCode !== 200) {
        reject(new Error(`Video download failed (${res.statusCode})`));
        res.resume();
        return;
      }
      const contentLength = parseInt(res.headers['content-length'] || '0', 10);
      if (contentLength && contentLength > MAX_VIDEO_BYTES) {
        reject(new Error(`Video too large`));
        res.resume();
        return;
      }
      let downloaded = 0;
      res.on('data', (chunk) => {
        downloaded += chunk.length;
        if (downloaded > MAX_VIDEO_BYTES) {
          res.destroy(new Error(`Video exceeded size limit`));
        }
      });
      pipeline(res, fs.createWriteStream(diskPath)).then(resolve).catch(reject);
    }).on('error', reject);
  });
}

async function processVideoEntry(item, videoEntry, downloadAssets) {
  if (!videoEntry || !videoEntry.link) return { videoUrl: '', posterImage: null };
  if (!downloadAssets) return { videoUrl: '', posterImage: null };

  ensureDirectory(RSS_VIDEO_DIR);
  const filename = buildVideoFilename(item, 0, videoEntry.link);
  const diskPath = path.join(RSS_VIDEO_DIR, filename);

  try {
    if (!fs.existsSync(diskPath)) {
      await downloadVideoAsset(videoEntry.link, diskPath);
    }
    const videoUrl = `${RSS_VIDEO_WEB_PATH}/${filename}`;
    // Video poster generation removed as service is missing
    return {
      videoUrl,
      posterImage: null
    };
  } catch (error) {
    return { videoUrl: '', posterImage: null };
  }
}

function toIsoDate(pubDate) {
  if (!pubDate) return new Date().toISOString();
  // Attempt to parse standard RSS dates
  const date = new Date(pubDate);
  if (!Number.isNaN(date.getTime())) {
    return date.toISOString();
  }
  // Try custom format replacement if needed
  const normalized = pubDate.replace(' ', 'T');
  const date2 = new Date(`${normalized}Z`);
  if (!Number.isNaN(date2.getTime())) {
    return date2.toISOString();
  }
  return new Date().toISOString();
}

async function buildArticlePayload(item, downloadAssets) {
  const descriptionHtml = item.description || '';
  const sanitizedDescriptionHtml = sanitizeDhaHtml(descriptionHtml, { removeWords: SETTINGS.removeWords });
  const descriptionText = stripHtml(sanitizedDescriptionHtml);
  const media = extractMedia(item);

  // If downloadAssets is false, we just want to know if media EXISTS for filtering purposes
  if (!downloadAssets) {
    return {
      hasImages: media.images.length > 0
    };
  }

  const images = await prepareImages(item, media.images, true);
  const safeImages = images
    .filter((img) => {
      const candidate = img?.lowRes || img?.url;
      return isLocalPath(candidate);
    })
    .map((img) => ({
      ...img,
      lowRes: img.lowRes || img.url,
      highRes: img.highRes || img.lowRes || img.url
    }));

  const videoResult = await processVideoEntry(item, media.videos[0], true);
  const videoUrl = isLocalPath(videoResult.videoUrl) ? videoResult.videoUrl : '';

  if (!safeImages.length && videoResult.posterImage) {
    safeImages.push(videoResult.posterImage);
  }

  // Tags/Categories
  const category = (item.category || '').trim() || SETTINGS.fallbackCategory;
  const tags = [];
  if (item.category) tags.push(item.category);
  if (item.location) tags.push(item.location);

  return {
    id: buildExternalId(item),
    header: stripHtml(item.title || 'DHA Haberi'),
    summaryHead: summarizeHead(descriptionText),
    summary: summarizeBody(descriptionText),
    category,
    tags,
    body: sanitizedDescriptionHtml,
    images: safeImages,
    headlineImage: safeImages[0] || null,
    videoUrl,
    writer: item.author?.trim() || SETTINGS.writerName,
    creationDate: toIsoDate(item.pubDate),
    source: 'DHA RSS',
    outlinks: item.link ? [item.link] : [],
    timestamp: Date.now()
  };
}

function buildExternalId(item) {
  if (item.newsId) return `dha:${item.newsId}`;
  if (item.link) {
    const hash = crypto.createHash('sha1').update(item.link).digest('hex');
    return `dha-link:${hash}`;
  }
  return `dha-random:${Math.random().toString(36).slice(2)}`;
}

function log(message) {
  console.log(message);
  if (args.logFile) {
    fs.appendFileSync(args.logFile, `[${new Date().toISOString()}] ${message}\n`, 'utf-8');
  }
}

const args = processArgs(process.argv.slice(2));

async function run() {
  log(`🔄 Starting DHA RSS worker (JSON mode)`);

  try {
    const xml = await fetchFeed(args.feedUrl);
    const parsed = await parseXml(xml);
    const rawItems = parsed?.rss?.channel?.item;
    if (!rawItems) throw new Error('No RSS items found');

    const items = Array.isArray(rawItems) ? rawItems : [rawItems];

    // Sort all items by date descending first
    const sortedItems = items.sort((a, b) => {
      const dateA = new Date(toIsoDate(a.pubDate));
      const dateB = new Date(toIsoDate(b.pubDate));
      return dateB - dateA; // Descending
    });

    // Valid candidates list
    const candidates = [];

    for (const item of sortedItems) {
      if (candidates.length >= 3) break; // Optimization: stop if we have 3 candidates

      const banCheck = containsBannedContent(item);
      if (banCheck.matched) {
        // log(`Skipped banned: ${item.title}`);
        continue;
      }

      // Check for images presence without downloading yet
      const mediaProbe = extractMedia(item);
      if (SETTINGS.skipNoImages && (!mediaProbe.images || mediaProbe.images.length === 0)) {
        // log(`Skipped no-image: ${item.title}`);
        continue;
      }

      candidates.push(item);
    }

    if (candidates.length === 0) {
      log('No valid articles found to process.');
      return;
    }

    // Read existing JSON
    let existingArticles = [];
    try {
      if (fs.existsSync(JSON_STORAGE_FILE)) {
        existingArticles = JSON.parse(fs.readFileSync(JSON_STORAGE_FILE, 'utf-8'));
      }
    } catch (err) {
      log(`Error reading existing JSON: ${err.message}`);
      existingArticles = [];
    }

    // Check if the newest candidate is newer than the newest existing article
    // We compare the very first (newest) candidate against the very first (newest) existing
    const topCandidateId = buildExternalId(candidates[0]);
    const topExistingId = existingArticles[0]?.id;

    if (topCandidateId === topExistingId) {
      log('No new articles detected. Top article ID matches.');
      return;
    }

    // If we have something new, process the top 3 candidates fully
    log(`Found new articles. Processing top ${candidates.length}...`);

    const processedArticles = [];
    for (const item of candidates) {
      log(`• Processing: ${item.title}`);
      const payload = await buildArticlePayload(item, true); // true = download assets
      processedArticles.push(payload);
    }

    // Save to JSON
    ensureDirectory(DATA_DIR);
    fs.writeFileSync(JSON_STORAGE_FILE, JSON.stringify(processedArticles, null, 2), 'utf-8');
    log(`✅ Successfully updated ${JSON_STORAGE_FILE} with ${processedArticles.length} articles.`);

  } catch (error) {
    console.error('❌ Worker failed:', error.message);
    process.exitCode = 1;
  }
}

run();


