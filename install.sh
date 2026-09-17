#!/bin/bash

set -e

echo "🚀 aws-auth Setup and Build Script"
echo "=================================="
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH."
    echo "Please install Python 3.8+ and try again."
    exit 1
fi

echo "✅ Python 3 found. Proceeding with setup..."
echo ""

echo "📦 Step 0: Checking required command-line tools..."

# Install basic prerequisites if missing
if ! command -v curl &> /dev/null || ! command -v unzip &> /dev/null; then
    echo "Installing required basic tools (curl, unzip)..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y curl unzip
    elif command -v yum &> /dev/null; then
        sudo yum install -y curl unzip
    else
        echo "⚠️  Please install 'curl' and 'unzip' manually."
    fi
fi

# Check and install AWS CLI
if ! command -v aws &> /dev/null; then
    echo "Installing AWS CLI..."
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    sudo ./aws/install
    rm -rf aws awscliv2.zip
    echo "✅ AWS CLI installed."
else
    echo "✅ AWS CLI already installed."
fi

# Check and install kubectl
if ! command -v kubectl &> /dev/null; then
    echo "Installing kubectl..."
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    rm kubectl
    echo "✅ kubectl installed."
else
    echo "✅ kubectl already installed."
fi

# Check and install AWS SSM Session Manager Plugin
if ! command -v session-manager-plugin &> /dev/null; then
    echo "Installing AWS SSM Session Manager Plugin..."
    if command -v dpkg &> /dev/null; then
        curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb" -o "session-manager-plugin.deb"
        sudo dpkg -i session-manager-plugin.deb
        rm session-manager-plugin.deb
        echo "✅ AWS SSM Session Manager Plugin installed."
    elif command -v rpm &> /dev/null; then
        curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/linux_64bit/session-manager-plugin.rpm" -o "session-manager-plugin.rpm"
        sudo rpm -i session-manager-plugin.rpm
        rm session-manager-plugin.rpm
        echo "✅ AWS SSM Session Manager Plugin installed."
    else
        echo "⚠️  Could not automatically install session-manager-plugin (neither dpkg nor rpm found)."
        echo "Please install it manually: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html"
    fi
else
    echo "✅ AWS SSM Session Manager Plugin already installed."
fi

# Ensure session-manager-plugin is on PATH for this shell session
export PATH="/usr/local/sessionmanagerplugin/bin:/usr/local/bin:${PATH}"
hash -r 2>/dev/null || true
if command -v session-manager-plugin &> /dev/null; then
    echo "✅ AWS SSM Session Manager Plugin verified on PATH."
else
    echo "⚠️  session-manager-plugin not found on PATH."
    echo "   Add to your shell profile: export PATH=\"/usr/local/sessionmanagerplugin/bin:\$PATH\""
fi
echo ""

# Prefer pyenv python3 if available and functional, otherwise system python3
PYTHON_CMD="python3"
if command -v pyenv &> /dev/null; then
    PYENV_PYTHON="$(pyenv which python3 2>/dev/null || true)"
    if [ -n "$PYENV_PYTHON" ] && [ -x "$PYENV_PYTHON" ]; then
        PYTHON_CMD="$PYENV_PYTHON"
    fi
fi

# Step 1: Create virtual environment first
echo "📦 Step 1: Creating virtual environment..."
if [ -d "venv" ] && [ -f "venv/bin/python" ] && [ -f "venv/bin/pip" ]; then
    echo "Virtual environment already exists and is healthy. Skipping creation."
else
    echo "Creating new virtual environment using $PYTHON_CMD..."
    rm -rf venv
    if $PYTHON_CMD -m venv venv 2>/dev/null; then
        echo "✅ Virtual environment created successfully with pip."
    else
        echo "Creating virtual environment without pip (will install pip later)..."
        $PYTHON_CMD -m venv venv --without-pip
        if [ $? -ne 0 ]; then
            echo "Error: Failed to create virtual environment."
            exit 1
        fi
        echo "✅ Virtual environment created successfully without pip."
    fi
fi

# Step 2: Activate virtual environment
echo "📦 Step 2: Activating virtual environment..."
source venv/bin/activate
echo "✅ Virtual environment activated."

# Step 3: Install pip if not available
if ! python -m pip --version &> /dev/null; then
    echo "📦 Step 3: Installing pip in virtual environment..."
    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    python get-pip.py --force-reinstall
    rm get-pip.py
    echo "✅ Pip installed in virtual environment."
else
    echo "📦 Step 3: Pip already available in virtual environment."
