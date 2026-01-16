"""
Jira Auto-Close Bot
Automatically closes Jira tickets that have been in "Waiting for Customer" status 
for more than 5 working days (excluding weekends).
"""

import os
import sys
from datetime import datetime, timedelta
from jira import JIRA
import json


class JiraAutoCloseBot:
    def __init__(self, jira_url, username, api_token):
        """
        Initialize the Jira bot.
        
        Args:
            jira_url: Jira instance URL (e.g., 'https://yourcompany.atlassian.net')
            username: Bot account email
            api_token: API token for authentication
        """
        options = {'server': jira_url, 'rest_api_version': '3'}
        self.jira = JIRA(options=options, basic_auth=(username, api_token))
        self.bot_username = username
        
    def is_working_day(self, date):
        """Check if a date is a working day (Monday-Friday)."""
        return date.weekday() < 5  # 0-4 are Monday-Friday
    
    def calculate_working_days(self, start_date, end_date):
        """
        Calculate the number of working days between two dates.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Number of working days
        """
        working_days = 0
        current_date = start_date
        
        while current_date < end_date:
            if self.is_working_day(current_date):
                working_days += 1
            current_date += timedelta(days=1)
            
        return working_days
    
    def find_old_waiting_tickets(self, days_threshold=5, status_name="Waiting for customer"):
        """
        Find tickets that have been in "Waiting for customer" status 
        for more than the specified working days.
        
        Args:
            days_threshold: Number of working days threshold (default: 5)
            status_name: Status name to check (default: "Waiting for customer")
            
        Returns:
            List of tickets to close
        """
        # JQL query to find tickets in specified status
        jql_query = f'status = "{status_name}"'
        
        print(f"Searching for tickets with status: {status_name}")
        try:
            tickets = self.jira.search_issues(jql_query, maxResults=1000)
        except Exception as e:
            print(f"✗ Error searching for tickets: {str(e)}")
            print(f"  Returning empty list and will retry on next run")
            return []
        
        tickets_to_close = []
        now = datetime.now()
        
        for ticket in tickets:
            try:
                # Get the history of status changes
                changelog = self.jira.issue(ticket.key, expand='changelog').changelog
                
                # Find the last time the status changed to "Waiting for Customer"
                last_status_change = None
                for history in reversed(changelog.histories):
                    for item in history.items:
                        if item.field == 'status' and item.toString == status_name:
                            last_status_change = datetime.strptime(
                                history.created, 
                                '%Y-%m-%dT%H:%M:%S.%f%z'
                            ).replace(tzinfo=None)
                            break
                    if last_status_change:
                        break
                
                if last_status_change:
                    working_days = self.calculate_working_days(last_status_change, now)
                    
                    print(f"Ticket {ticket.key}: {working_days} working days in {status_name}")
                    
                    if working_days > days_threshold:
                        tickets_to_close.append({
                            'ticket': ticket,
                            'days': working_days,
                            'status_changed': last_status_change
                        })
            except Exception as e:
                print(f"✗ Error processing ticket {ticket.key}: {str(e)}")
                print(f"  Skipping this ticket and continuing with others...")
                continue
        
        return tickets_to_close
    
    def close_ticket(self, ticket_key, comment_text=None):
        """
        Close a ticket by assigning it to the bot and transitioning to closed status.
        
        Args:
            ticket_key: Jira ticket key (e.g., 'PROJ-123')
            comment_text: Optional comment to add when closing
        """
        try:
            print(f"\nProcessing {ticket_key}...")
            ticket = self.jira.issue(ticket_key)
            
            # Assign ticket to bot account
            try:
                print(f"  Assigning to bot account...")
                self.jira.assign_issue(ticket, self.bot_username)
                print(f"  ✓ Assigned")
            except Exception as e:
                print(f"  Warning: Could not assign ticket: {str(e)}")
                print(f"  Continuing with close operation...")
            
            # Add comment explaining the auto-close (Jira Cloud API v3 format)
            if comment_text:
                try:
                    print(f"  Adding comment...")
                    import requests
                    url = f"{self.jira._options['server']}/rest/api/3/issue/{ticket_key}/comment"
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
                        auth=(self.bot_username, self.jira._session.auth[1]),
                        headers={"Content-Type": "application/json"}
                    )
                    if response.status_code in [200, 201]:
                        print(f"  ✓ Comment added")
                    else:
                        print(f"  Warning: Could not add comment (status {response.status_code})")
                except Exception as e:
                    print(f"  Warning: Could not add comment: {str(e)}")
                    print(f"  Continuing with close operation...")
            
            # Get available transitions
            transitions = self.jira.transitions(ticket)
            
            # Find the "Close" or "Closed" transition
            close_transition = None
            for transition in transitions:
                transition_name = transition['name'].lower()
                if transition_name in ['close', 'closed', 'close issue', 'done']:
                    close_transition = transition['id']
                    break
            
            if close_transition:
                try:
                    print(f"  Closing ticket...")
                    self.jira.transition_issue(ticket, close_transition)
                    print(f"✓ Ticket {ticket_key} closed successfully")
                    return True
                except Exception as e:
                    print(f"✗ Error transitioning {ticket_key}: {str(e)}")
                    return False
            else:
                print(f"✗ Could not find close transition for {ticket_key}")
                print(f"  Available transitions: {[t['name'] for t in transitions]}")
                return False
                
        except Exception as e:
            print(f"✗ Error closing ticket {ticket_key}: {str(e)}")
            print(f"  This ticket will be skipped, continuing with others...")
            return False
    
    def run(self, days_threshold=5, dry_run=False):
        """
        Main execution method.
        
        Args:
            days_threshold: Number of working days before auto-closing (default: 5)
            dry_run: If True, only report tickets but don't close them
        """
        print("=" * 60)
        print("Jira Auto-Close Bot - Starting...")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Threshold: {days_threshold} working days")
        print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        print("=" * 60)
        
        # Check if today is a working day
        today = datetime.now()
        if not self.is_working_day(today):
            print("Today is a weekend. Skipping execution.")
            return
        
        # Find tickets to close
        tickets_to_close = self.find_old_waiting_tickets(days_threshold)
        
        if not tickets_to_close:
            print("\nNo tickets found that meet the criteria.")
            return
        
        print(f"\nFound {len(tickets_to_close)} ticket(s) to close:")
        for item in tickets_to_close:
            ticket = item['ticket']
            print(f"  - {ticket.key}: {ticket.fields.summary}")
            print(f"    Status changed: {item['status_changed'].strftime('%Y-%m-%d')}")
            print(f"    Working days: {item['days']}")
        
        if dry_run:
            print("\n[DRY RUN] No tickets were closed.")
            return
        
        # Close tickets
        print("\nClosing tickets...")
        closed_count = 0
        for item in tickets_to_close:
            ticket = item['ticket']
            comment = (
                f"This ticket has been automatically closed because it has been "
                f"in 'Waiting for Customer' status for more than {days_threshold} working days "
                f"({item['days']} working days since {item['status_changed'].strftime('%Y-%m-%d')}).\n\n"
                f"If you still need assistance, please open a new ticket."
            )
            
            if self.close_ticket(ticket.key, comment):
                closed_count += 1
        
        print("\n" + "=" * 60)
        print(f"Summary: Closed {closed_count} out of {len(tickets_to_close)} ticket(s)")
        print("=" * 60)


