@echo off
echo Adding all files to git...
git add .

echo Creating a new commit...
git commit -m "Update project"

echo Force pushing to the remote repository...
git push --force https://github.com/unsuns06/ReplayTV-Stremio main

echo.
echo Push complete.
pause