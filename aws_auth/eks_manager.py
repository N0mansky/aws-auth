"""EKS cluster management for AWS authentication."""

import boto3
import logging
import subprocess
import shutil
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class EKSManager:
    """Manages EKS cluster operations and connections."""
    
    def __init__(self, profile_name: Optional[str] = None):
        """Initialize EKS manager with optional profile."""
        self.profile_name = profile_name
        self.session = None
        self.eks_client = None
        self._initialize_session()
    
    def _initialize_session(self) -> None:
        """Initialize boto3 session with profile."""
        try:
            if self.profile_name and self.profile_name != 'default':
                self.session = boto3.Session(profile_name=self.profile_name)
            else:
                self.session = boto3.Session()
            
            self.eks_client = self.session.client('eks')
            logger.info(f"EKS client initialized with profile: {self.profile_name or 'default'}")
        except Exception as e:
            logger.error(f"Failed to initialize EKS client: {e}")
            raise
    
    def list_clusters(self, region: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all EKS clusters in the account."""
        try:
            if region:
                eks_client = self.session.client('eks', region_name=region)
            else:
                eks_client = self.eks_client
            
            # Get cluster names
            response = eks_client.list_clusters()
            cluster_names = response.get('clusters', [])
            
            if not cluster_names:
                return []
            
            # Get detailed information for each cluster
            clusters = []
            for cluster_name in cluster_names:
                try:
                    cluster_detail = eks_client.describe_cluster(name=cluster_name)
                    cluster_info = self._format_cluster_info(cluster_detail['cluster'])
                    clusters.append(cluster_info)
                except Exception as e:
                    logger.warning(f"Failed to get details for cluster {cluster_name}: {e}")
                    # Add basic info even if details fail
                    clusters.append({
                        'name': cluster_name,
                        'status': 'unknown',
                        'version': 'unknown',
                        'endpoint': 'unknown',
                        'platform_version': 'unknown',
                        'node_groups': [],
                        'fargate_profiles': [],
                        'created_at': None,
                        'arn': 'unknown'
                    })
            
            # Sort by status (active first), then by name
            clusters.sort(key=lambda x: (x['status'] != 'ACTIVE', x['name']))
            
            return clusters
            
        except NoCredentialsError:
            logger.error("No valid AWS credentials found. Please authenticate first.")
            raise
        except ClientError as e:
            if e.response['Error']['Code'] == 'UnauthorizedOperation':
                logger.error("Access denied. Check your permissions for EKS:ListClusters")
            else:
                logger.error(f"AWS error listing clusters: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing clusters: {e}")
            raise
    
    def _format_cluster_info(self, cluster: Dict[str, Any]) -> Dict[str, Any]:
        """Format cluster information for display."""
        return {
            'name': cluster['name'],
            'status': cluster['status'],
            'version': cluster['version'],
            'platform_version': cluster['platformVersion'],
            'endpoint': cluster['endpoint'],
            'arn': cluster['arn'],
            'created_at': cluster['createdAt'],
            'vpc_config': cluster.get('resourcesVpcConfig', {}),
            'node_groups': [],  # Will be populated separately if needed
            'fargate_profiles': [],  # Will be populated separately if needed
            'logging': cluster.get('logging', {}),
            'identity': cluster.get('identity', {}),
            'tags': cluster.get('tags', {})
        }
    
    def get_cluster_node_groups(self, cluster_name: str, region: Optional[str] = None) -> List[str]:
        """Get node groups for a cluster."""
        try:
            if region:
                eks_client = self.session.client('eks', region_name=region)
            else:
                eks_client = self.eks_client
            
            response = eks_client.list_nodegroups(clusterName=cluster_name)
            return response.get('nodegroups', [])
        except Exception as e:
            logger.warning(f"Failed to get node groups for {cluster_name}: {e}")
            return []
    
    def get_cluster_fargate_profiles(self, cluster_name: str, region: Optional[str] = None) -> List[str]:
        """Get Fargate profiles for a cluster."""
        try:
            if region:
                eks_client = self.session.client('eks', region_name=region)
            else:
                eks_client = self.eks_client
            
            response = eks_client.list_fargate_profiles(clusterName=cluster_name)
            return response.get('fargateProfileNames', [])
        except Exception as e:
            logger.warning(f"Failed to get Fargate profiles for {cluster_name}: {e}")
            return []
    
    def generate_kubeconfig_command(self, cluster_name: str, region: str) -> str:
        """Generate kubectl config command for connecting to cluster."""
        profile_part = f"--profile {self.profile_name} " if self.profile_name and self.profile_name != 'default' else ""
        return f"aws {profile_part}eks update-kubeconfig --region {region} --name {cluster_name}"
    
    def update_kubeconfig(self, cluster_name: str, region: str, alias: Optional[str] = None) -> bool:
        """Update kubeconfig to connect to EKS cluster."""
        if not shutil.which('aws'):
            logger.error("AWS CLI not found. Please install AWS CLI first.")
            print("❌ AWS CLI not found. Please install AWS CLI first.")
            return False
        
        try:
            # Prepare command
            cmd = ['aws', 'eks', 'update-kubeconfig', '--region', region, '--name', cluster_name]
            
            if self.profile_name and self.profile_name != 'default':
                cmd.extend(['--profile', self.profile_name])
            
            if alias:
                cmd.extend(['--alias', alias])
            
            print(f"\n🔄 Updating kubeconfig for cluster '{cluster_name}'...")
            print(f"Command: {' '.join(cmd)}")
            
            # Execute command
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                print(f"✅ Successfully updated kubeconfig for cluster '{cluster_name}'")
                if alias:
                    print(f"📝 Cluster context alias: {alias}")
                    print(f"📝 Using AWS profile: {self.profile_name or 'default'}")
                else:
                    account_id = self._get_account_id()
                    cluster_arn = f"arn:aws:eks:{region}:{account_id}:cluster/{cluster_name}"
                    print(f"📝 Cluster context: {cluster_arn}")
                return True
            else:
                logger.error(f"Failed to update kubeconfig: {result.stderr}")
                print(f"❌ Failed to update kubeconfig: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating kubeconfig: {e}")
            print(f"❌ Error updating kubeconfig: {e}")
            return False
    
    def connect_to_cluster(self, cluster: Dict[str, Any], region: str) -> bool:
        """Connect to EKS cluster and optionally run kubectl commands."""
        cluster_name = cluster['name']
        cluster_arn = cluster['arn']
        
        # Check prerequisites
        if not shutil.which('kubectl'):
            print("❌ kubectl not found. Please install kubectl first.")
            print("   Installation: https://kubernetes.io/docs/tasks/tools/")
            return False
        
        # Create a unique context alias that includes profile name to avoid conflicts
        # Format: {profile}-{cluster-name} or just {cluster-name} if using default profile
        if self.profile_name and self.profile_name != 'default':
            context_alias = f"{self.profile_name}-{cluster_name}"
        else:
            # For default profile, use cluster name with a prefix to distinguish
            context_alias = f"default-{cluster_name}"
        
        print(f"\n🚀 Connecting to EKS cluster '{cluster_name}'...")
        print(f"📝 Using profile: {self.profile_name or 'default'}")
        print(f"📝 Creating context alias: {context_alias}")
        
        # Update kubeconfig with unique alias that includes profile name
        # This ensures each cluster has its own isolated context tied to its profile
        if not self.update_kubeconfig(cluster_name, region, context_alias):
            return False
        
        try:
            # Test connection using the unique context alias
            print(f"\n🔍 Testing connection to cluster...")
            test_cmd = ['kubectl', 'cluster-info', '--context', context_alias]
            result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✅ Successfully connected to cluster!")
                print("\n📊 Cluster Info:")
                print(result.stdout)
                print(f"\n🔧 Usage with this cluster:")
                print(f"   kubectl --context {context_alias} <command>")
                print(f"\n💡 This context is isolated to profile '{self.profile_name or 'default'}'")
                print(f"   You can use multiple clusters simultaneously with different profiles!")
                return True
            else:
                print(f"❌ Failed to connect to cluster: {result.stderr}")
                print("💡 Common issues:")
                print("   - No permissions to access the cluster")
                print("   - Cluster is not in ACTIVE state")
                print("   - Network connectivity issues")
                return False
                
        except subprocess.TimeoutExpired:
            print("⏰ Connection test timed out. Cluster might be unreachable.")
            return False
        except Exception as e:
            logger.error(f"Error testing cluster connection: {e}")
            print(f"❌ Error testing connection: {e}")
            return False
    
    def _get_account_id(self) -> str:
        """Get current AWS account ID."""
        try:
            sts_client = self.session.client('sts')
            response = sts_client.get_caller_identity()
            return response['Account']
        except Exception:
            return "unknown"
    
    def get_regions(self) -> List[str]:
        """Get list of available AWS regions for EKS."""
        # EKS is not available in all regions, so provide a curated list
        eks_regions = [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'ca-central-1',
            'eu-central-1', 'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-north-1',
            'ap-northeast-1', 'ap-northeast-2', 'ap-southeast-1', 'ap-southeast-2', 'ap-south-1',
            'sa-east-1'
        ]
        return eks_regions
