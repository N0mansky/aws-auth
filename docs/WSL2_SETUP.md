# WSL2 (Windows Subsystem for Linux) Setup Guide

Developing in WSL2 while using AWS SSO often encounters browser launch friction because Linux tools cannot easily launch native Windows browsers.

`aws-auth` comes with built-in **WSL2 Windows Browser Bridge**.

---

## 🚀 How It Works

When `aws-auth` runs inside WSL2:
1. It automatically detects the WSL environment (`/proc/sys/fs/binfmt_misc/WSLInterop` or `/proc/version`).
2. It initiates the AWS IAM Identity Center device authorization flow.
3. Instead of failing or printing a raw URL in the terminal, it executes `powershell.exe /c start <url>` or `cmd.exe /c start <url>`.
4. Your default Windows browser (Chrome, Edge, Firefox, Brave) instantly pops up with your active Windows corporate SSO session!

---

## ⚡ Sharing Credentials between WSL2 & Windows

To make your Windows AWS tools (e.g., PowerShell AWS CLI, VS Code on Windows) share credentials authenticated inside WSL2:

```bash
# In your ~/.bashrc or ~/.zshrc in WSL2:
# Symlink ~/.aws to Windows .aws directory (optional)
# ln -s /mnt/c/Users/<YourUsername>/.aws ~/.aws
```
