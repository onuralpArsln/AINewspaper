#!/usr/bin/env python3
"""
Configuration Examples for AI Newspaper Workflow

This script demonstrates different configuration scenarios for the workflow.
Copy the desired configuration to workflow.py to use it.
"""

# =============================================================================
# EXAMPLE CONFIGURATIONS
# =============================================================================

# Example 1: Full AI Pipeline (Production with Quality Control)
FULL_AI_PIPELINE = {
    "ENABLE_RSS_SOURCE": False,
    "ENABLE_SCRAPER_SOURCE": True,
    "ENABLE_AI_EDITOR": True,
    "ENABLE_AI_REWRITER": True,
    "description": "Full AI pipeline with editorial review and rewriting"
}

# Example 2: Direct Publishing (No AI Review)
DIRECT_PUBLISHING = {
    "ENABLE_RSS_SOURCE": False,
    "ENABLE_SCRAPER_SOURCE": True,
    "ENABLE_AI_EDITOR": False,
    "ENABLE_AI_REWRITER": False,
    "description": "Direct publishing without AI review - all articles published immediately"
}

# Example 3: Editor Only (No Rewriting)
EDITOR_ONLY = {
    "ENABLE_RSS_SOURCE": False,
    "ENABLE_SCRAPER_SOURCE": True,
    "ENABLE_AI_EDITOR": True,
    "ENABLE_AI_REWRITER": False,
    "description": "Editorial review only - rejected articles stay rejected"
}

# Example 4: Development/Testing Mode
DEVELOPMENT_MODE = {
    "ENABLE_RSS_SOURCE": False,
    "ENABLE_SCRAPER_SOURCE": True,
    "ENABLE_AI_EDITOR": False,
    "ENABLE_AI_REWRITER": False,
    "description": "Development mode - fast publishing for testing"
}

# Example 5: RSS Only Mode
RSS_ONLY = {
    "ENABLE_RSS_SOURCE": True,
    "ENABLE_SCRAPER_SOURCE": False,
    "ENABLE_AI_EDITOR": True,
    "ENABLE_AI_REWRITER": True,
    "description": "RSS feeds only with full AI processing"
}

def print_configuration(config, name):
    """Print a configuration in a readable format"""
    print(f"\n{'='*60}")
    print(f"CONFIGURATION: {name}")
    print(f"{'='*60}")
    print(f"Description: {config['description']}")
    print(f"\nConfiguration values:")
    for key, value in config.items():
        if key != 'description':
            print(f"  {key} = {value}")
    
    print(f"\nWorkflow steps:")
    if config['ENABLE_RSS_SOURCE']:
        print("  ✓ RSS Processing")
    if config['ENABLE_SCRAPER_SOURCE']:
        print("  ✓ Web Scraper Processing")
    print("  ✓ Article Grouping")
    print("  ✓ AI Article Writing")
    if config['ENABLE_AI_EDITOR']:
        print("  ✓ AI Article Editing")
    if config['ENABLE_AI_REWRITER']:
        print("  ✓ AI Article Rewriting")
    
    print(f"\nAPI Behavior:")
    if config['ENABLE_AI_EDITOR']:
        print("  - Serves: accepted articles only")
        print("  - Article flow: not_reviewed → accepted/rejected")
    else:
        print("  - Serves: not_reviewed articles directly")
        print("  - Article flow: not_reviewed (no review)")

def main():
    """Display all configuration examples"""
    print("AI NEWSPAPER WORKFLOW CONFIGURATION EXAMPLES")
    print("=" * 60)
    print("Choose a configuration and copy the values to workflow.py")
    
    configs = [
        ("Full AI Pipeline", FULL_AI_PIPELINE),
        ("Direct Publishing", DIRECT_PUBLISHING),
        ("Editor Only", EDITOR_ONLY),
        ("Development Mode", DEVELOPMENT_MODE),
        ("RSS Only", RSS_ONLY)
    ]
    
    for name, config in configs:
        print_configuration(config, name)
    
    print(f"\n{'='*60}")
    print("HOW TO APPLY A CONFIGURATION:")
    print("=" * 60)
    print("1. Choose a configuration from above")
    print("2. Open workflow.py")
    print("3. Replace the configuration section with the chosen values")
    print("4. Restart the backend server")
    print("5. Check status at http://localhost:8000/")
    
    print(f"\n{'='*60}")
    print("EXAMPLE: Applying Direct Publishing Configuration")
    print("=" * 60)
    print("In workflow.py, change:")
    print("ENABLE_RSS_SOURCE = False")
    print("ENABLE_SCRAPER_SOURCE = True")
    print("ENABLE_AI_EDITOR = False")
    print("ENABLE_AI_REWRITER = False")

if __name__ == "__main__":
    main()
