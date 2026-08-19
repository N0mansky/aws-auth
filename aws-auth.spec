# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['aws-auth.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['aws_auth', 'aws_auth.cli', 'aws_auth.mcp_server', 'aws_auth.auth_manager', 'aws_auth.caller_identity', 'aws_auth.config', 'aws_auth.credentials_manager', 'aws_auth.ec2_manager', 'aws_auth.eks_manager', 'aws_auth.local_browser_manager', 'aws_auth.profile_manager', 'aws_auth.sso_client', 'aws_auth.token_manager', 'aws_auth.user_interface'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='aws-auth',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
