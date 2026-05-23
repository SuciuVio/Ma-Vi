# GitHub Actions APK Build

This project can build the Android APK in GitHub Actions, so development can stay
on Windows 11 without local WSL or Ubuntu.

## 1. Push the project to GitHub

Create a GitHub repository, then push `C:\mavi_project` to it.

Example:

```powershell
cd C:\mavi_project
git init
git add .
git commit -m "Initial MaVi Android project"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## 2. Run the APK workflow

On GitHub:

1. Open the repository.
2. Go to `Actions`.
3. Select `Build Android APK`.
4. Click `Run workflow`.
5. Wait for the build to finish.

## 3. Download the APK

After the workflow succeeds:

1. Open the finished workflow run.
2. Scroll to `Artifacts`.
3. Download `mavi-debug-apk`.
4. Extract the zip.
5. Install the APK on Android.

## Notes

- The first build can take a long time because Android SDK, NDK, Gradle, and
  python-for-android dependencies are downloaded and compiled.
- Later builds should be faster because the workflow caches Buildozer and Gradle.
- The workflow builds a debug APK. Release signing can be added later with
  GitHub repository secrets.
