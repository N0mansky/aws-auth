"""
Command-line interface for AWS SSO Authentication tool.
"""

import os
import sys
import json
import argparse
import logging
from aws_auth import AuthManager, Config, CredentialsManager, __version__
from aws_auth.profile_manager import ProfileManager
from aws_auth.ec2_manager import EC2Manager
from aws_auth.eks_manager import EKSManager
from aws_auth.user_interface import UserInterface
from aws_auth.caller_identity import get_caller_identity, display_caller_identity

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description='AWS SSO Authentication and Profile Management',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                        # Interactive SSO authentication
  %(prog)s --manage               # Profile management menu
  %(prog)s --list-profiles        # List all profiles
  %(prog)s --list-profiles --json # List profiles as JSON
  %(prog)s --set-default [PROFILE]# Set profile as default (interactive if omitted)
  %(prog)s --export-env PROFILE   # Output bash exports for credentials
  %(prog)s --identity             # Check STS caller identity
  %(prog)s --mcp                  # Run Model Context Protocol (MCP) server
  %(prog)s --delete [PROFILE]     # Delete a profile (interactive if omitted)
  %(prog)s --list-ec2             # Authenticate & choose role, then list EC2 instances
  %(prog)s --list-eks             # Authenticate & choose role, then list EKS clusters
  %(prog)s --list-ec2 --region us-west-2  # Choose role, then list EC2 in specific region
  %(prog)s --list-eks --no-auth   # Use existing credentials, skip authentication
  %(prog)s --list-ec2 qa --no-auth --region us-west-2  # Use 'qa' profile, skip auth
        """
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}',
        help="Show program's version number and exit"
    )
    
    parser.add_argument(
        '--credential-process',
        metavar='PROFILE',
        nargs='?',
        const='default',
        help='Output AWS credentials matching standard AWS credential_process JSON specification'
    )
    
    parser.add_argument(
        '--configure',
        action='store_true',
        help='Interactively configure default AWS SSO Start URL and Region'
    )
    
    parser.add_argument(
        '--refresh-cache',
        action='store_true',
        help='Bypass cached account and role metadata and query AWS SSO directly'
    )
    
    parser.add_argument(
        '--mcp',
        action='store_true',
        help='Run as Model Context Protocol (MCP) server for AI agents via stdio'
    )
    
    parser.add_argument(
        '--export-env',
        metavar='PROFILE',
        nargs='?',
        const='default',
        help='Export AWS credentials as environment variables (default: default profile)'
    )
    
    parser.add_argument(
        '--identity',
        '--get-identity',
        action='store_true',
        help='Get AWS STS caller identity for active/default profile'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results in JSON format (machine-readable)'
    )
    
    parser.add_argument(
        '--non-interactive',
        action='store_true',
        help='Disable interactive prompts and menus (for scripts and AI agents)'
    )
    
    parser.add_argument(
        '--manage', 
        action='store_true',
        help='Open interactive profile management menu'
    )
    
    parser.add_argument(
        '--list-profiles',
        action='store_true',
        help='List all existing AWS profiles'
    )
    
    parser.add_argument(
        '--set-default',
        metavar='PROFILE',
        nargs='?',
        const='',
        help='Set the specified profile as default (interactive selection if omitted)'
    )
    
    parser.add_argument(
        '--delete',
        metavar='PROFILE',
        nargs='?',
        const='',
        help='Delete the specified profile (interactive selection if omitted)'
    )
    
    parser.add_argument(
        '--list-ec2',
        metavar='PROFILE',
        nargs='?',
        const='default',
        help='List EC2 instances for the specified profile (default: default)'
    )
    
    parser.add_argument(
        '--list-eks',
        metavar='PROFILE',
        nargs='?',
        const='default',
        help='List EKS clusters for the specified profile (default: default)'
    )
    
    parser.add_argument(
        '--region',
        metavar='REGION',
        default='us-east-1',
        help='AWS region for EC2/EKS operations (default: us-east-1)'
    )
    
    parser.add_argument(
        '--no-auth',
        action='store_true',
        help='Skip authentication and use existing credentials from profiles'
    )
    
    parser.add_argument(
        '--switch-profile',
        '-s',
        action='store_true',
        help='Quickly switch to an existing profile without re-authenticating'
    )
    
    parser.add_argument(
        '--use-profile',
        '-p',
        metavar='PROFILE',
        help='Activate and use a specific profile'
    )

    parser.add_argument(
        '--current-profile',
        action='store_true',
        help='Print the active AWS profile name from ~/.aws-auth/current_profile'
    )

    parser.add_argument(
        '--write-default',
        action='store_true',
        help='Also write/copy credentials to [default] section in credentials file (opt-in)'
    )
    
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose debug logging'
    )

    parser.add_argument(
        '--quiet',
        '-q',
        action='store_true',
        help='Suppress informational messages, only output warnings and errors'
    )
    
    return parser


def offer_resource_exploration(profile_name: str, region: str) -> None:
    """Interactive prompt to explore EKS or EC2 resources after authentication."""
    try:
        print("\n🔧 AWS Resources:")
        print("1. ☸️  List EKS clusters")
        print("2. 🖥️  List EC2 instances")
        print("3. ❌ Skip (or 'q' to quit)")
        
        choice = input("What would you like to explore? (1-3, default: 1, 'q' to quit): ").strip().lower()
        if choice in ('q', 'quit', 'exit', '0', '3'):
            return
        if choice in ('1', ''):
            eks_mgr = EKSManager(profile_name)
            print(f"\n🔍 Loading EKS clusters from {region}...")
            clusters = eks_mgr.list_clusters(region)
            ui = UserInterface()
            ui.display_eks_clusters(clusters, region)
            if clusters:
                selected = ui.select_eks_cluster(clusters)
                if selected and selected.get('status') == 'ACTIVE':
                    eks_mgr.connect_to_cluster(selected, region)
        elif choice == '2':
            ec2_mgr = EC2Manager(profile_name)
            print(f"\n🔍 Loading EC2 instances from {region}...")
            instances = ec2_mgr.list_instances(region)
            ui = UserInterface()
            ui.display_ec2_instances(instances, region)
            if instances:
                selected = ui.select_ec2_instance(instances)
                if selected and selected['state'] == 'running':
                    ssh_cmd = ec2_mgr.generate_ssh_command(selected)
                    ui.display_ssh_command(selected, ssh_cmd)
                    print(f"\n🚀 Initiating SSM connection to {selected['name'] or selected['instance_id']}...")
                    ec2_mgr.connect_via_ssm(selected)
    except (KeyboardInterrupt, EOFError):
        print("\nSkipping resource exploration.")


def main() -> None:
    """Main entry point with comprehensive error handling."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Configure logging level based on verbose/quiet flags and environment
    env_level = os.environ.get("AWS_AUTH_LOG_LEVEL", "").upper()
    default_level = getattr(logging, env_level, logging.INFO)

    if args.verbose:
        target_level = logging.DEBUG
        fmt = '[%(asctime)s] %(levelname)s: %(message)s'
    elif args.quiet:
        target_level = logging.WARNING
        fmt = '[%(asctime)s] %(message)s'
    else:
        target_level = default_level
        fmt = '[%(asctime)s] %(message)s'

    logging.getLogger().setLevel(target_level)
    logging.basicConfig(level=target_level, format=fmt, datefmt='%Y-%m-%d %H:%M:%S', force=True)

    if target_level > logging.DEBUG:
        # Suppress internal and external verbose diagnostics in standard mode
        logging.getLogger('aws_auth.credentials_manager').setLevel(logging.WARNING)
        logging.getLogger('botocore').setLevel(logging.WARNING)
        logging.getLogger('boto3').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Sanitize process environment: purge non-existent AWS_PROFILE to protect boto3
    CredentialsManager().sanitize_environment()
    
    # If running MCP mode, launch MCP server immediately
    if args.mcp:
        from aws_auth.mcp_server import main as mcp_main
        mcp_main()
        return

    # Handle interactive configuration
    if args.configure:
        config = Config()
        try:
            print("\n⚙️  AWS SSO Configuration")
            print("========================")
            url = input(f"AWS SSO Start URL [{config.SSO_START_URL or 'None'}]: ").strip() or config.SSO_START_URL
            region = input(f"AWS SSO Region [{config.SSO_REGION}]: ").strip() or config.SSO_REGION
            if url:
                config.save_user_config(url, region)
                print(f"✅ Configuration saved to {config.CONFIG_FILE}")
            else:
                print("❌ Start URL cannot be empty.")
                sys.exit(1)
        except (KeyboardInterrupt, EOFError):
            print("\nConfiguration cancelled.")
        return

    # Fast handler for current-profile check
    if args.current_profile:
        cm = ProfileManager().credentials_manager
        current = cm.get_current_profile()
        if current:
            if args.json:
                print(json.dumps({"success": True, "profile": current}, indent=2))
            else:
                print(current)
            return
        else:
            if args.json:
                print(json.dumps({"success": False, "error": "No active profile set"}, indent=2))
            else:
                sys.stderr.write("No active profile set. Run 'aws-auth' to authenticate or select a profile.\n")
            sys.exit(1)

    # Handle standard AWS credential_process
    if args.credential_process is not None:
        profile_manager = ProfileManager()
        target_profile = (args.credential_process if args.credential_process != 'default' else None) or profile_manager.credentials_manager.get_active_profile() or "default"
        creds = profile_manager.credentials_manager.get_unmasked_profile_credentials(target_profile)
        if not creds or not creds.get("aws_access_key_id"):
            sys.stderr.write(f"Error: No credentials found for profile '{target_profile}'.\n")
            sys.exit(1)
        
        output = {
            "Version": 1,
            "AccessKeyId": creds.get("aws_access_key_id"),
            "SecretAccessKey": creds.get("aws_secret_access_key"),
            "SessionToken": creds.get("aws_session_token", "")
        }
        print(json.dumps(output))
        return

    # Handle export-env
    if args.export_env is not None:
        profile_manager = ProfileManager()
        target_profile = (args.export_env if args.export_env != 'default' else None) or profile_manager.credentials_manager.get_active_profile() or "default"
        creds = profile_manager.credentials_manager.get_unmasked_profile_credentials(target_profile)
        if not creds:
            if args.json:
                print(json.dumps({"success": False, "error": f"Profile '{target_profile}' not found"}, indent=2))
            else:
                sys.stderr.write(f"Error: Profile '{target_profile}' not found.\n")
            sys.exit(1)
        
        region = creds.get("region", args.region or "us-east-1")
        if args.json:
            print(json.dumps({
                "success": True,
                "profile": target_profile,
                "AWS_ACCESS_KEY_ID": creds.get("aws_access_key_id", ""),
                "AWS_SECRET_ACCESS_KEY": creds.get("aws_secret_access_key", ""),
                "AWS_SESSION_TOKEN": creds.get("aws_session_token", ""),
                "AWS_DEFAULT_REGION": region,
                "AWS_REGION": region,
                "AWS_PROFILE": target_profile
            }, indent=2))
        else:
            print(f"export AWS_ACCESS_KEY_ID={creds.get('aws_access_key_id', '')}")
            print(f"export AWS_SECRET_ACCESS_KEY={creds.get('aws_secret_access_key', '')}")
            print(f"export AWS_SESSION_TOKEN={creds.get('aws_session_token', '')}")
            print(f"export AWS_DEFAULT_REGION={region}")
            print(f"export AWS_REGION={region}")
            print(f"export AWS_PROFILE={target_profile}")
        return

    # Handle identity check
    if args.identity:
        profile_manager = ProfileManager()
        target_profile = args.use_profile or profile_manager.credentials_manager.get_active_profile() or "default"
        identity = get_caller_identity(profile_name=target_profile if target_profile != "default" else None)
        if args.json:
            print(json.dumps({
                "success": bool(identity),
                "profile": target_profile,
                "identity": identity
            }, indent=2))
        else:
            display_caller_identity(profile_name=target_profile if target_profile != "default" else None)
        return

    try:
        profile_manager = ProfileManager()
        
        # Handle profile management operations
        if args.manage:
            if args.non_interactive:
                print("Error: --manage is an interactive menu and cannot be used with --non-interactive.")
                sys.exit(1)
            profile_manager.run_interactive_menu()
            return
        
        if args.switch_profile:
            if args.non_interactive:
                print("Error: --switch-profile requires interactive selection. Use --set-default <profile> instead.")
                sys.exit(1)
            set_default = (args.set_default is not None) or getattr(args, 'write_default', False)
            profile_manager.switch_profile(set_as_default=set_default)
            return
        
        if args.use_profile:
            existing_profiles = list(profile_manager.credentials_manager.get_existing_profiles())
            if args.use_profile not in existing_profiles:
                if args.json:
                    print(json.dumps({"success": False, "error": f"Profile '{args.use_profile}' not found"}, indent=2))
                else:
                    print(f"Error: Profile '{args.use_profile}' not found.")
                    print(f"Available profiles: {', '.join(existing_profiles) if existing_profiles else 'None'}")
                sys.exit(1)
            
            # Persist to current_profile
            profile_manager.credentials_manager.set_current_profile(args.use_profile)
            if getattr(args, 'write_default', False):
                profile_manager.credentials_manager.set_default_profile(args.use_profile)
            
            if args.json:
                print(json.dumps({"success": True, "profile": args.use_profile}, indent=2))
            else:
                print(f"\n✅ Active profile set to: {args.use_profile}")
                print(f"   Exported via shell wrapper: export AWS_PROFILE={args.use_profile}")
                print(f"   Or use: aws --profile {args.use_profile} <command>")
            return
        
        if args.list_profiles:
            if args.json:
                existing_profiles = list(profile_manager.credentials_manager.get_existing_profiles())
                default_p = profile_manager.credentials_manager.get_default_profile_name()
                active_p = profile_manager.credentials_manager.get_active_profile()
                profiles_info = {
                    p: profile_manager.credentials_manager.get_profile_info(p)
                    for p in existing_profiles
                }
                print(json.dumps({
                    "success": True,
                    "default_profile": default_p or "default",
                    "active_profile": active_p or default_p or "default",
                    "profiles": profiles_info
                }, indent=2))
            else:
                profile_manager.list_profiles()
            return
        
        if args.set_default is not None:
            target_profile = args.set_default
            if not target_profile:
                if args.non_interactive:
                    if args.json:
                        print(json.dumps({"success": False, "error": "--set-default requires a profile name when run with --non-interactive."}, indent=2))
                    else:
                        print("Error: --set-default requires a profile name when run with --non-interactive.")
                    sys.exit(1)
                if args.json:
                    print(json.dumps({"success": False, "error": "--set-default requires a profile name when run with --json."}, indent=2))
                    sys.exit(1)
                
                existing_profiles = list(profile_manager.credentials_manager.get_existing_profiles())
                if not existing_profiles:
                    print("No AWS profiles found. Please add a profile first.")
                    sys.exit(1)
                selected_profile = profile_manager.ui.select_profile_for_default(existing_profiles)
                if not selected_profile:
                    return
                target_profile = selected_profile
            
            success = profile_manager.credentials_manager.set_default_profile(target_profile)
            if success:
                profile_manager.credentials_manager.set_current_profile(target_profile)
            if args.json:
                print(json.dumps({
                    "success": success,
                    "default_profile": target_profile if success else None,
                    "active_profile": target_profile if success else None,
                    "error": None if success else f"Failed to set '{target_profile}' as default profile."
                }, indent=2))
            else:
                if success:
                    print(f"Successfully set '{target_profile}' as default profile.")
                else:
                    print(f"Failed to set '{target_profile}' as default profile.")
            if not success:
                sys.exit(1)
            return
        
        if args.delete is not None:
            target_profile = args.delete
            if not target_profile:
                if args.non_interactive:
                    if args.json:
                        print(json.dumps({"success": False, "error": "--delete requires a profile name when run with --non-interactive."}, indent=2))
                    else:
                        print("Error: --delete requires a profile name when run with --non-interactive.")
                    sys.exit(1)
                if args.json:
                    print(json.dumps({"success": False, "error": "--delete requires a profile name when run with --json."}, indent=2))
                    sys.exit(1)
                
                existing_profiles = list(profile_manager.credentials_manager.get_existing_profiles())
                if not existing_profiles:
                    print("No AWS profiles found.")
                    sys.exit(1)
                selected_profile = profile_manager.ui.select_profile_for_deletion(existing_profiles)
                if not selected_profile:
                    return
                target_profile = selected_profile
            
            if target_profile == 'default':
                if args.json:
                    print(json.dumps({"success": False, "error": "Cannot delete the default profile."}, indent=2))
                else:
                    print("Error: Cannot delete the default profile.")
                sys.exit(1)
            
            success = profile_manager.credentials_manager.delete_profile(target_profile)
            if args.json:
                print(json.dumps({
                    "success": success,
                    "deleted_profile": target_profile if success else None,
                    "error": None if success else f"Failed to delete profile '{target_profile}'."
                }, indent=2))
            else:
                if success:
                    print(f"Successfully deleted profile '{target_profile}'.")
                else:
                    print(f"Failed to delete profile '{target_profile}'.")
            if not success:
                sys.exit(1)
            return
        
        if args.list_ec2:
            try:
                ec2_profile = (args.list_ec2 if args.list_ec2 != 'default' else None) or profile_manager.credentials_manager.get_active_profile() or "default"
                # Check if we should authenticate first (default behavior)
                if not args.no_auth:
                    if not args.json:
                        print("🔐 Authenticating and selecting role...")
                    auth_manager = AuthManager()
                    auth_result = auth_manager.assume_role_via_sso(set_as_default=bool(args.write_default))
                    ec2_profile = auth_result.profile_names[0] if auth_result.profile_names else ec2_profile
                    if not args.json:
                        print(f"\n🔄 Now listing EC2 instances with your selected credentials...")
                elif not profile_manager.credentials_manager.get_profile_info(ec2_profile):
                    if not args.json:
                        print("🔐 No valid credentials found. Authenticating first...")
                    auth_manager = AuthManager()
                    auth_result = auth_manager.assume_role_via_sso(set_as_default=bool(args.write_default))
                    ec2_profile = auth_result.profile_names[0] if auth_result.profile_names else ec2_profile
                    if not args.json:
                        print(f"\n🔄 Now listing EC2 instances with your selected credentials...")
                
                ec2_manager = EC2Manager(ec2_profile)
                if not args.json:
                    print(f"🔍 Loading EC2 instances from {args.region} using profile '{ec2_profile}'...")
                instances = ec2_manager.list_instances(args.region)
                
                if args.json:
                    print(json.dumps({
                        "success": True,
                        "profile": ec2_profile,
                        "region": args.region,
                        "count": len(instances),
                        "instances": instances
                    }, indent=2, default=str))
                    return

                ui = UserInterface()
                ui.display_ec2_instances(instances, args.region)
                
                if instances and not args.non_interactive:
                    # Go directly to instance selection (default: 1)
                    selected_instance = ui.select_ec2_instance(instances)
                    if selected_instance:
                        instance_name = selected_instance['name'] or selected_instance['instance_id']
                        
                        if selected_instance['state'] != 'running':
                            print(f"\n⚠️  Instance '{instance_name}' is not running. Start it first.")
                        else:
                            # Always show SSH command for reference
                            ssh_cmd = ec2_manager.generate_ssh_command(selected_instance)
                            ui.display_ssh_command(selected_instance, ssh_cmd)
                            
                            # Connect via SSM directly (replaces current process)
                            print(f"\n🚀 Initiating SSM connection to {instance_name}...")
                            ec2_manager.connect_via_ssm(selected_instance)
            except Exception as e:
                if args.json:
                    print(json.dumps({"success": False, "error": str(e)}, indent=2))
                else:
                    logger.error(f"Failed to list EC2 instances: {e}")
                sys.exit(1)
            return
        
        if args.list_eks:
            try:
                eks_profile = (args.list_eks if args.list_eks != 'default' else None) or profile_manager.credentials_manager.get_active_profile() or "default"
                # Check if we should authenticate first (default behavior)
                if not args.no_auth:
                    if not args.json:
                        print("🔐 Authenticating and selecting role...")
                    auth_manager = AuthManager()
                    auth_result = auth_manager.assume_role_via_sso(set_as_default=bool(args.write_default))
                    eks_profile = auth_result.profile_names[0] if auth_result.profile_names else eks_profile
                    if not args.json:
                        print(f"\n🔄 Now listing EKS clusters with your selected credentials...")
                elif not profile_manager.credentials_manager.get_profile_info(eks_profile):
                    if not args.json:
                        print("🔐 No valid credentials found. Authenticating first...")
                    auth_manager = AuthManager()
                    auth_result = auth_manager.assume_role_via_sso(set_as_default=bool(args.write_default))
                    eks_profile = auth_result.profile_names[0] if auth_result.profile_names else eks_profile
                    if not args.json:
                        print(f"\n🔄 Now listing EKS clusters with your selected credentials...")
                
                eks_manager = EKSManager(eks_profile)
                if not args.json:
                    print(f"🔍 Loading EKS clusters from {args.region} using profile '{eks_profile}'...")
                clusters = eks_manager.list_clusters(args.region)
                
                if args.json:
                    print(json.dumps({
                        "success": True,
                        "profile": eks_profile,
                        "region": args.region,
                        "count": len(clusters),
                        "clusters": clusters
                    }, indent=2, default=str))
                    return

                ui = UserInterface()
                ui.display_eks_clusters(clusters, args.region)
                
                if clusters and not args.non_interactive:
                    connect_cluster = input("\n☸️  Connect to a cluster? (Y/n): ").strip().lower()
                    if connect_cluster in ['', 'y', 'yes']:
                        selected_cluster = ui.select_eks_cluster(clusters)
                        if selected_cluster:
                            if selected_cluster['status'] != 'ACTIVE':
                                print(f"⚠️  Cluster '{selected_cluster['name']}' is not in ACTIVE state")
                                print("Cannot connect to inactive cluster.")
                            else:
                                ui.display_cluster_details(selected_cluster)
                                confirm = input(f"\n🚀 Connect to cluster '{selected_cluster['name']}'? (Y/n): ").strip().lower()
                                if confirm in ['', 'y', 'yes']:
                                    eks_manager.connect_to_cluster(selected_cluster, args.region)
            except Exception as e:
                if args.json:
                    print(json.dumps({"success": False, "error": str(e)}, indent=2))
                else:
                    logger.error(f"Failed to list EKS clusters: {e}")
                sys.exit(1)
            return
        
        # Default behavior: SSO authentication
        config = Config()
        if not config.SSO_START_URL:
            if not args.non_interactive and not args.json:
                if not config.prompt_for_config_if_missing():
                    sys.exit(1)
            else:
                sys.stderr.write("Error: SSO_START_URL is required. Set AWS_SSO_START_URL or run 'aws-auth --configure'.\n")
                sys.exit(1)
        auth_manager = AuthManager(config=config)
        auth_result = auth_manager.assume_role_via_sso(
            force_refresh_accounts=args.refresh_cache,
            set_as_default=bool(args.write_default)
        )
        if not args.non_interactive and not args.json:
            primary_profile = auth_result.profile_names[0] if auth_result.profile_names else 'default'
            offer_resource_exploration(primary_profile, auth_result.region)
        
    except KeyboardInterrupt:
        print("\nExiting on user interrupt.")
        sys.exit(0)
    except RuntimeError as e:
        logger.error(f"Runtime error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()
