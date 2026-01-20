"""
Test Script for Jira Auto-Close Bot
====================================
This script tests various scenarios including:
1. Force closing tickets (bypassing days threshold)
2. Testing error handling and bug ticket creation
3. Creating test tickets and simulating failures
"""

import json
import sys
from jira import JIRA
from datetime import datetime, timedelta

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Set default project to RT if not specified
    if 'project' not in config:
        config['project'] = 'RT'
    if 'error_project' not in config:
        config['error_project'] = 'RT'
    
    return config

def connect_jira(config):
    """Connect to Jira"""
    options = {'server': config['jira_url'], 'rest_api_version': '3'}
    return JIRA(options=options, basic_auth=(config['username'], config['api_token']))

def test_force_close_ticket():
    """Test 1: Force close a specific ticket regardless of days"""
    print("\n" + "="*60)
    print("TEST 1: Force Close Ticket")
    print("="*60)
    
    config = load_config()
    jira = connect_jira(config)
    
    ticket_key = input("\nEnter ticket key to force close (e.g., DEV-7): ").strip()
    
    if not ticket_key:
        print("No ticket key provided. Skipping test.")
        return
    
    try:
        ticket = jira.issue(ticket_key)
        print(f"\nFound ticket: {ticket.key} - {ticket.fields.summary}")
        print(f"Current status: {ticket.fields.status.name}")
        
        confirm = input(f"\nForce close {ticket_key}? (yes/no): ").lower()
        if confirm != 'yes':
            print("Cancelled.")
            return
        
        # Assign
        print(f"\nAssigning to {config['username']}...")
        jira.assign_issue(ticket, config['username'])
        print("✓ Assigned")
        
        # Get transitions
        transitions = jira.transitions(ticket)
        print(f"\nAvailable transitions: {[t['name'] for t in transitions]}")
        
        # Find Done transition
        done_transition = None
        for t in transitions:
            if t['name'].lower() in ['done', 'close', 'closed']:
                done_transition = t['id']
                break
        
        if done_transition:
            print(f"\nAdding comment...")
            # Add comment using API v3 format with standard auto-close message
            import requests
            
            # For test purposes, use 0 days threshold
            days_threshold = 0
            comment_text = (
                f"This ticket has been automatically closed because it has been "
                f"in 'Waiting for Customer' status for more than {days_threshold} working days "
                f"(1 working days since {(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')}).\n\n"
                f"If you still need assistance, please open a new ticket."
            )
            
            url = f"{config['jira_url']}/rest/api/3/issue/{ticket_key}/comment"
            comment_body = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": comment_text
                                }
                            ]
                        }
                    ]
                }
            }
            
            response = requests.post(
                url, 
                json=comment_body, 
                auth=(config['username'], config['api_token']),
                headers={"Content-Type": "application/json"}
            )
            print("✓ Comment added")
            
            print(f"\nTransitioning to Done...")
            jira.transition_issue(ticket, done_transition)
            print(f"✓ Ticket {ticket_key} force closed successfully!")
        else:
            print(f"✗ No Done/Close transition found")
            
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")