def main():
    """Main entry point."""
    # Load configuration
    config_file = os.path.join(os.path.dirname(__file__), 'config.json')
    
    if not os.path.exists(config_file):
        print("Error: config.json not found!")
        print("Please create a config.json file with your Jira credentials.")
        sys.exit(1)
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Validate configuration
    required_fields = ['jira_url', 'username', 'api_token']
    for field in required_fields:
        if field not in config:
            print(f"Error: '{field}' not found in config.json")
            sys.exit(1)
    
    # Initialize bot
    bot = JiraAutoCloseBot(
        jira_url=config['jira_url'],
        username=config['username'],
        api_token=config['api_token']
    )
    
    # Get parameters from config or use defaults
    days_threshold = config.get('days_threshold', 5)
    dry_run = config.get('dry_run', False)
    
    # Run bot
    try:
        bot.run(days_threshold=days_threshold, dry_run=dry_run)
    except Exception as e:
        print("\n" + "=" * 60)
        print("ERROR: Bot execution failed")
        print("=" * 60)
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        
        # Log detailed error
        import traceback
        print("\nDetailed traceback:")
        traceback.print_exc()
        
        # Try to create error ticket in Jira
        try:
            error_summary = f"Auto-Close Bot Error: {type(e).__name__}"
            error_description = f"""
The Jira Auto-Close Bot encountered an error during execution.

**Error Type:** {type(e).__name__}
**Error Message:** {str(e)}

**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Configuration:**
- Days threshold: {days_threshold}
- Dry run: {dry_run}

**Stack Trace:**
{traceback.format_exc()}

Please investigate and fix the issue.
"""
            
            # Create error ticket (only if not in dry_run mode)
            if not dry_run:
                import platform
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
                
                error_ticket = bot.jira.create_issue(
                    project=config.get('error_project', 'DEV'),
                    summary=error_summary,
                    description=description_adf,
                    issuetype={'name': 'Bug'},
                    priority={'name': 'High'},
                    labels=['auto-bot', 'error'],
                    environment=environment_adf
                )
                print(f"\n✓ Error ticket created: {error_ticket.key}")
            else:
                print("\n[DRY RUN] Would create error ticket in Jira")
                
        except Exception as ticket_error:
            print(f"\nWarning: Could not create error ticket: {str(ticket_error)}")
        
        print("\n" + "=" * 60)
        print("Bot will retry on next scheduled run")
        print("=" * 60)
        
        # Exit with error code but don't crash
        sys.exit(1)


if __name__ == '__main__':
    main()
