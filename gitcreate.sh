#!/bin/bash

# Set GitHub username
GITHUB_USER="paragonsean"

# Ask for repository name
read -p "Enter the name of the GitHub repository: " REPO_NAME
REPO_NAME=${REPO_NAME:-$(basename "$PWD")}  # Default to folder name if empty

BRANCH_NAME="main"

# Check if the repository exists on GitHub
if gh repo view "$REPO_NAME" &>/dev/null; then
    echo "✅ GitHub repository '$REPO_NAME' already exists."
else
    echo "🚀 Creating GitHub repository: $REPO_NAME..."
    gh repo create "$REPO_NAME" --public --confirm
    echo "✅ Repository '$REPO_NAME' successfully created!"
fi

# Initialize Git if not already initialized
if [ ! -d ".git" ]; then
    echo "🔧 Initializing Git repository..."
    git init
    git branch -M "$BRANCH_NAME"
else
    echo "✅ Git repository already initialized."
fi

# Set the correct remote URL and ensure it's linked properly
REMOTE_URL="https://github.com/$GITHUB_USER/$REPO_NAME.git"

if git remote get-url origin &>/dev/null; then
    echo "✅ Remote 'origin' already exists. Updating URL..."
    git remote set-url origin "$REMOTE_URL"
else
    echo "🔗 Adding remote origin..."
    git remote add origin "$REMOTE_URL"
fi

# Verify that the remote is correctly set
echo "🔍 Checking Git remote..."
git remote -v

# Add all files (excluding nested Git repositories)
echo "📂 Adding files..."
git add .

# Remove accidental nested Git repository (if detected)
if [ -d "AddressBooks/.git" ]; then
    echo "⚠️ Detected nested Git repository 'AddressBooks'! Removing from tracking..."
    git rm -r --cached AddressBooks
    echo "✅ Removed 'AddressBooks' from tracking."
fi

# Commit changes
COMMIT_MESSAGE="Initial commit"
echo "📝 Committing changes..."
git commit -m "$COMMIT_MESSAGE"

# Verify repository existence before pushing
if gh repo view "$REPO_NAME" &>/dev/null; then
    echo "🚀 Pushing to GitHub..."
    git push -u origin "$BRANCH_NAME"
    echo "✅ Repository successfully pushed!"
else
    echo "❌ ERROR: Repository not found on GitHub. Please check your GitHub account or manually create the repository."
fi
