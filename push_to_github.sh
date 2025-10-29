#!/bin/bash

# Helper script to push to GitHub

echo "========================================="
echo "Unity Copy Trader - GitHub Push Helper"
echo "========================================="
echo ""

# Check if remote is configured
if ! git remote | grep -q "origin"; then
    echo "⚠️  No GitHub remote configured!"
    echo ""
    echo "Please enter your GitHub username:"
    read -r username

    echo "Repository name (default: Unity-copy-trader):"
    read -r repo_name
    repo_name=${repo_name:-Unity-copy-trader}

    echo ""
    echo "Choose connection method:"
    echo "1) HTTPS (easier, uses token)"
    echo "2) SSH (more secure, uses SSH key)"
    read -r choice

    if [ "$choice" = "2" ]; then
        remote_url="git@github.com:$username/$repo_name.git"
    else
        remote_url="https://github.com/$username/$repo_name.git"
    fi

    echo "Adding remote: $remote_url"
    git remote add origin "$remote_url"
    echo "✅ Remote added successfully!"
    echo ""
fi

# Show current status
echo "📊 Current Status:"
echo "-------------------"
git status --short
echo ""

# Show remote
echo "🔗 Remote Repository:"
git remote -v | head -1
echo ""

# Push to GitHub
echo "🚀 Pushing to GitHub..."
echo "-------------------"

if git push -u origin master 2>/dev/null; then
    echo "✅ Successfully pushed to GitHub!"
elif git push -u origin main 2>/dev/null; then
    echo "✅ Successfully pushed to GitHub (main branch)!"
else
    echo ""
    echo "⚠️  Push failed. Possible reasons:"
    echo "1. Repository doesn't exist on GitHub yet"
    echo "   → Create it at: https://github.com/new"
    echo ""
    echo "2. Authentication required"
    echo "   → For HTTPS: Use Personal Access Token"
    echo "   → Create at: https://github.com/settings/tokens"
    echo ""
    echo "3. Branch name mismatch"
    echo "   → Try: git branch -m master main"
    echo "   → Then: git push -u origin main"
    echo ""
    echo "Manual push command:"
    echo "git push -u origin master"
fi

echo ""
echo "========================================="
echo "Done!"
echo "========================================="