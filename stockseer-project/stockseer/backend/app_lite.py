import os
import logging
import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="StockSeer Backend", version="1.0.0")

# CORS
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
BASE_URL = os.getenv("STOCK_API_URL", "https://stock-price-prediction-7.onrender.com/analyze_stock")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "40"))

if BASE_URL.endswith("/analyze_stock"):
    base_api_url = BASE_URL.replace("/analyze_stock", "")
else:
    base_api_url = BASE_URL

POST_URL = f"{base_api_url}/analyze_stock"
GET_URL = f"{base_api_url}/get_predictions"

logger.info(f"[OK] API URL (POST): {POST_URL}")
logger.info(f"[OK] API URL (GET): {GET_URL}")
logger.info(f"[OK] Timeout: {API_TIMEOUT}s")


# Routes
@app.get("/health")
async def health():
    return JSONResponse({
        "status": "ok",
        "post_url":  POST_URL,
        "get_url":  GET_URL + "/{stock}",
    })


class PredictionRequest(BaseModel):
    symbol: str
    date: str = None


@app.post("/api/predict")
async def predict(request: PredictionRequest):
    """Get stock price prediction from ML API"""
    stock = request.symbol.strip().upper()
    if not stock:
        return JSONResponse({"error": "Missing field: symbol"}, status_code=400)

    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    # Try POST
    try:
        post_resp = requests.post(
            POST_URL,
            json={"stock": stock},
            headers=headers,
            timeout=API_TIMEOUT,
        )

        if post_resp.status_code == 200:
            logger.info(f"[OK] Prediction successful for {stock}")
            data = post_resp.json()
            return JSONResponse(normalise(data, stock), status_code=200)

        logger.warning(f"[WARN] POST failed with {post_resp.status_code} for {stock}")
        post_error = {
            "status": post_resp.status_code,
            "body": post_resp.text[:300],
        }

    except requests.exceptions.Timeout:
        logger.error(f"Timeout (POST) for {stock}")
        return JSONResponse({
            "error": f"API timed out ({API_TIMEOUT}s).",
            "hint": "Your Render service may be sleeping. Wait 30s and try again."
        }, status_code=504)
    except Exception as e:
        logger.error(f"Error (POST) for {stock}: {e}")
        post_error = {"exception": str(e)}

    # Fallback to GET
    try:
        get_resp = requests.get(
            f"{GET_URL}/{stock}",
            headers={"Accept": "application/json"},
            timeout=API_TIMEOUT,
        )

        if get_resp.status_code == 200:
            logger.info(f"[OK] Prediction successful (GET) for {stock}")
            return JSONResponse(normalise(get_resp.json(), stock), status_code=200)

        logger.error(f"GET failed with {get_resp.status_code} for {stock}")
        return JSONResponse({
            "error": "API failed",
            "status": get_resp.status_code,
        }, status_code=502)

    except Exception as e:
        logger.error(f"Error (GET) for {stock}: {e}")
        return JSONResponse({
            "error": "Both API attempts failed",
            "error_detail": str(e),
        }, status_code=500)


def normalise(result, stock=""):
    """Normalise API response"""
    price = (
        result.get("predicted_price")
        or result.get("prediction")
        or result.get("price")
        or result.get("predicted_close")
        or result.get("forecast")
        or 0
    )

    raw_conf = (
        result.get("confidence")
        or result.get("accuracy")
        or result.get("score")
        or 0
    )
    confidence = float(raw_conf) / 100.0 if float(raw_conf) > 1 else float(raw_conf)

    return {
        "predicted_price": float(price),
        "confidence": confidence,
        "symbol": stock,
        **result,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 5000))
    print(f"\n{'='*60}")
    print(f"  StockSeer API (Lite) -> http://127.0.0.1:{port}")
    print(f"{'='*60}")
    print(f"  Endpoints:")
    print(f"    GET  /health")
    print(f"    POST /api/predict")
    print(f"{'='*60}\n")

    uvicorn.run(
        "app_lite:app",
        host="127.0.0.1",
        port=port,
        reload=False,
        log_level="info"
    )
