"""User interface and interaction handling."""

import os
import sys
import getpass
import logging
from typing import Tuple, List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class UserInterface:
    """Handles user interactions and input prompts."""
    
    @staticmethod
    def prompt_choice(prompt: str, max_choice: int) -> int:
        """Prompt user for a choice between 1 and max_choice, return 0-indexed value."""
        while True:
            try:
                user_input = input(f"{prompt} (default: 1): ").strip()
                choice = int(user_input) if user_input else 1
                if 1 <= choice <= max_choice:
                    return choice - 1
                logger.info(f"Please enter a number between 1 and {max_choice}")
            except ValueError:
                logger.info("Invalid input. Please enter a number.")
            except KeyboardInterrupt:
                logger.info("\nOperation cancelled by user.")
                sys.exit(0)
    
    @staticmethod
    def get_credentials() -> Tuple[str, str]:
        """Get username and password from user or environment."""
        username = os.environ.get("AWS_AUTH_USERNAME")
        if not username:
            username = input("Enter your SSO Email: ").strip()
        
        password = os.environ.get("AWS_AUTH_PASSWORD")
        if not password:
            password = getpass.getpass("Enter your SSO password: ")
        
        return username, password
    
    @staticmethod
    def generate_profile_name(account_name: str, role_name: str) -> str:
        """Generate a clean profile name from account and role names.
        
        Examples:
            "Production-App" + "AdministratorAccess" -> "production-app-admin"
            "Staging-Web" + "DeveloperAccess" -> "staging-web-developer"
        """
        import re
        
        # Clean account name: lowercase, replace spaces/special chars with hyphens
        account_clean = re.sub(r'[^a-zA-Z0-9]+', '-', account_name.lower()).strip('-')
        
        # Clean role name: extract meaningful part (remove common prefixes)
        role_clean = role_name.lower()
        # Remove common prefixes
        for prefix in ['aws-']:
            if role_clean.startswith(prefix):
                role_clean = role_clean[len(prefix):]
        
        # Extract key part of role (e.g., "administratoraccess" -> "admin", "developeraccess" -> "developer")
        if 'administrator' in role_clean or 'admin' in role_clean:
            role_part = 'admin'
        elif 'developer' in role_clean or 'dev' in role_clean:
            role_part = 'developer'
        elif 'readonly' in role_clean or 'read-only' in role_clean:
            role_part = 'readonly'
        else:
            # Use first meaningful word or shorten
            words = re.split(r'[^a-zA-Z0-9]+', role_clean)
            role_part = words[0] if words else 'user'
        
        profile_name = f"{account_clean}-{role_part}"
        return profile_name
    
    @staticmethod
    def get_user_preferences(
        existing_profiles: Optional[List[str]] = None,
        account_name: Optional[str] = None,
        role_name: Optional[str] = None,
        region: Optional[str] = None
    ) -> Tuple[List[str], str, bool]:
        """Get user preferences for profile names.
        
        Args:
            existing_profiles: List of existing profile names
            account_name: Account name for auto-generating profile name
            role_name: Role name for auto-generating profile name
            region: Region already selected (will be used, not prompted)
        """
        # Auto-generate profile name from account and role
        auto_profile_name = None
        profile_exists = False
        if account_name and role_name:
            auto_profile_name = UserInterface.generate_profile_name(account_name, role_name)
            # Check if auto-generated name already exists
            if existing_profiles and auto_profile_name in existing_profiles:
                profile_exists = True
        
        if auto_profile_name:
            if profile_exists:
                # Auto-update existing profile without prompting
                print(f"✅ Profile '{auto_profile_name}' exists. Updating with new credentials...")
                profile_names = [auto_profile_name]
            else:
                print(f"Auto-generated profile name: {auto_profile_name}")
                profile_names_input = input(
                    f"Enter AWS profile name(s) to save credentials (comma-separated, default '{auto_profile_name}'): "
                ).strip()
                profile_names = [name.strip() for name in profile_names_input.split(",")] if profile_names_input else [auto_profile_name]
        else:
            profile_names_input = input(
                "Enter AWS profile name(s) to save credentials (comma-separated, default 'default'): "
            ).strip()
            profile_names = [name.strip() for name in profile_names_input.split(",")] if profile_names_input else ["default"]
        
        # Use provided region or default to us-east-1
        selected_region = region or "us-east-1"
        
        # Always set as default (no prompt)
        set_as_default = True
        
        return profile_names, selected_region, set_as_default
    
    @staticmethod
    def select_account_and_role(accounts: List[Dict[str, Any]], all_account_roles: Dict[str, List[Dict[str, Any]]]) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
        """Interactive selection of AWS account, role, and region from combined list."""
        # Common AWS regions
        common_regions = [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1', 'eu-north-1',
            'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1', 'ap-northeast-2', 'ap-south-1',
            'ca-central-1', 'sa-east-1'
        ]
        
        from .config import Config
        config = Config()
        recent_selections = config.get_recent_selections()
        aliases = config.get_aliases()
        preferred_accounts = config.get_preferred_accounts()
        
        # Create a flat list of all account-role combinations
        all_combinations = []
        for account in accounts:
            account_id = account['accountId']
            account_name = account['accountName']
            if account_id in all_account_roles:
                roles = all_account_roles[account_id]
                for role in roles:
                    role_name = role['roleName']
                    all_combinations.append({
                        'account': account,
                        'role': role,
                        'account_id': account_id,
                        'account_name': account_name,
                        'role_name': role_name,
                    })
        
        if not all_combinations:
            raise RuntimeError("No account-role combinations available")
        
        def combo_sort_key(combo: Dict[str, Any]) -> Tuple[int, int, str, str]:
            """Sort order:
            1. Recent selections (MRU order)
            2. Preferred accounts from config
            3. Role tier: AdministratorAccess first (0), then DeveloperAccess (1), then other (2)
            4. Account name & role name alphabetically
            """
            acc_id = str(combo['account_id'])
            acc_name = combo['account_name']
            r_name = combo['role_name']
            
            # Check MRU recents
            for r_idx, rec in enumerate(recent_selections):
                if str(rec.get('accountId')) == acc_id and rec.get('roleName') == r_name:
                    return (0, r_idx, acc_name.lower(), r_name.lower())
            
            # Check preferred accounts
            for p_idx, pref in enumerate(preferred_accounts):
                if pref.lower() in acc_name.lower() or pref == acc_id:
                    return (1, p_idx, acc_name.lower(), r_name.lower())
            
            # Role tier
            role_tier = 2
            if 'admin' in r_name.lower():
                role_tier = 0
            elif 'dev' in r_name.lower():
                role_tier = 1
                
            return (2, role_tier, acc_name.lower(), r_name.lower())

        sorted_combinations = sorted(all_combinations, key=combo_sort_key)
        
        active_combinations = sorted_combinations
        items_per_page = 10
        current_page = 1
        active_filter = ""
        
        def pad_cell(text: str, target_width: int) -> str:
            """Pad string taking into account 2-column emoji/wide characters for perfect terminal alignment."""
            vis_len = sum(2 if (c in ('⭐', '☸', '🖥', '❌', '✅', '🚀', '🔍', '⚙', '👤', '📦', '🔑') or ord(c) > 0x2000) else 1 for c in text)
            if vis_len > target_width:
                # Truncate safely
                curr_w = 0
                truncated = []
                for c in text:
                    w = 2 if (c in ('⭐', '☸', '🖥', '❌', '✅', '🚀', '🔍', '⚙', '👤', '📦', '🔑') or ord(c) > 0x2000) else 1
                    if curr_w + w > target_width:
                        break
                    truncated.append(c)
                    curr_w += w
                text = "".join(truncated)
                vis_len = curr_w
            return text + (" " * max(0, target_width - vis_len))
        
        col_widths = {
            'idx': 3,
            'acc': 28,
            'id': 15,
            'role': 28,
            'reg': 11
        }
        
        header = f"| {pad_cell('#', col_widths['idx'])} | {pad_cell('Account', col_widths['acc'])} | {pad_cell('Account ID', col_widths['id'])} | {pad_cell('Role', col_widths['role'])} | {pad_cell('Region', col_widths['reg'])} |"
        separator = "+" + "-" * (col_widths['idx'] + 2) + "+" + "-" * (col_widths['acc'] + 2) + "+" + "-" * (col_widths['id'] + 2) + "+" + "-" * (col_widths['role'] + 2) + "+" + "-" * (col_widths['reg'] + 2) + "+"
        
        while True:
            total_items = len(active_combinations)
            total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)
            if current_page > total_pages:
                current_page = total_pages
                
            start_idx = (current_page - 1) * items_per_page
            end_idx = min(start_idx + items_per_page, total_items)
            page_items = active_combinations[start_idx:end_idx]
            
            filter_banner = f" [Filter: '{active_filter}']" if active_filter else ""
            print(f"\nAvailable account-role combinations (Page {current_page}/{total_pages}, Showing {start_idx + 1}-{end_idx} of {total_items}){filter_banner}:")
            print(separator)
            print(header)
            print(separator)
            
            for local_idx, combo in enumerate(page_items):
                global_idx = start_idx + local_idx + 1
                acc_name = combo['account_name']
                acc_id = combo['account_id']
                r_name = combo['role_name']
                
                # Check for alias in config
                alias = aliases.get(str(acc_id))
                display_acc = f"{acc_name} ({alias})" if alias else acc_name
                
                # Check if recent
                is_recent = any(
                    str(r.get('accountId')) == str(acc_id) and r.get('roleName') == r_name 
                    for r in recent_selections[:3]
                )
                prefix = "⭐ " if is_recent else ""
                display_acc = prefix + display_acc
                display_id = f"({acc_id})"
                region_display = "us-east-1"
                
                row = (
                    f"| {pad_cell(str(global_idx), col_widths['idx'])} "
                    f"| {pad_cell(display_acc, col_widths['acc'])} "
                    f"| {pad_cell(display_id, col_widths['id'])} "
                    f"| {pad_cell(r_name, col_widths['role'])} "
                    f"| {pad_cell(region_display, col_widths['reg'])} |"
                )
                print(row)
                print(separator)
            
            # Navigation / search prompt
            nav_hints = []
            if total_pages > 1:
                if current_page > 1:
                    nav_hints.append("'p'=prev")
                if current_page < total_pages:
                    nav_hints.append("'n'=next")
            if active_filter:
                nav_hints.append("'r'=reset filter")
            else:
                nav_hints.append("type keyword to filter")
                
            hints_str = f" ({', '.join(nav_hints)})" if nav_hints else ""
            default_hint = f" (default: {start_idx + 1})"
            
            prompt_text = f"Select number {start_idx + 1}-{end_idx}{default_hint}{hints_str}: "
            try:
                user_input = input(prompt_text).strip()
            except (KeyboardInterrupt, EOFError):
                print("\nSelection cancelled.")
                raise KeyboardInterrupt
            
            # Default Enter press selects option 1 of current view
            if not user_input:
                user_input = str(start_idx + 1)
            
            # Handle commands
            cmd = user_input.lower()
            if cmd == 'n' and current_page < total_pages:
                current_page += 1
                continue
            elif cmd == 'p' and current_page > 1:
                current_page -= 1
                continue
            elif cmd in ('r', 'reset'):
                active_filter = ""
                active_combinations = sorted_combinations
                current_page = 1
                continue
            elif user_input.isdigit():
                choice = int(user_input)
                if start_idx + 1 <= choice <= end_idx:
                    selected_combo = active_combinations[choice - 1]
                    # Record this selection to MRU in config
                    config.record_recent_selection(
                        selected_combo['account_id'],
                        selected_combo['account_name'],
                        selected_combo['role_name']
                    )
                    return selected_combo['account'], selected_combo['role'], 'us-east-1'
                else:
                    print(f"⚠️  Please enter a number between {start_idx + 1} and {end_idx}.")
            else:
                # Text filter search
                keyword = user_input.lower()
                filtered = [
                    c for c in sorted_combinations
                    if keyword in c['account_name'].lower()
                    or keyword in c['role_name'].lower()
                    or keyword in str(c['account_id'])
                    or (aliases.get(str(c['account_id'])) and keyword in aliases[str(c['account_id'])].lower())
                ]
                if filtered:
                    active_filter = user_input
                    active_combinations = filtered
                    current_page = 1
                else:
                    print(f"⚠️  No account/role matches keyword '{user_input}'. Type 'r' to reset.")
    
    @staticmethod
    def display_profiles(profiles: Dict[str, Dict[str, str]]) -> None:
        """Display available AWS profiles with their information."""
        if not profiles:
            print("No AWS profiles found.")
            return
        
        print("\n=== Available AWS Profiles ===")
        for idx, (profile_name, profile_info) in enumerate(sorted(profiles.items()), 1):
            print(f"{idx}. Profile: {profile_name}")
            if profile_info:
                print(f"   Region: {profile_info.get('region', 'N/A')}")
                print(f"   Access Key: {profile_info.get('aws_access_key_id', 'N/A')}")
                if 'aws_session_token' in profile_info:
                    print(f"   Session Token: {profile_info['aws_session_token']}")
            print()
    
    @staticmethod
    def display_profiles_table(profiles: Dict[str, Dict[str, str]], default_profile: Optional[str] = None) -> None:
        """Display available AWS profiles in a table format for quick selection.
        
        Args:
            profiles: Dictionary of profile names to profile info
            default_profile: Name of the profile currently set as default (will be marked with *)
        """
        if not profiles:
            print("No AWS profiles found.")
            return
        
        # Filter out 'default' profile and sort
        filtered_profiles = [(name, info) for name, info in profiles.items() if name != 'default']
        sorted_profiles = sorted(filtered_profiles)
        
        print("\nAvailable AWS Profiles:")
        # AWS CLI style table with borders (expanded for default indicator)
        header = f"| {'#':<3} | {'Profile Name':<22} | {'Region':<15} | {'Status':<15} |"
        separator = "+" + "-" * 5 + "+" + "-" * 24 + "+" + "-" * 17 + "+" + "-" * 17 + "+"
        print(separator)
        print(header)
        print(separator)
        
        for idx, (profile_name, profile_info) in enumerate(sorted_profiles, 1):
            region = profile_info.get('region', 'N/A') if profile_info else 'N/A'
            # Check if credentials exist and are valid
            has_access_key = profile_info and profile_info.get('aws_access_key_id')
            has_token = profile_info and 'aws_session_token' in profile_info
            if has_access_key and has_token:
                status = "✅ Active"
            elif has_access_key:
                status = "⚠️  Expired"
            else:
                status = "❌ Invalid"
            
            # Add * indicator if this is the default profile
            display_name = profile_name
            if default_profile and profile_name == default_profile:
                display_name = f"{profile_name} *"  # Add * to show it's default
            
            row = f"| {str(idx):<3} | {display_name:<22} | {region:<15} | {status:<15} |"
            print(row)
        
        print(separator)
        
        # Show note about default indicator if applicable
        if default_profile:
            print(f"* = Currently set as default profile")
    
    @staticmethod
    def select_profile_to_use(profiles: List[str], default_profile: Optional[str] = None) -> Optional[str]:
        """Let user select which profile to use/switch to.
        
        Args:
            profiles: List of profile names (should not include 'default')
            default_profile: Name of the currently default profile (for indicator)
        """
        if not profiles:
            print("No profiles available.")
            return None
        
        print("\n=== Switch to Profile ===")
        sorted_profiles = sorted(profiles)
        for idx, profile_name in enumerate(sorted_profiles, 1):
            # Add indicator for default profile
            display_name = profile_name
            if default_profile and profile_name == default_profile:
                display_name = f"{profile_name} * (default)"
            print(f"{idx}. {display_name}")
        
        try:
            choice = UserInterface.prompt_choice("Select profile to use", len(sorted_profiles))
            return sorted_profiles[choice]
        except (KeyboardInterrupt, EOFError):
            return None
    
    @staticmethod
    def select_profile_for_default(profiles: List[str]) -> Optional[str]:
        """Let user select which profile to set as default."""
        if not profiles:
            print("No profiles available.")
            return None
        
        print("\n=== Select Profile to Set as Default ===")
        sorted_profiles = sorted(profiles)
        for idx, profile_name in enumerate(sorted_profiles, 1):
            print(f"{idx}. {profile_name}")
        
        try:
            choice = UserInterface.prompt_choice("Select profile to set as default", len(sorted_profiles))
            return sorted_profiles[choice]
        except (KeyboardInterrupt, EOFError):
            return None
    
    @staticmethod
    def select_profile_for_deletion(profiles: List[str]) -> Optional[str]:
        """Let user select which profile to delete."""
        # Filter out 'default' profile as it shouldn't be deleted
        deletable_profiles = [p for p in profiles if p != 'default']
        
        if not deletable_profiles:
            print("No deletable profiles available (default profile cannot be deleted).")
            return None
        
        print("\n=== Select Profile to Delete ===")
        sorted_profiles = sorted(deletable_profiles)
        for idx, profile_name in enumerate(sorted_profiles, 1):
            print(f"{idx}. {profile_name}")
        
        try:
            choice = UserInterface.prompt_choice("Select profile to delete", len(sorted_profiles))
            selected_profile = sorted_profiles[choice]
            
            # Confirmation
            confirm = input(f"Are you sure you want to delete profile '{selected_profile}'? (y/N): ").strip().lower()
            if confirm in ['y', 'yes']:
                return selected_profile
            else:
                print("Deletion cancelled.")
                return None
        except (KeyboardInterrupt, EOFError):
            return None
    
    @staticmethod
    def show_profile_menu() -> str:
        """Show profile management menu and return user choice."""
        print("\n=== AWS Profile Management ===")
        print("1. Add new profile (authenticate with SSO)")
        print("2. List existing profiles")
        print("3. Set profile as default")
        print("4. Delete profile")
        print("5. Exit")
        
        while True:
            try:
                choice = input("Select an option (1-5): ").strip()
                if choice in ['1', '2', '3', '4', '5']:
                    return choice
                print("Please enter a number between 1 and 5.")
            except (KeyboardInterrupt, EOFError):
                print("\nExiting...")
                return '5'
    
    @staticmethod
    def display_ec2_instances(instances: List[Dict[str, Any]], region: str) -> None:
        """Display running EC2 instances in a bordered table format.
        
        Only running instances are shown. Non-running instances are filtered out
        and a summary count is displayed if any were excluded.
        """
        if not instances:
            print(f"\nNo EC2 instances found in region {region}.")
            return
        
        # Filter to running instances only
        running = [i for i in instances if i['state'] == 'running']
        non_running_count = len(instances) - len(running)
        
        if not running:
            print(f"\nNo running EC2 instances found in region {region}.")
            if non_running_count:
                print(f"({non_running_count} non-running instance(s) hidden)")
            return
        
        # Replace instances list in-place so select_ec2_instance gets the filtered list
        instances.clear()
        instances.extend(running)
        
        print(f"\n=== Running EC2 Instances in {region} ({len(running)} instances) ===")
        
        # Table with borders
        separator = "+" + "-" * 5 + "+" + "-" * 27 + "+" + "-" * 22 + "+" + "-" * 17 + "+" + "-" * 17 + "+" + "-" * 17 + "+"
        header =    f"| {'#':<3} | {'Name':<25} | {'Instance ID':<20} | {'Type':<15} | {'Public IP':<15} | {'Private IP':<15} |"
        
        print(separator)
        print(header)
        print(separator)
        
        for idx, instance in enumerate(running, 1):
            name = instance['name'] or '(no name)'
            public_ip = instance['public_ip'] or '-'
            private_ip = instance['private_ip'] or '-'
            
            row = f"| {str(idx):<3} | {name[:25]:<25} | {instance['instance_id']:<20} | {instance['instance_type']:<15} | {public_ip:<15} | {private_ip:<15} |"
            print(row)
            print(separator)
        
        if non_running_count:
            print(f"({non_running_count} non-running instance(s) hidden)")
    
    @staticmethod
    def select_ec2_instance(instances: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Let user select an EC2 instance."""
        if not instances:
            return None
        
        try:
            choice = UserInterface.prompt_choice("Select an instance to get connection commands", len(instances))
            return instances[choice]
        except (KeyboardInterrupt, EOFError):
            return None
    
    @staticmethod
    def display_ssh_command(instance: Dict[str, Any], ssh_cmd: str) -> None:
        """Display SSH connection information."""
        print(f"\n=== SSH Connection for {instance['name'] or instance['instance_id']} ===")
        print("─" * 80)
        
        print("🔑 SSH Command:")
        print(f"   {ssh_cmd}")
        
        if instance['key_name']:
            print(f"\n💡 For SSH with key file:")
            username = 'Administrator' if instance['platform'] == 'windows' else 'ec2-user'
            ip = instance['public_ip'] or instance['private_ip']
            print(f"   ssh -i /path/to/{instance['key_name']}.pem {username}@{ip}")
            print(f"\n📝 Make sure you have the key file '{instance['key_name']}.pem' and proper permissions:")
            print(f"   chmod 400 /path/to/{instance['key_name']}.pem")
        
        print("─" * 80)
    
    @staticmethod
    def display_eks_clusters(clusters: List[Dict[str, Any]], region: str) -> None:
        """Display EKS clusters in a table format."""
        if not clusters:
            print(f"\nNo EKS clusters found in region {region}.")
            return
        
        print(f"\n=== EKS Clusters in {region} ===")
        print("─" * 100)
        print(f"{'#':<3} {'Name':<25} {'Status':<12} {'Version':<10} {'Platform Version':<20} {'Created':<12}")
        print("─" * 100)
        
        for idx, cluster in enumerate(clusters, 1):
            name = cluster['name']
            status = cluster['status']
            
            # Add status indicators
            if status == 'ACTIVE':
                status_display = f"🟢 {status}"
            elif status == 'CREATING':
                status_display = f"🟡 {status}"
            elif status in ['DELETING', 'FAILED']:
                status_display = f"🔴 {status}"
            else:
                status_display = f"⚪ {status}"
            
            version = cluster['version']
            platform_version = cluster['platform_version'][:19] if cluster['platform_version'] else 'N/A'
            
            # Format creation date
            created = 'N/A'
            if cluster['created_at']:
                try:
                    created = cluster['created_at'].strftime('%Y-%m-%d')
                except:
                    created = 'N/A'
            
            print(f"{idx:<3} {name[:24]:<25} {status_display:<15} {version:<10} {platform_version:<20} {created:<12}")
        
        print("─" * 100)
    
    @staticmethod
    def select_eks_cluster(clusters: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Let user select an EKS cluster."""
        if not clusters:
            return None
        
        try:
            choice = UserInterface.prompt_choice("Select a cluster to connect", len(clusters))
            return clusters[choice]
        except (KeyboardInterrupt, EOFError):
            return None
    
    @staticmethod
    def display_cluster_details(cluster: Dict[str, Any]) -> None:
        """Display detailed information about an EKS cluster."""
        print(f"\n=== Cluster Details: {cluster['name']} ===")
        print("─" * 60)
        
        print(f"Name: {cluster['name']}")
        print(f"Status: {cluster['status']}")
        print(f"Version: {cluster['version']}")
        print(f"Platform Version: {cluster['platform_version']}")
        
        if cluster['endpoint'] != 'unknown':
            print(f"Endpoint: {cluster['endpoint']}")
        
        if cluster['created_at']:
            try:
                created_str = cluster['created_at'].strftime('%Y-%m-%d %H:%M:%S UTC')
                print(f"Created: {created_str}")
            except (AttributeError, ValueError, TypeError):
                pass
        
        # Show VPC info if available
        vpc_config = cluster.get('vpc_config', {})
        if vpc_config:
            if 'subnetIds' in vpc_config:
                print(f"Subnets: {len(vpc_config['subnetIds'])} configured")
            if 'securityGroupIds' in vpc_config:
                print(f"Security Groups: {len(vpc_config['securityGroupIds'])} configured")
        
        print("─" * 60)
