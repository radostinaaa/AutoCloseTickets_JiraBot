"""
Debug SLA Fields Script
Shows all fields for a specific ticket to help find SLA information
"""

import json
from jira import JIRA

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

def main():
    # Load config
    config = load_config()
    
    # Connect to Jira
    print("Connecting to Jira...")
    options = {'server': config['jira_url'], 'rest_api_version': '3'}
    jira = JIRA(options=options, basic_auth=(config['username'], config['api_token']))
    print("✓ Connected successfully\n")
    
    # Get a ticket key from user
    ticket_key = input("Enter ticket key (e.g., STS-123): ").strip()
    
    print(f"\nFetching all fields for {ticket_key}...\n")
    
    # Get ticket with all fields
    ticket = jira.issue(ticket_key, fields='*all', expand='names')
    
    print("="*80)
    print(f"TICKET: {ticket.key} - {ticket.fields.summary}")
    print("="*80)
    
    # Show all custom fields
    print("\n\nALL CUSTOM FIELDS:")
    print("-"*80)
    
    for field_name in dir(ticket.fields):
        if field_name.startswith('customfield_'):
            field_value = getattr(ticket.fields, field_name, None)
            if field_value:
                print(f"\n{field_name}:")
                print(f"  Type: {type(field_value)}")
                
                # Convert PropertyHolder to dict if needed
                if hasattr(field_value, '__dict__'):
                    try:
                        field_dict = field_value.__dict__
                        print(f"  Value (dict): {field_dict}")
                        field_value = field_dict
                    except:
                        print(f"  Value: {field_value}")
                else:
                    print(f"  Value: {field_value}")
                
                # If it's a dict, show its structure
                if isinstance(field_value, dict):
                    print("  Structure:")
                    for key, value in field_value.items():
                        print(f"    - {key}: {type(value).__name__}")
                        if key in ['ongoingCycle', 'completedCycles']:
                            print(f"      → SLA FIELD DETECTED!")
                            print(f"      → Content: {value}")
    
    # Also check for SLA-like patterns
    print("\n\n" + "="*80)
    print("POTENTIAL SLA FIELDS:")
    print("="*80)
    
    found_sla = False
    for field_name in dir(ticket.fields):
        if field_name.startswith('customfield_'):
            field_value = getattr(ticket.fields, field_name, None)
            
            # Convert PropertyHolder to dict if needed
            if hasattr(field_value, '__dict__'):
                try:
                    field_value = field_value.__dict__
                except:
                    pass
            
            if field_value and isinstance(field_value, dict):
                # Check if this looks like an SLA field
                str_value = str(field_value)
                if 'ongoingCycle' in str_value or 'completedCycles' in str_value or 'breach' in str_value.lower():
                    found_sla = True
                    print(f"\n{field_name}:")
                    print(f"  {field_value}")
                    
                    # Try to parse SLA status
                    if 'ongoingCycle' in field_value:
                        ongoing = field_value.get('ongoingCycle', {})
                        
                        # Convert PropertyHolder to dict if needed
                        if hasattr(ongoing, '__dict__'):
                            try:
                                ongoing = ongoing.__dict__
                            except:
                                pass
                        
                        if ongoing:
                            print(f"\n  Ongoing Cycle:")
                            print(f"    Raw: {ongoing}")
                            if isinstance(ongoing, dict):
                                print(f"    - Breached: {ongoing.get('breached', 'N/A')}")
                                
                                goal = ongoing.get('goalDuration', {})
                                if hasattr(goal, '__dict__'):
                                    goal = goal.__dict__
                                print(f"    - Goal Duration: {goal.get('friendly', 'N/A') if isinstance(goal, dict) else goal}")
                                
                                elapsed = ongoing.get('elapsedTime', {})
                                if hasattr(elapsed, '__dict__'):
                                    elapsed = elapsed.__dict__
                                print(f"    - Elapsed Time: {elapsed.get('friendly', 'N/A') if isinstance(elapsed, dict) else elapsed}")
                                
                                remaining = ongoing.get('remainingTime', {})
                                if hasattr(remaining, '__dict__'):
                                    remaining = remaining.__dict__
                                print(f"    - Remaining Time: {remaining.get('friendly', 'N/A') if isinstance(remaining, dict) else remaining}")
                    
                    if 'completedCycles' in field_value:
                        completed = field_value.get('completedCycles', [])
                        if completed:
                            print(f"\n  Completed Cycles: {len(completed)}")
                            for i, cycle in enumerate(completed):
                                # Convert PropertyHolder to dict if needed
                                if hasattr(cycle, '__dict__'):
                                    try:
                                        cycle = cycle.__dict__
                                    except:
                                        pass
                                
                                print(f"    Cycle {i+1}:")
                                print(f"      Raw: {cycle}")
                                if isinstance(cycle, dict):
                                    print(f"      - Breached: {cycle.get('breached', 'N/A')}")
                                    
                                    goal = cycle.get('goalDuration', {})
                                    if hasattr(goal, '__dict__'):
                                        goal = goal.__dict__
                                    print(f"      - Goal Duration: {goal.get('friendly', 'N/A') if isinstance(goal, dict) else goal}")
    
    if not found_sla:
        print("\n⚠ No SLA fields found!")
        print("This might mean:")
        print("  1. The ticket doesn't have SLA configured")
        print("  2. Your Jira uses a different SLA field structure")
        print("  3. You need additional permissions to see SLA fields")

if __name__ == "__main__":
    main()
