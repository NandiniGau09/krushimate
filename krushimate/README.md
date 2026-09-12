# Krushimate - Smart Farming App (Prototype)

This is a local prototype of Krushimate built with Flask. It uses browser localStorage and local JSON files in `/data` for storing data (no external database).

## Run locally
1. Create a virtual environment (recommended)
   ```bash
   python3 -m venv venv
   source venv/bin/activate     # on Windows: venv\Scripts\activate
   pip install flask
   ```
2. Run the app
   ```bash
   python app.py
   ```
3. Open http://127.0.0.1:5000 in your browser.

## Notes
- This prototype stores credentials locally for ease of testing. Do NOT use this for production.
- The medicine ordering is simulated and stored in localStorage and `data/orders.json` when using the Flask API endpoints.
- The disease detection page is a placeholder for future ML integration.
