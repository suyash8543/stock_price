import os
import logging
import requests
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ─── Setup Logging ────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="StockSeer Backend", version="1.0.0")

# ─── CORS Configuration ────────────────────────────────────────────────────
# IMPORTANT: In production, set FRONTEND_ORIGIN to your actual Netlify URL
# This prevents cross-origin attacks. Do NOT use "*" in production!
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
if FRONTEND_ORIGIN == "*":
    logger.warning("[WARN] CORS is configured with '*'. This is OK for development, but MUST be set to your frontend URL in production!")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGIN.split(",") if FRONTEND_ORIGIN != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API Configuration ────────────────────────────────────────────────────
# GET YOUR API KEY: Sign up at https://groq.com and set it in your .env file
# The backend uses environment variables for all sensitive configuration
BASE_URL = os.getenv("STOCK_API_URL", "https://stock-price-prediction-7.onrender.com/analyze_stock")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "40"))

# Extract base URL for GET endpoint (remove /analyze_stock if present)
if BASE_URL.endswith("/analyze_stock"):
    base_api_url = BASE_URL.replace("/analyze_stock", "")
else:
    base_api_url = BASE_URL

POST_URL  = f"{base_api_url}/analyze_stock"
GET_URL   = f"{base_api_url}/get_predictions"

# Validate configuration
if not BASE_URL:
    logger.info("Using default API URL. Update STOCK_API_URL in .env if needed.")

logger.info(f"[OK] API URL (POST): {POST_URL}")
logger.info(f"[OK] API URL (GET): {GET_URL}")
logger.info(f"[OK] Timeout: {API_TIMEOUT}s")
logger.info(f"[OK] CORS Origin: {FRONTEND_ORIGIN if FRONTEND_ORIGIN != '*' else '* (development only)'}")


# ── Serve Frontend ────────────────────────────────────────────────────────────

# Mount static files (frontend)
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path / "static")), name="static")


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return JSONResponse({
        "status":    "ok",
        "post_url":  POST_URL,
        "get_url":   GET_URL + "/{stock}",
    })


# ── Models ────────────────────────────────────────────────────────────────────

class PredictionRequest(BaseModel):
    symbol: str
    date: str = None


# ── Predict ───────────────────────────────────────────────────────────────────

@app.post("/api/predict")
async def predict(request: PredictionRequest):
    """Get stock price prediction from ML API"""
    data = {"symbol": request.symbol}
    if request.date:
        data["date"] = request.date

    stock = data.get("symbol", "").strip().upper()
    if not stock:
        return JSONResponse({"error": "Missing field: symbol"}, status_code=400)

    if not stock or len(stock) > 10 or not stock.replace(".", "").replace("^", "").replace("-", "").isalpha():
        return JSONResponse({"error": "Invalid symbol format"}, status_code=400)

    # ── Strategy 1: POST /analyze_stock  {"stock": "AAPL"}
    # ── Strategy 2: GET  /get_predictions/AAPL  (fallback)
    # We try POST first; if it returns 422/404 we fall back to GET.

    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    # --- Try POST ---
    try:
        post_resp = requests.post(
            POST_URL,
            json={"stock": stock},
            headers=headers,
            timeout=API_TIMEOUT,
        )

        if post_resp.status_code == 200:
            logger.info(f"[OK] Prediction successful for {stock}")
            return JSONResponse(normalise(post_resp.json(), stock), status_code=200)

        # POST didn't work — log reason and fall through to GET
        logger.warning(f"[WARN] POST /analyze_stock failed with {post_resp.status_code} for {stock}")
        post_error = {
            "status": post_resp.status_code,
            "body":   post_resp.text[:300],
        }

    except requests.exceptions.Timeout:
        logger.error(f"Timeout (POST) for {stock} after {API_TIMEOUT}s")
        return JSONResponse({
            "error": f"API timed out ({API_TIMEOUT}s).",
            "hint":  "Your Render service may be sleeping. Wait 30s and try again."
        }, status_code=504)
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error for {stock}: {e}")
        return JSONResponse({
            "error":  "Cannot reach Render server.",
            "detail": str(e),
        }, status_code=502)
    except Exception as e:
        logger.error(f"Unexpected error (POST) for {stock}: {e}")
        post_error = {"exception": str(e)}

    # --- Fallback: GET /get_predictions/{stock} ---
    try:
        get_resp = requests.get(
            f"{GET_URL}/{stock}",
            headers={"Accept": "application/json"},
            timeout=API_TIMEOUT,
        )

        if get_resp.status_code == 200:
            logger.info(f"[OK] Prediction successful (fallback GET) for {stock}")
            return JSONResponse(normalise(get_resp.json(), stock), status_code=200)

        # Both failed — return detailed error
        logger.error(f"GET /get_predictions/{stock} failed with {get_resp.status_code}")
        try:
            get_detail = get_resp.json()
        except Exception:
            get_detail = get_resp.text[:400]

        return JSONResponse({
            "error":       "Both API attempts failed.",
            "post_result": post_error,
            "get_status":  get_resp.status_code,
            "get_detail":  get_detail,
            "hint":        f"Visit {BASE_URL}/docs to check the API manually.",
        }, status_code=502)

    except requests.exceptions.Timeout:
        logger.error(f"Timeout (GET fallback) for {stock} after {API_TIMEOUT}s")
        return JSONResponse({
            "error": f"API timed out on fallback GET request ({API_TIMEOUT}s).",
            "hint":  "Render free tier is sleeping. Wait 30s and try again."
        }, status_code=504)
    except Exception as e:
        logger.error(f"Unexpected error (GET fallback) for {stock}: {e}")
        return JSONResponse({
            "error":       "Both API strategies failed.",
            "post_result": post_error,
            "get_error":   str(e),
        }, status_code=500)


