# Installing AWS CLI and kubectl on Linux

This guide provides step-by-step instructions to install the AWS Command Line Interface (AWS CLI), `kubectl` (Kubernetes CLI), and `aws-auth` on Linux.

---

## Prerequisites
- Linux (Ubuntu, Debian, CentOS, etc.)
- Terminal access with sudo privileges
- Internet connection

---

## 1. Install AWS CLI

### a. Download the AWS CLI Installer
- Run the following commands in your terminal:

```sh
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

### b. Verify Installation
```sh
aws --version
```
You should see output similar to:
```
aws-cli/2.x.x Python/3.x.x Linux/x86_64
```

---

## 2. Install kubectl

### a. Download the kubectl Binary
- Find the latest stable version from the [Kubernetes releases page](https://kubernetes.io/releases/download/).
- Download and install (replace `<version>` with the latest version, e.g., `v1.30.1`):

```sh
curl -LO "https://dl.k8s.io/release/<version>/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/
```

Example for v1.30.1:
```sh
curl -LO "https://dl.k8s.io/release/v1.30.1/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/
```

### b. Verify Installation
```sh
kubectl version --client
```
You should see output with the client version.

---

## 3. Download and Install aws-auth (Linux Version)

### a. Download the aws-auth Linux Executable
- Visit the official aws-auth Git repository: `<repository-url>`
- Download the Linux version of the `aws-auth` executable from the repository's releases or downloads section (if available).
- Make the file executable and move it to a directory in your PATH:

```sh
chmod +x aws-auth
sudo mv aws-auth /usr/local/bin/
```

### b. Execute aws-auth
- After installing or downloading `aws-auth`, run the executable to complete the setup:

```sh
aws-auth
```

- Follow any on-screen instructions provided by the tool.

---

## 4. Update kubeconfig for EKS Cluster

After installing aws-auth, update your kubeconfig to connect kubectl to your EKS cluster by running:

```sh
aws eks update-kubeconfig --region us-east-1 --name eks
```

This command configures kubectl to use your EKS cluster in the `us-east-1` region with the name `eks`.

---

## 5. Install Nocalhost Plugin in VSCode

To enhance your Kubernetes development experience, you can install the Nocalhost plugin in Visual Studio Code:

1. Open **Visual Studio Code**.
2. Go to the **Extensions** view by clicking the square icon on the sidebar or pressing `Ctrl+Shift+X`.
3. In the search bar, type `Nocalhost`.
4. Find the **Nocalhost** extension by Nocalhost Team and click **Install**.
5. Once installed, you can access Nocalhost features from the VSCode sidebar.

For more information, visit the [Nocalhost VSCode Extension page](https://marketplace.visualstudio.com/items?itemName=nocalhost.nocalhost) and the [Nocalhost Documentation](https://nocalhost.dev/docs/).

---

## 6. RDS Port Forwarding with kubectl

If you need to access an AWS RDS instance (or any database service running inside your Kubernetes cluster) from your local machine, you can use `kubectl port-forward` to forward a port from your local machine to the RDS service inside the cluster.

### Prerequisites
- Ensure you have network access to the Kubernetes cluster and the RDS service is exposed as a Kubernetes Service.

### Example Command
Suppose your RDS service is named `my-rds-service` in the `default` namespace and listens on port `5432` (PostgreSQL default):

```sh
kubectl port-forward svc/my-rds-service 5432:5432 --namespace default
```

- This command forwards your local port 5432 to the service's port 5432.
- You can now connect to the database using `localhost:5432` from your local machine.

> **Note:** Adjust the service name, namespace, and port as needed for your setup.

---

## 7. RDS Port Forwarding via AWS CLI (SSM)

If your RDS instance is in a private VPC, you can use AWS Systems Manager (SSM) to port-forward from your local machine to the RDS instance via an SSM-enabled EC2 instance.

### Prerequisites
- The RDS instance is not publicly accessible.
- An EC2 instance in the same VPC/subnet as the RDS instance.
- The EC2 instance has the SSM Agent installed and running.
- The EC2 instance IAM role allows SSM access.
- Your local AWS CLI is authenticated and has SSM permissions.

### Steps

1. **Find your EC2 instance ID** (the one with SSM access in the same VPC as RDS):

   ```sh
   aws ec2 describe-instances --filters "Name=tag:Name,Values=<your-bastion-name>" --query "Reservations[*].Instances[*].InstanceId" --output text
   ```

2. **Start the port forwarding session** (replace values as needed):

   ```sh
   aws ssm start-session \
     --target i-xxxxxxxxxxxxxxxxx \
     --document-name AWS-StartPortForwardingSessionToRemoteHost \
     --parameters 'host="<rds-endpoint>",portNumber="5432",localPortNumber="5432"'
   ```

   - Replace `i-xxxxxxxxxxxxxxxxx` with your EC2 instance ID.
   - Replace `<rds-endpoint>` with your RDS endpoint (e.g., `mydb.xxxxxxx.us-east-1.rds.amazonaws.com`).
   - Adjust the port numbers for your database (e.g., 3306 for MySQL, 5432 for PostgreSQL).

3. **Connect to your RDS instance locally**:

   - Use `localhost:5432` (or your chosen local port) in your database client.

> **Note:** You need the AWS CLI v2 and Session Manager Plugin installed on your local machine.

**References:**
- [AWS: Connect to a private RDS instance using SSM](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-getting-started.html)
- [AWS CLI: start-session](https://docs.aws.amazon.com/cli/latest/reference/ssm/start-session.html)

---

**You are now ready to use AWS CLI, kubectl, and aws-auth on your Linux machine!**

---

## References
- [AWS CLI Official Docs](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [kubectl Install Docs](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/) 