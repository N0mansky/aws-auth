"""Local browser manager - opens URLs in system browser instead of Playwright.

This is similar to AWS CLI's approach: it opens the browser and lets the user
complete authentication using their browser's cookies and sessions.
Works in WSL2 by opening the Windows browser.
"""

import os
import sys
import subprocess
import logging
import platform
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def is_valid_url(url: str) -> bool:
    """Validate that the URL has a safe http/https scheme and a network location."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except Exception:
        return False


def is_wsl() -> bool:
    """Check if running in WSL (Windows Subsystem for Linux)."""
    try:
        # Check for WSL-specific files
        if os.path.exists('/proc/version'):
            with open('/proc/version', 'r') as f:
                version = f.read().lower()
                if 'microsoft' in version or 'wsl' in version:
                    return True
        return False
    except Exception:
        return False


def open_browser_wsl2(url: str) -> bool:
    """Open URL in Windows browser from WSL2.
    
    Uses cmd.exe to execute start command which opens the default browser.
    """
    try:
        # Use cmd.exe to open URL in Windows default browser
        # This works because WSL2 can execute Windows commands
        result = subprocess.run(
            ['cmd.exe', '/c', 'start', '', url],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            return True
        
        # Alternative: Try using PowerShell
        result = subprocess.run(
            ['powershell.exe', '-Command', f'Start-Process "{url}"'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.warning("Timeout opening browser via cmd.exe")
        return False
    except FileNotFoundError:
        logger.debug("cmd.exe or powershell.exe not found")
        return False
    except Exception as e:
        logger.debug(f"Error opening browser in WSL2: {e}")
        return False


def open_browser_linux(url: str) -> bool:
    """Open URL in Linux system browser."""
    # Try common Linux browser commands
    browsers = ['xdg-open', 'x-www-browser', 'www-browser']
    
    for browser_cmd in browsers:
        try:
            result = subprocess.run(
                [browser_cmd, url],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout opening browser with {browser_cmd}")
            continue
        except Exception as e:
            logger.debug(f"Error with {browser_cmd}: {e}")
            continue
    
    return False


def open_browser_macos(url: str) -> bool:
    """Open URL in macOS default browser."""
    try:
        result = subprocess.run(
            ['open', url],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except FileNotFoundError:
        logger.debug("'open' command not found on macOS")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("Timeout opening browser on macOS")
        return False
    except Exception as e:
        logger.debug(f"Error opening browser on macOS: {e}")
        return False


def open_browser_windows(url: str) -> bool:
    """Open URL in Windows default browser."""
    try:
        result = subprocess.run(
            ['cmd', '/c', 'start', '', url],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except FileNotFoundError:
        logger.debug("cmd.exe not found")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("Timeout opening browser on Windows")
        return False
    except Exception as e:
        logger.debug(f"Error opening browser on Windows: {e}")
        return False


def open_url_in_browser(url: str) -> bool:
    """Open URL in the system's default browser.
    
    Works across platforms including WSL2.
    In WSL2, opens the Windows browser.
    
    Returns:
        True if browser was opened successfully, False otherwise
    """
    if not is_valid_url(url):
        logger.warning(f"⚠️  Invalid or unsafe URL rejected: {url}")
        return False

    if is_wsl():
        logger.info("🌐 Detected WSL2 - opening Windows browser...")
        if open_browser_wsl2(url):
            logger.info("✅ Opened URL in Windows browser")
            return True
        else:
            logger.warning("⚠️  Failed to open Windows browser automatically")
            logger.info(f"   Please manually open this URL in your browser:")
            logger.info(f"   {url}")
            return False
    
    # Not WSL - use platform-specific method
    system = platform.system().lower()
    
    if system == 'linux':
        logger.info("🌐 Opening Linux browser...")
        if open_browser_linux(url):
            logger.info("✅ Opened URL in browser")
            return True
        else:
            logger.warning("⚠️  Failed to open browser automatically")
            logger.info(f"   Please manually open this URL in your browser:")
            logger.info(f"   {url}")
            return False
    elif system == 'darwin':
        logger.info("🌐 Opening macOS browser...")
        if open_browser_macos(url):
            logger.info("✅ Opened URL in browser")
            return True
        else:
            logger.warning("⚠️  Failed to open browser automatically")
            logger.info(f"   Please manually open this URL in your browser:")
            logger.info(f"   {url}")
            return False
    elif system == 'windows':
        logger.info("🌐 Opening Windows browser...")
        if open_browser_windows(url):
            logger.info("✅ Opened URL in browser")
            return True
        else:
            logger.warning("⚠️  Failed to open browser automatically")
            logger.info(f"   Please manually open this URL in your browser:")
            logger.info(f"   {url}")
            return False
    else:
        logger.warning(f"⚠️  Unsupported platform: {system}")
        logger.info(f"   Please manually open this URL in your browser:")
        logger.info(f"   {url}")
        return False


class LocalBrowserManager:
    """Manages opening URLs in local browser instead of Playwright."""
    
    def __init__(self, config):
        self.config = config
    
    def perform_sso_login(self, aws_sso_url: str, **kwargs) -> None:
        """Open device authorization URL in local browser.
        
        This is similar to AWS CLI's approach: just open the URL and let the user
        complete authentication in their browser. The browser will use existing
        cookies/sessions, so Microsoft authentication is often skipped.
        
        Args:
            aws_sso_url: The device authorization URL (verificationUriComplete)
            **kwargs: Ignored (kept for compatibility)
        """
        logger.info("🌐 Using local browser for authentication (like AWS CLI)...")
        logger.info("   Your browser will open with the device authorization URL")
        logger.info("   Complete authentication in your browser - it will use your existing cookies/sessions")
        logger.info("   After authentication, you'll see 'You can close this window' - then return here")
        
        # Open the URL in the user's browser
        if open_url_in_browser(aws_sso_url):
            logger.info("")
            logger.info("=" * 70)
            logger.info("⏳ Waiting for you to complete authentication in the browser...")
            logger.info("   After you see 'You can close this window', authentication is complete")
            logger.info("   The polling will automatically detect completion")
            logger.info("=" * 70)
        else:
            logger.info("")
            logger.info("=" * 70)
            logger.info("📋 Please complete authentication:")
            logger.info(f"   1. Open this URL in your browser: {aws_sso_url}")
            logger.info("   2. Complete the authentication (browser will use your cookies)")
            logger.info("   3. After you see 'You can close this window', return here")
            logger.info("=" * 70)
