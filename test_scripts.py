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
        config['project'] = 'STS'
    if 'error_project' not in config:
        config['error_project'] = 'RT'
    
    return config

def connect_jira(config):
    """Connect to Jira"""
    options = {'server': config['jira_url'], 'rest_api_version': '3'}
    return JIRA(options=options, basic_auth=(config['username'], config['api_token']))

def check_sla_breach(jira, ticket):
    """
    Check if both SLA goals are breached (Time to first response AND Time to resolution).
    
    Args:
        jira: JIRA client object
        ticket: Jira ticket object or ticket key
        
    Returns:
        True if both SLAs are breached, False otherwise
    """
    try:
        # Get ticket key if ticket object is passed
        ticket_key = ticket.key if hasattr(ticket, 'key') else ticket
        
        # Get full ticket with SLA fields
        full_ticket = jira.issue(ticket_key, fields='*all')
        
        print(f"\n  Checking SLA status for {ticket_key}...")
        
        # Helper function to convert PropertyHolder to dict
        def to_dict(obj):
            if hasattr(obj, '__dict__'):
                return obj.__dict__
            return obj
        
        # Try to find SLA fields - they vary by Jira configuration
        sla_fields = []
        for field_name in dir(full_ticket.fields):
            if 'customfield' in field_name:
                field_value = getattr(full_ticket.fields, field_name, None)
                
                # Convert PropertyHolder to dict
                if hasattr(field_value, '__dict__'):
                    field_value = to_dict(field_value)
                
                if field_value and isinstance(field_value, dict):
                    # Check if this looks like an SLA field
                    if 'ongoingCycle' in str(field_value) or 'completedCycles' in str(field_value):
                        sla_name = field_value.get('name', field_name)
                        sla_fields.append((field_name, sla_name, field_value))
        
        # If we found SLA fields, check for breaches
        if sla_fields:
            # Look specifically for these two SLAs
            time_to_first_response_breached = False
            time_to_resolution_breached = False
            
            time_to_first_response_found = False
            time_to_resolution_found = False
            
            for field_name, sla_name, field_value in sla_fields:
                if isinstance(field_value, dict):
                    sla_name_lower = sla_name.lower()
                    
                    # Check ongoing cycle
                    ongoing = field_value.get('ongoingCycle', {})
                    if ongoing:
                        ongoing = to_dict(ongoing)
                    
                    # Check completed cycles
                    completed = field_value.get('completedCycles', [])
                    
                    # Determine if this SLA is breached
                    is_breached = False
                    
                    # Ongoing and breached
                    if ongoing and isinstance(ongoing, dict) and ongoing.get('breached') == True:
                        is_breached = True
                        elapsed = to_dict(ongoing.get('elapsedTime', {}))
                        elapsed_friendly = elapsed.get('friendly', 'N/A') if isinstance(elapsed, dict) else 'N/A'
                        print(f"    SLA {sla_name}: ✗ BREACHED (elapsed: {elapsed_friendly})")
                    # Ongoing but not breached
                    elif ongoing and isinstance(ongoing, dict):
                        remaining = to_dict(ongoing.get('remainingTime', {}))
                        remaining_friendly = remaining.get('friendly', 'N/A') if isinstance(remaining, dict) else 'N/A'
                        print(f"    SLA {sla_name}: ✓ Not breached (remaining: {remaining_friendly})")
                    # Completed (always count as breached)
                    elif completed:
                        is_breached = True
                        for cycle in completed:
                            cycle = to_dict(cycle)
                            if isinstance(cycle, dict):
                                elapsed = to_dict(cycle.get('elapsedTime', {}))
                                elapsed_friendly = elapsed.get('friendly', 'N/A') if isinstance(elapsed, dict) else 'N/A'
                                goal = to_dict(cycle.get('goalDuration', {}))
                                goal_friendly = goal.get('friendly', 'N/A') if isinstance(goal, dict) else 'N/A'
                                print(f"    SLA {sla_name} (completed): ✗ BREACHED (elapsed: {elapsed_friendly} / goal: {goal_friendly})")
                    
                    # Map to specific SLA types
                    if 'first response' in sla_name_lower:
                        time_to_first_response_found = True
                        if is_breached:
                            time_to_first_response_breached = True
                    elif 'resolution' in sla_name_lower and 'close after' not in sla_name_lower:
                        time_to_resolution_found = True
                        if is_breached:
                            time_to_resolution_breached = True
            
            # Check if both required SLAs are found and breached
            if time_to_first_response_found and time_to_resolution_found:
                both_breached = time_to_first_response_breached and time_to_resolution_breached
                breached_count = (1 if time_to_first_response_breached else 0) + (1 if time_to_resolution_breached else 0)
                print(f"  → SLA Status: {'BOTH BREACHED ✗' if both_breached else 'Not both breached ✓'} ({breached_count}/2)")
                return both_breached
            else:
                missing = []
                if not time_to_first_response_found:
                    missing.append("Time to first response")
                if not time_to_resolution_found:
                    missing.append("Time to resolution")
                print(f"  → Warning: Required SLA(s) not found: {', '.join(missing)}")
                return False
        else:
            print(f"  → Warning: No SLA fields found for ticket")
            return False
            
    except Exception as e:
        print(f"  → Warning: Could not check SLA status: {str(e)}")
        return False


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

