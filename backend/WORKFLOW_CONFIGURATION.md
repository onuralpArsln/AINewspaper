# Workflow Configuration Guide

This guide explains how to configure the AI Newspaper workflow to enable or disable different components.

## Configuration Location

All workflow configuration is done in `workflow.py` at the top of the file:

```python
# =============================================================================
# WORKFLOW CONFIGURATION
# =============================================================================

# Source Configuration - Enable/Disable Data Sources
ENABLE_RSS_SOURCE = False      # Enable RSS feed processing (rss2db.py)
ENABLE_SCRAPER_SOURCE = True  # Enable web scraper processing (scraper2db.py)

# AI Processing Configuration - Enable/Disable AI Components
ENABLE_AI_EDITOR = True        # Enable AI article editor (ai_editor.py)
ENABLE_AI_REWRITER = True      # Enable AI article rewriter (ai_rewriter.py)
```

## Configuration Options

### Data Sources
- **ENABLE_RSS_SOURCE**: Controls RSS feed processing
- **ENABLE_SCRAPER_SOURCE**: Controls web scraper processing

### AI Processing Components
- **ENABLE_AI_EDITOR**: Controls AI article evaluation and approval
- **ENABLE_AI_REWRITER**: Controls AI article enhancement for rejected articles

## Configuration Scenarios

### Scenario 1: Full AI Pipeline (Default)
```python
ENABLE_RSS_SOURCE = False
ENABLE_SCRAPER_SOURCE = True
ENABLE_AI_EDITOR = True
ENABLE_AI_REWRITER = True
```
**Result**: 
- Articles go through: Scraper → Grouping → AI Writer → AI Editor → AI Rewriter
- API serves only `accepted` articles
- RSS feeds serve only `accepted` articles

### Scenario 2: No AI Review (Direct Publishing)
```python
ENABLE_RSS_SOURCE = False
ENABLE_SCRAPER_SOURCE = True
ENABLE_AI_EDITOR = False
ENABLE_AI_REWRITER = False
```
**Result**:
- Articles go through: Scraper → Grouping → AI Writer
- API serves `not_reviewed` articles directly
- RSS feeds serve `not_reviewed` articles directly
- No editorial review or rewriting

### Scenario 3: Editor Only (No Rewriting)
```python
ENABLE_RSS_SOURCE = False
ENABLE_SCRAPER_SOURCE = True
ENABLE_AI_EDITOR = True
ENABLE_AI_REWRITER = False
```
**Result**:
- Articles go through: Scraper → Grouping → AI Writer → AI Editor
- API serves only `accepted` articles
- Rejected articles are not rewritten
- RSS feeds serve only `accepted` articles

### Scenario 4: Rewriter Only (No Initial Review)
```python
ENABLE_RSS_SOURCE = False
ENABLE_SCRAPER_SOURCE = True
ENABLE_AI_EDITOR = False
ENABLE_AI_REWRITER = True
```
**Result**:
- Articles go through: Scraper → Grouping → AI Writer → AI Rewriter
- API serves `not_reviewed` articles (since no editor to mark as accepted)
- AI Rewriter processes articles (though this scenario is unusual)
- RSS feeds serve `not_reviewed` articles

## Article States and API Behavior

### When AI Editor is ENABLED:
- Articles start as `not_reviewed`
- AI Editor evaluates and marks as `accepted` or `rejected`
- API and RSS serve only `accepted` articles
- AI Rewriter (if enabled) enhances `rejected` articles

### When AI Editor is DISABLED:
- Articles remain as `not_reviewed`
- API and RSS serve `not_reviewed` articles directly
- No editorial review process
- AI Rewriter (if enabled) has no rejected articles to process

## How to Change Configuration

1. **Edit `workflow.py`**: Modify the configuration flags at the top of the file
2. **Restart the backend server**: The server reads the configuration on startup
3. **Check status**: Visit `http://localhost:8000/` to see current configuration

## Server Status Endpoint

The root endpoint (`/`) shows the current configuration:

```json
{
  "message": "AI Newspaper Backend Server",
  "status": "running",
  "editor_enabled": true,
  "workflow_configuration": {
    "ai_editor_enabled": true,
    "ai_rewriter_enabled": true
  },
  "article_filtering": "accepted articles only"
}
```

## Performance Considerations

- **AI Editor Disabled**: Faster workflow, more articles published, no quality control
- **AI Rewriter Disabled**: Faster workflow, rejected articles stay rejected
- **Both Disabled**: Fastest workflow, all generated articles published immediately

## Use Cases

### Development/Testing
```python
ENABLE_AI_EDITOR = False
ENABLE_AI_REWRITER = False
```
Use this for rapid testing and development where you want to see all generated articles immediately.

### Production with Quality Control
```python
ENABLE_AI_EDITOR = True
ENABLE_AI_REWRITER = True
```
Use this for production where you want editorial review and article enhancement.

### High-Volume Publishing
```python
ENABLE_AI_EDITOR = False
ENABLE_AI_REWRITER = False
```
Use this when you want to publish many articles quickly without review delays.

## Troubleshooting

### Articles Not Appearing
- Check if `ENABLE_AI_EDITOR = True` and articles are still `not_reviewed`
- Check if `ENABLE_AI_EDITOR = False` and articles are `accepted` (they won't show)

### Workflow Not Running Components
- Verify the configuration flags are set correctly
- Check the workflow log for which steps are being executed
- Restart the backend server after configuration changes

### API Serving Wrong Articles
- Check the `editor_enabled` status in the root endpoint
- Verify the workflow configuration matches your expectations
- Check article states in the database
