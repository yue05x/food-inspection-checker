@echo off
git rm -r --cached .
git add backend README.md
git commit -m "feat(backend): optimize OCR and fix oneDNN bug"
git add frontend
git commit -m "feat(frontend): refactor result validation and cards"
git push -f origin main
