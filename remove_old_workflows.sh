#!/bin/bash

echo "🔍 Checking for old workflow files..."

cd .github/workflows || { echo "❌ Cannot find .github/workflows directory"; exit 1; }

FILES_TO_DELETE=("x_bot_workflow.yml" "bluesky_bot_workflow.yml")

for file in "${FILES_TO_DELETE[@]}"; do
    if [ -f "$file" ]; then
        echo "🗑️  Deleting $file"
        rm "$file"
    else
        echo "⚠️  $file not found, skipping"
    fi
done

cd ../../

echo "📦 Committing changes..."
git add .github/workflows/
git commit -m "Remove old separate bot workflows"
git push

echo "✅ Done!"
