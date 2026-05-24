[app]
title = Ma:Vi
package.name = mavi
package.domain = com.mavi
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,sql,md
source.exclude_dirs = .venv,tests,bin,build,__pycache__,server
icon.filename = %(source.dir)s/assets/icon.png
version = 0.1.0
requirements = python3==3.10.11,hostpython3==3.10.11,kivy==2.2.1,kivymd==1.1.1,websockets,cryptography==41.0.7,plyer
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,RECORD_AUDIO,ACCESS_NETWORK_STATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 35
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a
android.private_storage = True
android.accept_sdk_license = True

[app:desktop]
requirements = -r requirements.txt

[buildozer]
log_level = 2
warn_on_root = 1
