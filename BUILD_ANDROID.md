# Build Android

Buildozer must be run from Linux or WSL. The Windows desktop virtualenv is useful
for development and tests, but Android builds use python-for-android recipes.

## WSL setup

If WSL is not installed yet, open PowerShell as Administrator and run:

```powershell
wsl.exe --install -d Ubuntu
```

Restart Windows if the installer requests it. Then open Ubuntu from the Start
menu once so it can finish creating the Linux user.

```bash
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip python3-venv autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo6 cmake libffi-dev libssl-dev
cd /mnt/c/mavi_project
python3 -m venv .buildozer-venv
source .buildozer-venv/bin/activate
pip install --upgrade pip
pip install buildozer cython
```

## Debug APK

```bash
cd /mnt/c/mavi_project
source .buildozer-venv/bin/activate
buildozer android debug
```

Expected output:

```text
bin/Ma-Vi-0.1.0-debug.apk
```

## Helper scripts

From Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File C:\mavi_project\tools\android_build_preflight.ps1
```

From WSL:

```bash
bash /mnt/c/mavi_project/tools/build_android_wsl.sh
```

## Notes

- The Android build excludes `server/`, `tests/`, `.venv/`, `build/`, and `bin/`.
- Android requirements intentionally omit `pyaudio`; microphone support should be
  completed with an Android-compatible audio bridge or pyjnius integration.
- The backend server is deployed separately and the APK connects to it over HTTP
  and WebSocket using the URLs in `client/utils/constants.py`.
