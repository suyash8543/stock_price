# StockSeer — Stock Price Prediction Website

A production-ready website that securely calls your ML stock prediction API.
The API key is **never exposed** in the browser — all API calls are proxied through the Flask backend.

---

## Folder Structure

```
stockseer/
├── backend/
│   ├── app.py              ← Flask server (API proxy)
│   ├── .env                ← Your secrets (never commit this!)
│   ├── .env.example        ← Template to share with team
│   ├── .gitignore
│   ├── requirements.txt
│   └── Procfile            ← For Render/Railway deployment
│
└── frontend/
    ├── index.html
    ├── netlify.toml        ← For Netlify deployment
    └── static/
        ├── css/
        │   └── style.css
        └── js/
            └── app.js
```

---

## Step-by-Step: Add Your API Key

### Step 1 — Open the `.env` file
```
stockseer/backend/.env
```

### Step 2 — Replace the placeholder values
```env
STOCK_API_KEY=sk-your-actual-api-key-here        # ← paste your key here
STOCK_API_URL=https://your-real-api.com/predict  # ← your ML API endpoint
FLASK_ENV=development
PORT=5000
```

### Step 3 — Save the file. That's it.
The Flask backend reads this file automatically. Your key never reaches the browser.

> ⚠️ **NEVER commit `.env` to Git.** It's already in `.gitignore`.

---

## Run Locally

### 1. Start the Flask Backend

```bash
cd stockseer/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py
```

Backend will start at: `http://localhost:5000`

### 2. Serve the Frontend

Open a new terminal:

```bash
cd stockseer/frontend

# Option A — Python (simplest)
python -m http.server 8080

# Option B — Node.js
npx serve .
```

Frontend will open at: `http://localhost:8080`

### 3. Test It

Open your browser → `http://localhost:8080`  
Enter a stock symbol (e.g. `AAPL`) → click **Predict Price**

---

## Deploy to Production

### Backend → Render (Free Tier)

1. Push `stockseer/backend/` to a GitHub repository
2. Go to [render.com](https://render.com) → **New Web Service**
3. Connect your GitHub repo
4. Set these settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. Under **Environment Variables**, add:
   - `STOCK_API_KEY` = your real API key
   - `STOCK_API_URL` = your ML API endpoint
   - `FLASK_ENV` = production
6. Click **Deploy**. Copy the URL (e.g. `https://stockseer-api.onrender.com`)

### Backend → Railway (Alternative)

1. Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub**
2. Select your backend repo
3. Add the same environment variables in the **Variables** tab
4. Railway auto-detects the Procfile and deploys

---

### Frontend → Netlify

1. **Update `BACKEND_URL` in `frontend/static/js/app.js`:**
   ```js
   // Line ~9 — replace with your actual Render/Railway URL:
   : "https://stockseer-api.onrender.com"
   ```
2. Push `stockseer/frontend/` to GitHub (separate repo or subfolder)
3. Go to [netlify.com](https://netlify.com) → **Add New Site → Import from Git**
4. Set **Publish Directory** to `frontend` (or root if it's a separate repo)
5. Click **Deploy Site**

---

## API Contract

### Request (frontend → Flask)
```
POST /api/predict
Content-Type: application/json

{ "symbol": "AAPL", "date": "2025-06-01" }   ← date is optional
```

### Flask → Your ML API (server-side)
```
POST https://your-api-url.com/predict
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json

{ "symbol": "AAPL" }
```

### Expected Response from ML API
```json
{
  "predicted_price": 189.45,
  "confidence": 0.92
}
```

> The frontend also handles optional fields: `date`, `accuracy`, `target_date`, `price` — all gracefully.

---

## Health Check

```
GET http://localhost:5000/health
→ { "status": "ok" }
```

---

## Tech Stack

| Layer     | Technology          |
|-----------|---------------------|
| Frontend  | HTML, CSS, Vanilla JS |
| Charts    | Chart.js 4          |
| Backend   | Python Flask        |
| CORS      | flask-cors          |
| Secrets   | python-dotenv (.env)|
| Hosting   | Netlify + Render    |