def test_error_bug_ticket_creation():
    """Test 2: Simulate an error and test bug ticket creation"""
    print("\n" + "="*60)
    print("TEST 2: Simulate Error & Bug Ticket Creation")
    print("="*60)
    
    config = load_config()
    jira = connect_jira(config)
    
    print("\nThis will simulate an error in the bot and create a Bug ticket.")
    confirm = input("Continue? (yes/no): ").lower()
    if confirm != 'yes':
        print("Cancelled.")
        return
    
    # Simulate error
    error_type = "TestError"
    error_message = "This is a simulated error for testing purposes"
    
    try:
        print("\nSimulating bot error...")
        
        # Create bug ticket
        error_summary = f"Auto-Close Bot Error: {error_type}"
        error_description = f"""
The Jira Auto-Close Bot encountered an error during execution.

**Error Type:** {error_type}
**Error Message:** {error_message}

**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Test Info:** This is a TEST error ticket created by test_scripts.py

**Configuration:**
- Days threshold: {config.get('days_threshold', 5)}
- Dry run: {config.get('dry_run', True)}

Please verify that error handling works correctly.
"""
        
        print("\nCreating Bug ticket in Jira...")
        
        import platform
        import sys
        
        environment_info = f"Python: {sys.version}\nOS: {platform.system()} {platform.release()}\nPlatform: {platform.platform()}"
        
        # Convert text to Atlassian Document Format for Cloud API v3
        description_adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": error_message
                        }
                    ]
                }
            ]
        }
        
        environment_adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": environment_info
                        }
                    ]
                }
            ]
        }
        
        bug_ticket = jira.create_issue(
            project=config.get('error_project', 'DEV'),
            summary=error_summary,
            description=description_adf,
            issuetype={'name': 'Bug'},
            priority={'name': 'High'},
            labels=['auto-bot', 'error', 'test'],
            environment=environment_adf
        )
        
        # Add comment with description (using API v3 format)
        import requests
        url = f"{config['jira_url']}/rest/api/3/issue/{bug_ticket.key}/comment"
        comment_body = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": error_description
                            }
                        ]
                    }
                ]
            }
        }
        
        response = requests.post(
            url, 
            json=comment_body, 
            auth=(config['username'], config['api_token']),
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\n✓ Bug ticket created: {bug_ticket.key}")
        print(f"   Summary: {error_summary}")
        print(f"   URL: {config['jira_url']}/browse/{bug_ticket.key}")
        
    except Exception as e:
        print(f"\n✗ Error creating bug ticket: {str(e)}")
        import traceback
        traceback.print_exc()

def test_create_waiting_ticket():
    """Test 3: Create a new ticket in Waiting for customer status"""
    print("\n" + "="*60)
    print("TEST 3: Create Test Ticket in 'Waiting for customer'")
    print("="*60)
    
    config = load_config()
    jira = connect_jira(config)
    
    print("\nThis will create a new test ticket in 'Waiting for customer' status.")
    confirm = input("Continue? (yes/no): ").lower()
    if confirm != 'yes':
        print("Cancelled.")
        return
    
    try:
        # Create ticket
        print("\nCreating test ticket...")
        issue = jira.create_issue(
            project=config['project'],
            summary=f'Test ticket - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            issuetype={'name': 'Task'}
        )
        
        print(f"✓ Created: {issue.key}")
        
        # Transition to Waiting for customer
        transitions = jira.transitions(issue)
        waiting_transition = None
        
        for t in transitions:
            if 'waiting' in t['name'].lower():
                waiting_transition = t['id']
                break
        
        if waiting_transition:
            print(f"\nTransitioning to 'Waiting for customer'...")
            jira.transition_issue(issue, waiting_transition)
            print(f"✓ Status changed to: {jira.issue(issue.key).fields.status.name}")
            print(f"\n✓ Test ticket ready: {config['jira_url']}/browse/{issue.key}")
        else:
            print(f"\n✗ Could not find 'Waiting for customer' transition")
            print(f"   Available: {[t['name'] for t in transitions]}")
            
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()

def test_invalid_config():
    """Test 4: Test with invalid configuration (should log error)"""
    print("\n" + "="*60)
    print("TEST 4: Test Invalid Configuration Error Handling")
    print("="*60)
    
    print("\nThis will test error handling with invalid Jira URL and create a Bug ticket.")
    confirm = input("Continue? (yes/no): ").lower()
    if confirm != 'yes':
        print("Cancelled.")
        return
    
    config = load_config()
    error_type = None
    error_message = None
    
    try:
        print("\nAttempting to connect with invalid URL...")
        options = {'server': 'https://invalid-jira-url.example.com', 'rest_api_version': '3'}
        jira_test = JIRA(options=options, basic_auth=('test@example.com', 'invalid_token'))
        
        # Try to search
        jira_test.search_issues('project=TEST', maxResults=1)
        
    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        print(f"\n✓ Error caught successfully (as expected):")
        print(f"   {error_type}: {error_message}")
        
        # Now create a Bug ticket using valid credentials
        try:
            print("\n✓ Creating Bug ticket for this error...")
            jira = connect_jira(config)
            
            error_summary = f"Auto-Close Bot Error: {error_type}"
            error_description = f"""
The Jira Auto-Close Bot encountered an error during execution.

**Error Type:** {error_type}
**Error Message:** {error_message}

**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Test Info:** This is a TEST error ticket created by test_scripts.py - Test 4 (Invalid Configuration)

**Configuration:**
- Days threshold: {config.get('days_threshold', 5)}
- Dry run: {config.get('dry_run', True)}

This error was simulated by attempting to connect to an invalid Jira URL.
"""
            
            import platform
            import sys
            
            environment_info = f"Python: {sys.version}\nOS: {platform.system()} {platform.release()}\nPlatform: {platform.platform()}"
            
            # Convert text to Atlassian Document Format for Cloud API v3
            description_adf = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": error_message
                            }
                        ]
                    }
                ]
            }
            
            environment_adf = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": environment_info
                            }
                        ]
                    }
                ]
            }
            
            bug_ticket = jira.create_issue(
                project=config.get('error_project', 'DEV'),
                summary=error_summary,
                description=description_adf,
                issuetype={'name': 'Bug'},
                priority={'name': 'High'},
                labels=['auto-bot', 'error', 'test', 'config-test'],
                environment=environment_adf
            )
            
            # Add comment with description (using API v3 format)
            import requests
            url = f"{config['jira_url']}/rest/api/3/issue/{bug_ticket.key}/comment"
            comment_body = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": error_description
                                }
                            ]
                        }
                    ]
                }
            }
            
            response = requests.post(
                url, 
                json=comment_body, 
                auth=(config['username'], config['api_token']),
                headers={"Content-Type": "application/json"}
            )
            
            print(f"\n✓ Bug ticket created: {bug_ticket.key}")
            print(f"   Summary: {error_summary}")
            print(f"   URL: {config['jira_url']}/browse/{bug_ticket.key}")
            
        except Exception as bug_error:
            print(f"\n✗ Error creating bug ticket: {str(bug_error)}")
            import traceback
            traceback.print_exc()

