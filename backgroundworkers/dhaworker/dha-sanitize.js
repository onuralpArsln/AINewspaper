/**
 * DHA RSS HTML sanitizer.
 *
 * Goal:
 * - Remove DHA author/location byline prefixes that appear inside <p> blocks.
 * - Remove trailing "(DHA)" tokens that appear at the end of paragraphs.
 *
 * NOTE: Keep this conservative to avoid deleting real story text.
 */

function sanitizeDhaHtml(html = '', options = {}) {
  const source = (html || '').toString();
  if (!source.trim()) return source;

  const removeWords = Array.isArray(options.removeWords)
    ? options.removeWords.filter((w) => typeof w === 'string' && w.length > 0)
    : [];

  // Only operate on <p> blocks (DHA RSS uses <p> for content).
  const paragraphRegex = /<p\b[^>]*>[\s\S]*?<\/p>/gi;
  const paragraphs = source.match(paragraphRegex);
  if (!paragraphs) {
    // Fallback: still remove trailing "(DHA)" if it’s the whole string
    const tokenStripped = stripTrailingDhaToken(source);
    return removeWords.length ? removeExactWords(tokenStripped, removeWords) : tokenStripped;
  }

  const cleaned = paragraphs
    .map((p) => {
      const inner = p
        .replace(/^<p\b[^>]*>/i, '')
        .replace(/<\/p>\s*$/i, '');

      const cleanedText = sanitizeParagraphText(inner, { removeWords });
      if (!cleanedText) return '';

      return `<p>${cleanedText}</p>`;
    })
    .filter(Boolean);

  return cleaned.join('');
}

function sanitizeParagraphText(htmlLike = '', options = {}) {
  const raw = (htmlLike || '').toString();
  const text = stripInlineTags(raw).trim();
  if (!text) return '';

  const removeWords = Array.isArray(options.removeWords)
    ? options.removeWords.filter((w) => typeof w === 'string' && w.length > 0)
    : [];

  // 1) Drop standalone "Haber-Kamera: ..." paragraphs (detect BEFORE trimming "(DHA)")
  if (isStandaloneCameraByline(text)) {
    return '';
  }

  // 2) Remove trailing "(DHA)" token ONLY (keep paragraph text, including punctuation)
  let next = stripTrailingDhaToken(text);

  // 3) Remove byline prefixes like "Name SURNAME/ LOCATION, (DHA)- ..." or "Name/ LOCATION, DHA/ LOCATION"
  // Supports both formats: (DHA) with parentheses and DHA/ without parentheses (optionally followed by location)
  // Location after DHA/ is limited to avoid matching story text (max ~20 chars, typically 1-2 words)
  // Handles "DHA/" and "DHA /" (with optional space before slash)
  // Keep the remainder of the paragraph.
  const bylinePrefixRegex =
    /^\s*(?:Haber\s*[-–—]\s*Kamera:\s*)?[\p{L}.'’\-–—\s]{2,120}\s*\/\s*[\p{L}0-9()'’.,\-–—\s]{2,160}\s*,?\s*(?:\(DHA\)|DHA\s*\/\s*(?:[A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ\s]{0,20}(?=\s))?)\s*[-–—]?\s*/u;

  if (bylinePrefixRegex.test(next)) {
    next = next.replace(bylinePrefixRegex, '').trim();
  }

  // 4) Remove exact case-sensitive words (e.g. FOTOĞRAFLI) without affecting other text.
  if (removeWords.length) {
    next = removeExactWords(next, removeWords).trim();
  }

  // If after stripping the byline we have nothing meaningful, drop paragraph.
  if (!next) return '';

  return next;
}

function stripTrailingDhaToken(text = '') {
  // Remove only the "(DHA)" token when it appears at the end,
  // optionally preceded by whitespace and optionally followed by punctuation/whitespace.
  // IMPORTANT: Do not remove punctuation that appears before "(DHA)".
  return (text || '').toString().replace(/\s*\(DHA\)\s*[\.,;:!?]*\s*$/i, '').trim();
}

function isStandaloneCameraByline(text = '') {
  const t = (text || '').toString().trim();
  if (!t) return false;
  // Examples:
  // - "Haber-Kamera: Emre ÖNCEL- Berkay YILDIZ/ SAMSUN, (DHA)-"
  // - "Haber - Kamera: Tunahan KIR/ANTALYA, (DHA)"
  return /^(?:Haber\s*[-–—]\s*Kamera:|Haber-Kamera:)\s*.+\(DHA\)\s*[-–—]?\s*$/i.test(t);
}

function stripInlineTags(value = '') {
  // We expect plain text in <p>, but be defensive.
  return (value || '').toString().replace(/<[^>]*>/g, '');
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function removeExactWords(text = '', words = []) {
  let out = (text || '').toString();
  for (const word of words) {
    if (!word) continue;
    // Case-sensitive exact word removal.
    // We cannot rely on \b for Turkish characters, so we use Unicode letter/number boundaries.
    const w = escapeRegExp(word);
    const re = new RegExp(`(^|[^\\p{L}0-9_])${w}($|[^\\p{L}0-9_])`, 'gu');
    out = out.replace(re, (match, left, right) => `${left}${right}`);
  }
  // Normalize leftover whitespace introduced by removals.
  return out.replace(/\s{2,}/g, ' ').replace(/\s+([,.;:!?])/g, '$1').trim();
}

module.exports = {
  sanitizeDhaHtml,
  // exported for unit tests
  sanitizeParagraphText,
  stripTrailingDhaToken,
  removeExactWords
};


