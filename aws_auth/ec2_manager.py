"""EC2 instance management for AWS authentication."""

import sys
import subprocess
import boto3
import logging
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


def _has_attached_win32_console() -> bool:
    """True only for classic Win32 consoles; False for Cursor/VS Code ConPTY terminals."""
    if sys.platform != 'win32':
        return False

    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-10)
    mode = ctypes.c_uint32()
    return bool(kernel32.GetConsoleMode(handle, ctypes.byref(mode)))


def _restore_windows_console() -> None:
    """Restore classic Win32 console mode after SSM (no-op on ConPTY terminals)."""
    if not _has_attached_win32_console():
        return

    import ctypes

    kernel32 = ctypes.windll.kernel32
    ENABLE_PROCESSED_INPUT = 0x0001
    ENABLE_LINE_INPUT = 0x0002
    ENABLE_ECHO_INPUT = 0x0004
    ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200
    ENABLE_PROCESSED_OUTPUT = 0x0001
    ENABLE_WRAP_AT_EOL_OUTPUT = 0x0020
    ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

    stdin_mode = (
        ENABLE_PROCESSED_INPUT
        | ENABLE_LINE_INPUT
        | ENABLE_ECHO_INPUT
        | ENABLE_VIRTUAL_TERMINAL_INPUT
    )
    stdout_mode = (
        ENABLE_PROCESSED_OUTPUT
        | ENABLE_WRAP_AT_EOL_OUTPUT
        | ENABLE_VIRTUAL_TERMINAL_PROCESSING
    )

    for handle_id, mode in ((-10, stdin_mode), (-11, stdout_mode), (-12, stdout_mode)):
        handle = kernel32.GetStdHandle(handle_id)
        if handle not in (0, -1):
            kernel32.SetConsoleMode(handle, mode)


def _run_ssm_on_windows(cmd: List[str]) -> int:
    """Run SSM without corrupting integrated terminals (Cursor/VS Code use ConPTY)."""
    if _has_attached_win32_console():
        try:
            return subprocess.run(cmd).returncode
        finally:
            _restore_windows_console()

    # ConPTY terminals ignore SetConsoleMode; isolate SSM in its own console window.
    print("💡 Opening SSM in a new window (keeps this terminal usable on Windows)")
    print("   Type exit in that window when you are done")
    return subprocess.run(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE).returncode


class EC2Manager:
    """Manages EC2 instance operations and connections."""
    
    def __init__(self, profile_name: Optional[str] = None):
        """Initialize EC2 manager with optional profile."""
        self.profile_name = profile_name
        self.session = None
        self.ec2_client = None
        self._initialize_session()
    
    def _initialize_session(self) -> None:
        """Initialize boto3 session with profile."""
        try:
            if self.profile_name and self.profile_name != 'default':
                self.session = boto3.Session(profile_name=self.profile_name)
            else:
                self.session = boto3.Session()
            
            self.ec2_client = self.session.client('ec2')
            logger.info(f"EC2 client initialized with profile: {self.profile_name or 'default'}")
        except Exception as e:
            logger.error(f"Failed to initialize EC2 client: {e}")
            raise
    
    def list_instances(self, region: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all EC2 instances in the account."""
        try:
            if region:
                ec2_client = self.session.client('ec2', region_name=region)
            else:
                ec2_client = self.ec2_client
            
            response = ec2_client.describe_instances()
            
            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instance_info = self._format_instance_info(instance)
                    instances.append(instance_info)
            
            # Sort by state (running first), then by name
            instances.sort(key=lambda x: (x['state'] != 'running', x['name'] or ''))
            
            return instances
            
        except NoCredentialsError:
            logger.error("No valid AWS credentials found. Please authenticate first.")
            raise
        except ClientError as e:
            if e.response['Error']['Code'] == 'UnauthorizedOperation':
                logger.error("Access denied. Check your permissions for EC2:DescribeInstances")
            else:
                logger.error(f"AWS error listing instances: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing instances: {e}")
            raise
    
    def _format_instance_info(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        """Format instance information for display."""
        # Get instance name from tags
        name = None
        for tag in instance.get('Tags', []):
            if tag['Key'] == 'Name':
                name = tag['Value']
                break
        
        # Get public/private IPs
        public_ip = instance.get('PublicIpAddress')
        private_ip = instance.get('PrivateIpAddress')
        
        # Get security groups
        security_groups = [sg['GroupName'] for sg in instance.get('SecurityGroups', [])]
        
        return {
            'instance_id': instance['InstanceId'],
            'name': name,
            'state': instance['State']['Name'],
            'instance_type': instance['InstanceType'],
            'public_ip': public_ip,
            'private_ip': private_ip,
            'key_name': instance.get('KeyName'),
            'security_groups': security_groups,
            'availability_zone': instance['Placement']['AvailabilityZone'],
            'launch_time': instance['LaunchTime'],
            'platform': instance.get('Platform', 'linux'),
            'vpc_id': instance.get('VpcId'),
            'subnet_id': instance.get('SubnetId')
        }
    
    def generate_ssh_command(self, instance: Dict[str, Any], key_path: Optional[str] = None, 
                           username: str = 'ec2-user') -> str:
        """Generate SSH command for connecting to instance."""
        ip = instance['public_ip'] or instance['private_ip']
        if not ip:
            return "No IP address available"
        
        if instance['platform'] == 'windows':
            return f"# Windows instance - use RDP to {ip}"
        
        key_part = f"-i {key_path} " if key_path else ""
        return f"ssh {key_part}{username}@{ip}"
    
    def connect_via_ssm(self, instance: Dict[str, Any]) -> bool:
        """Connect to instance via AWS Systems Manager Session Manager.
        
        Uses os.execvp to replace the current process with the SSM session,
        giving it full terminal control. This prevents Ctrl+C from being
        intercepted by Python and killing the session prematurely.
        """
        import os
        import shutil
        
        instance_id = instance['instance_id']
        instance_name = instance['name'] or instance_id
        
        # Check if AWS CLI is available
        if not shutil.which('aws'):
            logger.error("AWS CLI not found. Please install AWS CLI first.")
            print("❌ AWS CLI not found. Please install AWS CLI first.")
            print("   Installation: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html")
            return False
        
        # Prepare SSM command
        cmd = ['aws', 'ssm', 'start-session', '--target', instance_id]
        if self.profile_name and self.profile_name != 'default':
            cmd.extend(['--profile', self.profile_name])
        
        print(f"\n🔌 Connecting to {instance_name} via AWS SSM...")
        print("─" * 60)
        print("💡 To exit the session, type: exit or press Ctrl+D")
        print("📝 Session Manager provides secure shell access without SSH keys")
        print("─" * 60)
        print(f"🚀 Starting session... (Instance: {instance_id})")
        print()
        
        # Replace current process with SSM session so it gets full terminal control.
        # On Windows, os.execvp can leave orphan session-manager-plugin processes
        # that keep reading stdin and corrupt the terminal; subprocess.run avoids that.
        try:
            if sys.platform == 'win32':
                return _run_ssm_on_windows(cmd) == 0
            os.execvp('aws', cmd)
        except FileNotFoundError:
            print("❌ AWS CLI not found.")
            return False
        except Exception as e:
            logger.error(f"Failed to exec SSM session: {e}")
            print(f"\n❌ Failed to start SSM session: {e}")
            return False
        
        # os.execvp replaces the process, so this line is never reached
        return True