def main_menu():
    """Main menu for test selection"""
    while True:
        print("\n" + "="*60)
        print("JIRA AUTO-CLOSE BOT - TEST SCRIPTS")
        print("="*60)
        print("\n1. Force Close Specific Ticket")
        print("2. Simulate Error & Create Bug Ticket")
        print("3. Create Test Ticket in 'Waiting for customer'")
        print("4. Test Invalid Configuration Error Handling")
        print("5. Run ALL Tests")
        print("0. Exit")
        
        choice = input("\nSelect test (0-5): ").strip()
        
        if choice == '0':
            print("\nExiting...")
            break
        elif choice == '1':
            test_force_close_ticket()
        elif choice == '2':
            test_error_bug_ticket_creation()
        elif choice == '3':
            test_create_waiting_ticket()
        elif choice == '4':
            test_invalid_config()
        elif choice == '5':
            print("\n" + "="*60)
            print("RUNNING ALL TESTS")
            print("="*60)
            test_create_waiting_ticket()
            input("\nPress Enter to continue to next test...")
            test_force_close_ticket()
            input("\nPress Enter to continue to next test...")
            test_error_bug_ticket_creation()
            input("\nPress Enter to continue to next test...")
            test_invalid_config()
            print("\n✓ All tests completed!")
        else:
            print("Invalid choice. Please select 0-5.")

if __name__ == '__main__':
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