def test_sla_check():
    """Test 5: Check SLA breach status for a ticket"""
    print("\n" + "="*60)
    print("TEST 5: Check SLA Breach Status")
    print("="*60)
    
    config = load_config()
    jira = connect_jira(config)
    
    ticket_key = input("\nEnter ticket key to check SLA (e.g., RT-123): ").strip()
    
    if not ticket_key:
        print("No ticket key provided. Skipping test.")
        return
    
    try:
        ticket = jira.issue(ticket_key)
        print(f"\nFound ticket: {ticket.key} - {ticket.fields.summary}")
        print(f"Current status: {ticket.fields.status.name}")
        
        # Check SLA breach
        is_breached = check_sla_breach(jira, ticket)
        
        print("\n" + "="*60)
        if is_breached:
            print("RESULT: ✗ Both SLAs are BREACHED - Ticket would be closed by bot")
        else:
            print("RESULT: ✓ SLAs not breached - Ticket would NOT be closed")
        print("="*60)
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()

def test_list_closeable_tickets():
    """Test 6: List all tickets that can be closed based on SLA logic"""
    print("\n" + "="*60)
    print("TEST 6: List All Closeable Tickets")
    print("="*60)
    
    config = load_config()
    jira = connect_jira(config)
    
    days_threshold = config.get('days_threshold', 5)
    status_name = "Waiting for customer"
    project = config.get('project', None)
    
    print(f"\nSearching for closeable tickets...")
    print(f"Status: '{status_name}'")
    if project:
        print(f"Project: {project}")
    print(f"Criteria: Both SLAs breached/completed (2/2)")
    print(f"\nAnalyzing all tickets (no limit)...\n")
    
    # Build JQL query
    if project:
        jql_query = f'project = "{project}" AND status = "{status_name}"'
    else:
        jql_query = f'status = "{status_name}"'
    
    try:
        # Search for ALL tickets (paginated)
        import requests
        url = f"{config['jira_url']}/rest/api/3/search/jql"
        headers = {"Accept": "application/json"}
        auth = (config['username'], config['api_token'])
        
        all_tickets = []
        start_at = 0
        max_results = 100
        
        while True:
            params = {
                "jql": jql_query,
                "startAt": start_at,
                "maxResults": max_results,
                "fields": "summary,status,created"
            }
            
            response = requests.get(url, headers=headers, auth=auth, params=params)
            response.raise_for_status()
            data = response.json()
            
            tickets = data.get('issues', [])
            all_tickets.extend(tickets)
            
            total = data.get('total', 0)
            
            if start_at + max_results >= total:
                break
            
            start_at += max_results
        
        if not all_tickets:
            print("✓ No tickets found in 'Waiting for customer' status.")
            return
        
        print(f"Found {len(all_tickets)} total ticket(s) in '{status_name}' status")
        print("Checking SLA status for closeable tickets only...\n")
        
        closeable_tickets = []
        
        # Check each ticket but only print closeable ones
        for i, ticket_data in enumerate(all_tickets, 1):
            ticket_key = ticket_data['key']
            ticket_summary = ticket_data['fields']['summary']
            
            # Show progress every 10 tickets
            if i % 10 == 0:
                print(f"Progress: {i}/{len(all_tickets)} tickets checked...")
            
            # Check SLA breach silently
            try:
                ticket = jira.issue(ticket_key, fields='*all')
                
                # Helper function to convert PropertyHolder to dict
                def to_dict(obj):
                    if hasattr(obj, '__dict__'):
                        return obj.__dict__
                    return obj
                
                # Find SLA fields
                sla_fields = []
                for field_name in dir(ticket.fields):
                    if 'customfield' in field_name:
                        field_value = getattr(ticket.fields, field_name, None)
                        
                        if hasattr(field_value, '__dict__'):
                            field_value = to_dict(field_value)
                        
                        if field_value and isinstance(field_value, dict):
                            if 'ongoingCycle' in str(field_value) or 'completedCycles' in str(field_value):
                                sla_name = field_value.get('name', field_name)
                                sla_fields.append((field_name, sla_name, field_value))
                
                # Check for breaches - look for specific SLAs
                time_to_first_response_breached = False
                time_to_resolution_breached = False
                
                time_to_first_response_found = False
                time_to_resolution_found = False
                
                for field_name, sla_name, field_value in sla_fields:
                    if isinstance(field_value, dict):
                        sla_name_lower = sla_name.lower()
                        
                        # Check ongoing cycle
                        ongoing = field_value.get('ongoingCycle', {})
                        if ongoing:
                            ongoing = to_dict(ongoing)
                        
                        # Check completed cycles
                        completed = field_value.get('completedCycles', [])
                        
                        # Determine if this SLA is breached
                        is_breached = False
                        
                        # Ongoing and breached
                        if ongoing and isinstance(ongoing, dict) and ongoing.get('breached') == True:
                            is_breached = True
                        # Completed (always count as breached)
                        elif completed:
                            is_breached = True
                        
                        # Map to specific SLA types
                        if 'first response' in sla_name_lower:
                            time_to_first_response_found = True
                            if is_breached:
                                time_to_first_response_breached = True
                        elif 'resolution' in sla_name_lower and 'close after' not in sla_name_lower:
                            time_to_resolution_found = True
                            if is_breached:
                                time_to_resolution_breached = True
                
                # Add to closeable if both required SLAs are found and breached
                if time_to_first_response_found and time_to_resolution_found:
                    if time_to_first_response_breached and time_to_resolution_breached:
                        closeable_tickets.append((ticket_key, ticket_summary))
                    
            except Exception as e:
                # Skip tickets with errors
                pass
        
        # Final Summary
        print("\n" + "="*80)
        print("CLOSEABLE TICKETS - READY TO BE CLOSED")
        print("="*80)
        
        if closeable_tickets:
            print(f"\nFound {len(closeable_tickets)} ticket(s) that meet criteria (2/2 SLA breached/completed):\n")
            for i, (key, summary) in enumerate(closeable_tickets, 1):
                print(f"{i}. {key}")
                print(f"   {summary}")
                print(f"   URL: {config['jira_url']}/browse/{key}\n")
        else:
            print("\n✓ No tickets meet the closure criteria at this time.")
            print("  All tickets have active SLAs that are not yet breached.\n")
        
        print("="*80)
        print(f"Summary: {len(closeable_tickets)} closeable out of {len(all_tickets)} total in '{status_name}' status")
        print("="*80)
        
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
        print("5. Check SLA Breach Status")
        print("6. List All Closeable Tickets (by SLA)")
        print("7. Run ALL Tests")
        print("0. Exit")
        
        choice = input("\nSelect test (0-7): ").strip()
        
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
            test_sla_check()
        elif choice == '6':
            test_list_closeable_tickets()
        elif choice == '7':
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
            input("\nPress Enter to continue to next test...")
            test_sla_check()
            input("\nPress Enter to continue to next test...")
            test_list_closeable_tickets()
            print("\n✓ All tests completed!")
        else:
            print("Invalid choice. Please select 0-7.")

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