# ── Normalise any response shape → consistent frontend keys ───────────────────

def normalise(result, stock=""):
    """
    Your API might return many different field names.
    We map all known variants to predicted_price and confidence.
    Everything else is passed through as-is.
    """
    # Find the price
    price = (
        result.get("predicted_price")
        or result.get("prediction")
        or result.get("price")
        or result.get("predicted_close")
        or result.get("next_close")
        or result.get("forecast")
        or result.get("close")
        or result.get("next_day_price")
        or result.get("tomorrow_price")
        or 0
    )

    # Find the confidence
    raw_conf = (
        result.get("confidence")
        or result.get("accuracy")
        or result.get("score")
        or result.get("confidence_score")
        or result.get("model_accuracy")
        or result.get("r2")
        or 0
    )
    # Normalise to 0-1 (some models return 92.5 instead of 0.925)
    confidence = float(raw_conf) / 100.0 if float(raw_conf) > 1 else float(raw_conf)

    skip = {
        "predicted_price","prediction","price","predicted_close","next_close",
        "forecast","close","next_day_price","tomorrow_price",
        "confidence","accuracy","score","confidence_score","model_accuracy","r2"
    }

    return {
        "predicted_price": float(price),
        "confidence":      confidence,
        "symbol":          stock,
        # pass through everything else (dates, charts, extra fields)
        **{k: v for k, v in result.items() if k not in skip},
    }


# ── Frontend Serving (catch-all at the end) ──────────────────────────────────────

@app.get("/")
async def serve_index():
    """Serve the frontend index.html"""
    index_path = frontend_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path), media_type="text/html")
    return JSONResponse({"error": "Frontend not found"}, status_code=404)


@app.get("/{path:path}")
async def serve_static(path: str):
    """Serve static frontend files, fallback to index.html"""
    static_path = frontend_path / path
    if static_path.exists() and static_path.is_file():
        return FileResponse(str(static_path))
    # Fallback to index.html for SPA routing
    index_path = frontend_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path), media_type="text/html")
    return JSONResponse({"error": "File not found"}, status_code=404)


# ── Start ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 5000))
    debug_mode = os.getenv("FLASK_ENV") == "development"

    print(f"\n{'='*60}")
    print(f"  StockSeer (FastAPI) -> http://127.0.0.1:{port}")
    print(f"{'='*60}")
    print(f"  Open in browser : http://127.0.0.1:{port}/")
    print(f"  API Docs        : http://127.0.0.1:{port}/docs")
    print(f"  POST endpoint   : {POST_URL}")
    print(f"  GET  endpoint   : {GET_URL}/{{stock}}")
    print(f"  Auth            : None (public API)")
    print(f"{'='*60}\n")

    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=port,
        reload=debug_mode,
        log_level="info"
    )