fi

# Step 4: Install Python dependencies
echo "📦 Step 4: Installing Python dependencies..."
pip install -r requirements.txt
pip install -r requirements-dev.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install Python dependencies."
    exit 1
fi
echo "✅ Python dependencies installed."

# Step 6: Build the application
echo "🔨 Step 6: Building application..."

# Check if PyInstaller is available
if ! command -v pyinstaller &> /dev/null; then
    echo "Error: PyInstaller not found in virtual environment."
    echo "Please check that requirements.txt includes pyinstaller."
    exit 1
fi

# Generate spec file with all hidden imports
echo "Generating PyInstaller spec file..."
pyi-makespec --onefile \
    --hidden-import=aws_auth \
    --hidden-import=aws_auth.cli \
    --hidden-import=aws_auth.mcp_server \
    --hidden-import=aws_auth.auth_manager \
    --hidden-import=aws_auth.caller_identity \
    --hidden-import=aws_auth.config \
    --hidden-import=aws_auth.credentials_manager \
    --hidden-import=aws_auth.ec2_manager \
    --hidden-import=aws_auth.eks_manager \
    --hidden-import=aws_auth.local_browser_manager \
    --hidden-import=aws_auth.profile_manager \
    --hidden-import=aws_auth.sso_client \
    --hidden-import=aws_auth.token_manager \
    --hidden-import=aws_auth.user_interface \
    aws-auth.py

# Build with PyInstaller
echo "Running PyInstaller..."
venv/bin/pyinstaller -y --clean aws-auth.spec

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 SUCCESS! Build completed successfully!"
    echo "Executable created in: dist/aws-auth"
    echo ""
    
    echo "📦 Step 7: Installing executable..."
    if [ -w /usr/local/bin/aws-auth ]; then
        cp dist/aws-auth /usr/local/bin/aws-auth
        chmod +x /usr/local/bin/aws-auth
        echo "✅ Installed to /usr/local/bin/aws-auth"
    elif [ -w /usr/local/bin ]; then
        cp dist/aws-auth /usr/local/bin/aws-auth
        chmod +x /usr/local/bin/aws-auth
        echo "✅ Installed to /usr/local/bin/aws-auth"
    else
        echo "Requesting sudo privileges to install to /usr/local/bin..."
        sudo cp dist/aws-auth /usr/local/bin/aws-auth
        sudo chmod +x /usr/local/bin/aws-auth
        echo "✅ Installed to /usr/local/bin/aws-auth"
    fi
    echo ""

    echo "🔧 Step 8: Configuring shell integration wrapper in ~/.zshrc and ~/.bashrc..."
    WRAPPER_BLOCK='# >>> aws-auth shell wrapper >>>
# Auto-export active profile on shell startup if present
if [ -f ~/.aws-auth/current_profile ]; then
    export AWS_PROFILE=$(< ~/.aws-auth/current_profile)
fi

# Scopes active profile to current terminal session via AWS_PROFILE
aws-auth() {
    command /usr/local/bin/aws-auth "$@"
    local ret=$?
    if [ $ret -eq 0 ] && [ -f ~/.aws-auth/current_profile ]; then
        export AWS_PROFILE=$(< ~/.aws-auth/current_profile)
    fi
    return $ret
}
# <<< aws-auth shell wrapper <<<'

    for rc_file in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.profile"; do
        if [ -f "$rc_file" ]; then
            if grep -q "# >>> aws-auth shell wrapper >>>" "$rc_file"; then
                # Replace existing wrapper block
                python3 -c "
import sys, re
path = sys.argv[1]
with open(path, 'r') as f:
    content = f.read()
pattern = r'# >>> aws-auth shell wrapper >>>.*?# <<< aws-auth shell wrapper <<<'
replacement = '''$WRAPPER_BLOCK'''
new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
with open(path, 'w') as f:
    f.write(new_content)
" "$rc_file"
                echo "✅ Updated aws-auth wrapper in $rc_file"
            else
                echo "" >> "$rc_file"
                echo "$WRAPPER_BLOCK" >> "$rc_file"
                echo "✅ Added aws-auth wrapper function to $rc_file"
            fi
        fi
    done
    echo ""

    echo "You can now run the application from anywhere with:"
    echo "  aws-auth"
    echo ""
    echo "💡 Note: Reload your shell or run 'source ~/.zshrc' / 'source ~/.bashrc' to activate the wrapper function."
    echo ""
else
    echo ""
    echo "❌ Build failed!"
    exit 1
fi 