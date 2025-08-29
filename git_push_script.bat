@echo off
SETLOCAL

REM Check if .git directory exists
IF NOT EXIST .git (
    echo Initializing new Git repository...
    git init
    IF %ERRORLEVEL% NEQ 0 (
        echo Error: Git initialization failed.
        GOTO :EOF
    )
)

echo Adding all files to staging area...
git add .
IF %ERRORLEVEL% NEQ 0 (
    echo Error: Git add failed.
    GOTO :EOF
)

echo Checking for changes to commit...
git diff --cached --exit-code
IF %ERRORLEVEL% NEQ 0 (
    echo Committing changes...
    git commit -m "Automated commit: Updates from local development"
    IF %ERRORLEVEL% NEQ 0 (
        echo Error: Git commit failed.
        GOTO :EOF
    )
) ELSE (
    echo No changes to commit.
)

echo Pushing changes to origin...
git push origin main
IF %ERRORLEVEL% NEQ 0 (
    echo Error: Git push failed. Please ensure your remote is configured and authentication is set up.
    GOTO :EOF
)

echo Git operations completed successfully.
ENDLOCAL