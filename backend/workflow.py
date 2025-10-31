#!/usr/bin/env python3
"""
Workflow Orchestrator
Executes the complete article processing pipeline in sequence
"""

import sys
import os
from datetime import datetime
from typing import Dict, Any

# Resolve script directory for log file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, 'workflow_log.txt')

# Import all modules
import rss2db
import scraper2db
import group_articles
import ai_writer
import ai_editor
import ai_rewriter

# =============================================================================
# WORKFLOW CONFIGURATION
# =============================================================================

# Source Configuration - Enable/Disable Data Sources
ENABLE_RSS_SOURCE = False      # Enable RSS feed processing (rss2db.py)
ENABLE_SCRAPER_SOURCE = True  # Enable web scraper processing (scraper2db.py)

# AI Processing Configuration - Enable/Disable AI Components
ENABLE_AI_EDITOR = False    # Enable AI article editor (ai_editor.py)
ENABLE_AI_REWRITER = ENABLE_AI_EDITOR      # Enable AI article rewriter (ai_rewriter.py)

# =============================================================================

def log_to_file(message: str, log_file: str = LOG_FILE):
    """Log message to file with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] {message}\n"
    
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Error writing to log file: {e}")

def run_workflow() -> Dict[str, Any]:
    """Execute complete workflow pipeline"""
    start_time = datetime.now()
    log_file = LOG_FILE
    
    # Initialize log file
    log_to_file("=" * 80, log_file)
    log_to_file("WORKFLOW EXECUTION STARTED", log_file)
    log_to_file(f"RSS Source: {'ENABLED' if ENABLE_RSS_SOURCE else 'DISABLED'}", log_file)
    log_to_file(f"Scraper Source: {'ENABLED' if ENABLE_SCRAPER_SOURCE else 'DISABLED'}", log_file)
    log_to_file(f"AI Editor: {'ENABLED' if ENABLE_AI_EDITOR else 'DISABLED'}", log_file)
    log_to_file(f"AI Rewriter: {'ENABLED' if ENABLE_AI_REWRITER else 'DISABLED'}", log_file)
    log_to_file("=" * 80, log_file)
    
    # Define workflow steps - conditionally include sources
    workflow_steps = []

    # Add data collection sources based on configuration
    if ENABLE_RSS_SOURCE:
        workflow_steps.append({
            'name': 'rss2db',
            'description': 'RSS to Database Processing',
            'function': rss2db.run,
            'args': {}
        })

    if ENABLE_SCRAPER_SOURCE:
        workflow_steps.append({
            'name': 'scraper2db',
            'description': 'Web Scraper to Database Processing',
            'function': scraper2db.run,
            'args': {}
        })

    # Add processing steps (always enabled)
    workflow_steps.extend([
        {
            'name': 'group_articles',
            'description': 'Article Grouping',
            'function': group_articles.run,
            'args': {}
        },
        {
            'name': 'ai_writer',
            'description': 'AI Article Writing',
            'function': ai_writer.run,
            'args': {}
        }
    ])
    
    # Add AI processing steps based on configuration
    if ENABLE_AI_EDITOR:
        workflow_steps.append({
            'name': 'ai_editor',
            'description': 'AI Article Editing',
            'function': ai_editor.run,
            'args': {}
        })
    
    if ENABLE_AI_REWRITER:
        workflow_steps.append({
            'name': 'ai_rewriter',
            'description': 'AI Article Rewriting',
            'function': ai_rewriter.run,
            'args': {}
        })
    
    results = {
        'start_time': start_time.isoformat(),
        'steps': {},
        'success_count': 0,
        'failure_count': 0,
        'total_steps': len(workflow_steps)  # Dynamic count
    }
    
    print("=" * 80)
    print("WORKFLOW EXECUTION STARTED")
    print("=" * 80)
    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Log file: {log_file}")
    print()
    
    # Execute each step
    for i, step in enumerate(workflow_steps, 1):
        step_name = step['name']
        step_desc = step['description']
        step_func = step['function']
        step_args = step['args']
        
        print(f"Step {i}/{len(workflow_steps)}: {step_desc}")
        print("-" * 60)
        
        step_start_time = datetime.now()
        log_to_file(f"Starting step {i}: {step_desc}", log_file)
        
        # Check database state before ai_writer step
        if step_name == 'ai_writer':
            try:
                writer = ai_writer.AIWriter()
                stats = writer.get_writing_statistics()
                log_to_file(f"Database state before AI Writer:", log_file)
                log_to_file(f"  - Total RSS articles: {stats['total_rss_articles']}", log_file)
                log_to_file(f"  - Unread articles: {stats['unread_rss_articles']}", log_file)
                log_to_file(f"  - Read articles: {stats['read_rss_articles']}", log_file)
                log_to_file(f"  - Our articles (existing): {stats['our_articles_count']}", log_file)
                
                print(f"Database state before AI Writer:")
                print(f"  - Total RSS articles: {stats['total_rss_articles']}")
                print(f"  - Unread articles: {stats['unread_rss_articles']}")
                print(f"  - Read articles: {stats['read_rss_articles']}")
                
                if stats['unread_rss_articles'] == 0:
                    warning_msg = "WARNING: No unread articles available! AI Writer may generate 0 articles."
                    log_to_file(warning_msg, log_file)
                    print(f"  ⚠️  {warning_msg}")
                elif stats['unread_rss_articles'] < 5:
                    info_msg = f"Info: Only {stats['unread_rss_articles']} unread articles available (target is usually 5)."
                    log_to_file(info_msg, log_file)
                    print(f"  ℹ️  {info_msg}")
                print()
            except Exception as e:
                log_to_file(f"Error checking database state before ai_writer: {e}", log_file)
                print(f"  ⚠️  Could not check database state: {e}")
        
        try:
            # Execute the step
            result = step_func(**step_args)
            
            step_end_time = datetime.now()
            step_duration = (step_end_time - step_start_time).total_seconds()
            
            # Log success
            log_to_file(f"Step {i} COMPLETED SUCCESSFULLY in {step_duration:.2f} seconds", log_file)
            
            # Special handling for AI writer statistics
            if step_name == 'ai_writer' and isinstance(result, dict) and 'ai_trials' in result:
                log_to_file(f"AI Writer Statistics:", log_file)
                log_to_file(f"  - Articles generated: {result['articles_generated']}/{result['articles_target']}", log_file)
                log_to_file(f"  - AI trials made: {result['ai_trials']}", log_file)
                log_to_file(f"  - Articles skipped: {result['articles_skipped']}", log_file)
                log_to_file(f"  - Success rate: {result['success_rate']}%", log_file)
                log_to_file(f"  - Processed groups: {result['processed_groups']}", log_file)
                
                # Highlight if zero articles generated
                if result['articles_generated'] == 0:
                    warning_msg = "⚠️  WARNING: AI Writer generated ZERO articles!"
                    log_to_file(warning_msg, log_file)
                    log_to_file(f"  This may indicate:", log_file)
                    log_to_file(f"    - No unread articles were available", log_file)
                    log_to_file(f"    - All articles failed validation or AI generation", log_file)
                    log_to_file(f"    - Articles were skipped due to processing errors", log_file)
            
            # Store results
            results['steps'][step_name] = {
                'status': 'SUCCESS',
                'start_time': step_start_time.isoformat(),
                'end_time': step_end_time.isoformat(),
                'duration': step_duration,
                'result': result,
                'error': None
            }
            
            results['success_count'] += 1
            
            print(f"+ {step_desc} completed successfully in {step_duration:.2f} seconds")
            
            # Print AI writer statistics to console as well
            if step_name == 'ai_writer' and isinstance(result, dict) and 'ai_trials' in result:
                print(f"  AI Writer Results:")
                print(f"    Articles generated: {result['articles_generated']}/{result['articles_target']}")
                print(f"    AI trials made: {result['ai_trials']}")
                print(f"    Articles skipped: {result['articles_skipped']}")
                print(f"    Success rate: {result['success_rate']}%")
                print(f"    Processed groups: {result['processed_groups']}")
                
                # Highlight if zero articles generated
                if result['articles_generated'] == 0:
                    print(f"    ⚠️  WARNING: Zero articles generated!")
                    if result['ai_trials'] > 0:
                        print(f"    ⚠️  {result['ai_trials']} AI trials were made but all failed or were skipped")
                    if result['articles_skipped'] > 0:
                        print(f"    ⚠️  {result['articles_skipped']} articles were skipped during processing")
                    print(f"    💡 Check the logs above for detailed skip reasons")
            
        except Exception as e:
            step_end_time = datetime.now()
            step_duration = (step_end_time - step_start_time).total_seconds()
            
            # Log error
            error_msg = f"Step {i} FAILED: {str(e)}"
            log_to_file(error_msg, log_file)
            
            # Store error results
            results['steps'][step_name] = {
                'status': 'FAILED',
                'start_time': step_start_time.isoformat(),
                'end_time': step_end_time.isoformat(),
                'duration': step_duration,
                'result': None,
                'error': str(e)
            }
            
            results['failure_count'] += 1
            
            print(f"- {step_desc} failed: {str(e)}")
            print(f"  Duration: {step_duration:.2f} seconds")
            print(f"  Continuing with next step...")
        
        print()
    
    # Calculate total duration
    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()
    results['end_time'] = end_time.isoformat()
    results['total_duration'] = total_duration
    
    # Log final summary
    log_to_file("=" * 80, log_file)
    log_to_file("WORKFLOW EXECUTION COMPLETED", log_file)
    log_to_file(f"Total duration: {total_duration:.2f} seconds", log_file)
    log_to_file(f"Successful steps: {results['success_count']}/{results['total_steps']}", log_file)
    log_to_file(f"Failed steps: {results['failure_count']}/{results['total_steps']}", log_file)
    log_to_file("=" * 80, log_file)
    
    # Print final summary
    print("=" * 80)
    print("WORKFLOW EXECUTION COMPLETED")
    print("=" * 80)
    print(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total duration: {total_duration:.2f} seconds")
    print(f"Successful steps: {results['success_count']}/{results['total_steps']}")
    print(f"Failed steps: {results['failure_count']}/{results['total_steps']}")
    print()
    
    # Print step summary
    print("STEP SUMMARY:")
    print("-" * 40)
    for step_name, step_result in results['steps'].items():
        status_icon = "+" if step_result['status'] == 'SUCCESS' else "-"
        duration = step_result['duration']
        print(f"{status_icon} {step_name}: {step_result['status']} ({duration:.2f}s)")
        if step_result['error']:
            print(f"    Error: {step_result['error']}")
    
    print()
    print(f"Detailed log saved to: {log_file}")
    print("=" * 80)
    
    return results

def main():
    """Main function for command line usage"""
    try:
        results = run_workflow()
        
        # Exit with appropriate code
        if results['failure_count'] > 0:
            print(f"\nWorkflow completed with {results['failure_count']} failures.")
            return 1
        else:
            print("\nWorkflow completed successfully!")
            return 0
            
    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user.")
        log_to_file("Workflow interrupted by user", LOG_FILE)
        return 1
    except Exception as e:
        print(f"\nUnexpected error in workflow: {e}")
        log_to_file(f"Unexpected workflow error: {e}", LOG_FILE)
        return 1

if __name__ == "__main__":
    exit(main())
