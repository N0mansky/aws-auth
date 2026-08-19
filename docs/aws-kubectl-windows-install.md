# Installing AWS CLI and kubectl on Windows

This guide provides step-by-step instructions to install the AWS Command Line Interface (AWS CLI) and `kubectl` (Kubernetes CLI) on Windows.

---

## Prerequisites
- Windows 10 or later
- Administrator access
- Internet connection

---

## 1. Install AWS CLI

### a. Download the AWS CLI Installer
- Go to the [AWS CLI MSI installer for Windows](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html#install-windows).
- Direct download link: [AWS CLI v2 MSI](https://awscli.amazonaws.com/AWSCLIV2.msi)

### b. Run the Installer
- Double-click the downloaded `AWSCLIV2.msi` file.
- Follow the on-screen instructions to complete the installation.

### c. Verify Installation
Open **Command Prompt** and run:
```sh
aws --version
```
You should see output similar to:
```
aws-cli/2.x.x Python/3.x.x Windows/10 exe/AMD64
```

---

## 2. Install kubectl

### a. Download the kubectl Binary
- Go to the [Kubernetes releases page](https://kubernetes.io/releases/download/).
- Find the latest stable version. Copy the version (e.g., `v1.30.1`).
- Download using PowerShell (replace `<version>` with the latest version):

```powershell
curl -LO "https://dl.k8s.io/release/<version>/bin/windows/amd64/kubectl.exe"
```

Example for v1.30.1:
```powershell
curl -LO "https://dl.k8s.io/release/v1.30.1/bin/windows/amd64/kubectl.exe"
```

### b. Add kubectl to Your PATH
- Move `kubectl.exe` to a directory already in your PATH, or add its location to the PATH environment variable:
  1. Right-click **This PC** > **Properties** > **Advanced system settings** > **Environment Variables**.
  2. Under **System variables**, select `Path` > **Edit**.
  3. Add the folder path where `kubectl.exe` is located.
  4. Click **OK** to save.

### c. Verify Installation
Open **Command Prompt** or **PowerShell** and run:
```sh
kubectl version --client
```
You should see output with the client version.

---

## 4. Download and Install aws-auth (Windows Version)

After installing AWS CLI and kubectl, you can set up `aws-auth` on Windows by following one of these methods:

### a. Download the aws-auth Windows Executable
- Visit the official aws-auth Git repository: `<repository-url>`
- Download the Windows version of the `aws-auth` executable from the repository's releases or downloads section (if available).
- Place the executable in a directory included in your system PATH for easy access.

### b. Run the install.bat Script
- If your project provides an `install.bat` script:
  1. Locate the `install.bat` file in your project directory.
  2. Right-click the file and select **Run as administrator** (recommended).
  3. Follow any on-screen prompts to complete the installation.

### c. Execute aws-auth.exe
- After installing or downloading `aws-auth`, run the executable to complete the setup:

```sh
aws-auth.exe
```

- Follow any on-screen instructions provided by the tool.

---

## 5. Update kubeconfig for EKS Cluster

After installing aws-auth, update your kubeconfig to connect kubectl to your EKS cluster by running the following command in Command Prompt or PowerShell:

```sh
aws eks update-kubeconfig --region us-east-1 --name eks
```

This command configures kubectl to use your EKS cluster in the `us-east-1` region with the name `eks`.

---

## 6. Install Nocalhost Plugin in VSCode

To enhance your Kubernetes development experience, you can install the Nocalhost plugin in Visual Studio Code:

1. Open **Visual Studio Code**.
2. Go to the **Extensions** view by clicking the square icon on the sidebar or pressing `Ctrl+Shift+X`.
3. In the search bar, type `Nocalhost`.
4. Find the **Nocalhost** extension by Nocalhost Team and click **Install**.
5. Once installed, you can access Nocalhost features from the VSCode sidebar.

For more information, visit the [Nocalhost VSCode Extension page](https://marketplace.visualstudio.com/items?itemName=nocalhost.nocalhost) and the [Nocalhost Documentation](https://nocalhost.dev/docs/). 

// ... existing code ...

---

## 6.1 (Alternative) Access Cluster Services with Telepresence

[Telepresence](https://github.com/telepresenceio/telepresence) is an open-source tool for local development against a remote Kubernetes or OpenShift cluster. It can be used as an alternative to Nocalhost for connecting your local environment to cluster services, enabling debugging, testing, and development as if the services were running locally.

### Prerequisites
- Access to your Kubernetes cluster
- `kubectl` configured and working
- Telepresence installed on your local machine

### Install Telepresence
- For Windows, install via Chocolatey:
  ```powershell
  choco install telepresence
  ```
- Or download the installer from the [Telepresence GitHub Releases](https://github.com/telepresenceio/telepresence/releases).
- See the [official install guide](https://www.telepresence.io/docs/latest/install/) for more options.


---

**References:**
- [Telepresence GitHub](https://github.com/telepresenceio/telepresence)
- [Telepresence Documentation](https://www.telepresence.io/docs/latest/)


---

## 7. RDS Port Forwarding via AWS CLI (SSM)

If your RDS instance is in a private VPC, you can use AWS Systems Manager (SSM) to port-forward from your local Windows machine to the RDS instance via an SSM-enabled EC2 instance.

### Prerequisites
- The RDS instance is not publicly accessible.
- An EC2 instance in the same VPC/subnet as the RDS instance.
- The EC2 instance has the SSM Agent installed and running.
- The EC2 instance IAM role allows SSM access.
- Your local AWS CLI is authenticated and has SSM permissions.

### Steps

1. **Find your EC2 instance ID** (the one with SSM access in the same VPC as RDS):

   Open Command Prompt or PowerShell and run:
   ```sh
   aws ec2 describe-instances --filters "Name=tag:Name,Values=<your-bastion-name>" --query "Reservations[*].Instances[*].InstanceId" --output text
   ```

2. **Start the port forwarding session** (replace values as needed):

   ```sh
   aws ssm start-session ^
     --target i-xxxxxxxxxxxxxxxxx ^
     --document-name AWS-StartPortForwardingSessionToRemoteHost ^
     --parameters 'host="<rds-endpoint>",portNumber="5432",localPortNumber="5432"'
   ```

   - Replace `i-xxxxxxxxxxxxxxxxx` with your EC2 instance ID.
   - Replace `<rds-endpoint>` with your RDS endpoint (e.g., `mydb.xxxxxxx.us-east-1.rds.amazonaws.com`).
   - Adjust the port numbers for your database (e.g., 3306 for MySQL, 5432 for PostgreSQL).

3. **Connect to your RDS instance locally**:

   - Use `localhost:5432` (or your chosen local port) in your database client.

   **Example for PostgreSQL:**
   ```sh
   psql -h localhost -p 5432 -U <db-username> -d <db-name>
   ```

   **Example for MySQL:**
   ```sh
   mysql -h 127.0.0.1 -P 3306 -u <db-username> -p <db-name>
   ```

> **Note:** You need the AWS CLI v2 and Session Manager Plugin installed on your Windows machine.

**References:**
- [AWS: Connect to a private RDS instance using SSM](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-getting-started.html)
- [AWS CLI: start-session](https://docs.aws.amazon.com/cli/latest/reference/ssm/start-session.html)

---

**You are now ready to use AWS CLI, kubectl, and aws-auth on your Windows machine!**

---

## References
- [AWS CLI Official Docs](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [kubectl Install Docs](https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/)

--- 