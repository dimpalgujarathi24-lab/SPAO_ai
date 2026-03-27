# Shark Tank AI Investor

A hackathon-level startup pitch analyzer built with Flask + vanilla JS.
No paid APIs required. Fully offline after install.

## Setup

1. Open this folder in VS Code
2. Press Ctrl+` to open the terminal
3. Run: python -m venv .venv
4. Press Ctrl+Shift+P → Python: Select Interpreter → choose .venv
5. Reopen terminal, run: pip install flask flask-cors pandas
6. cd backend
7. python app.py   ← keep this terminal open

## Open the frontend

8. In VS Code, right-click frontend/index.html → Open with Live Server
   OR just open frontend/index.html directly in Chrome

## API

POST http://127.0.0.1:5000/analyze
Body: { "pitch": "your pitch text here" }