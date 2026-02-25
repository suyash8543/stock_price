/* ─────────────────────────────────────────────────────
───────────────────────────────────────────────────── */

// ── CONFIG ──────────────────────────────────────────
// IMPORTANT: Configure your backend URL here
// Running on port 8000 locally or Render in production

// Detect environment and set backend URL
let BACKEND_URL;

// Check if running on localhost/127.0.0.1
if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
  // Local development - use localhost:8000
  BACKEND_URL = "http://localhost:8000";
  console.log("[StockSeer] Running in LOCAL MODE - Backend: " + BACKEND_URL);
} else {
  // Production - use same origin (both served from same domain)
  BACKEND_URL = window.location.origin;
  console.log("[StockSeer] Running in PRODUCTION MODE - Backend: " + BACKEND_URL);
}

// OVERRIDE: If your backend is on a DIFFERENT domain (like Render), uncomment and update:
// BACKEND_URL = "https://your-flask-backend-name.onrender.com";
// console.log("[StockSeer] OVERRIDE - Custom Backend: " + BACKEND_URL);

// ── STATE ──────────────────────────────────────────
let chartInstance = null;

// ── DOM REFS ───────────────────────────────────────
const form         = document.getElementById("predictForm");
const submitBtn    = document.getElementById("submitBtn");
const symbolInput  = document.getElementById("symbol");
const dateInput    = document.getElementById("date");
const symbolError  = document.getElementById("symbolError");
const loadingState = document.getElementById("loadingState");
const errorState   = document.getElementById("errorState");
const resultWrapper= document.getElementById("resultWrapper");
const errorTitle   = document.getElementById("errorTitle");
const errorMsg     = document.getElementById("errorMsg");

// ── HELPERS ────────────────────────────────────────
function show(el)  { el.hidden = false; }
function hide(el)  { el.hidden = true;  }

function resetUI() {
  hide(loadingState);
  hide(errorState);
  hide(resultWrapper);
  symbolError.textContent = "";
}

function setLoading(on) {
  submitBtn.disabled = on;
  if (on) {
    show(loadingState);
    hide(errorState);
    hide(resultWrapper);
  } else {
    hide(loadingState);
  }
}

function showError(title, msg) {
  errorTitle.textContent = title;
  errorMsg.textContent   = msg;
  show(errorState);
  hide(resultWrapper);
}

function clearResult() {
  resetUI();
  symbolInput.focus();
}

// ── VALIDATE ───────────────────────────────────────
function validate() {
  const val = symbolInput.value.trim();
  if (!val) {
    symbolError.textContent = "Please enter a stock symbol.";
    symbolInput.focus();
    return false;
  }
  if (!/^[A-Za-z.^-]{1,10}$/.test(val)) {
    symbolError.textContent = "Invalid symbol. Use letters only (e.g. AAPL, TSLA).";
    symbolInput.focus();
    return false;
  }
  symbolError.textContent = "";
  return true;
}

// ── API CALL ───────────────────────────────────────
async function fetchPrediction(symbol, date) {
  const body = { symbol };
  if (date) body.date = date;

  const url = `${BACKEND_URL}/api/predict`;
  console.log("[API] Calling:", url, "with symbol:", symbol);

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    console.log("[API] Response status:", resp.status, resp.statusText);

    const data = await resp.json();
    console.log("[API] Response data:", data);

    if (!resp.ok) {
      const msg = data.error || `Server error ${resp.status}`;
      const detail = data.detail ? JSON.stringify(data.detail) : "";
      const errMsg = detail ? `${msg} — ${detail}` : msg;
      console.error("[API] Error:", errMsg);
      throw new Error(errMsg);
    }

    console.log("[API] Success!");
    return data;
  } catch (err) {
    console.error("[API] Exception:", err.message);
    throw err;
  }
}

// ── RENDER RESULTS ─────────────────────────────────
function renderResults(data, symbol) {
  // Extract price from various possible response formats
  let price = 0;

  // Try to get from predicted_price field
  if (data.predicted_price !== undefined && data.predicted_price > 0) {
    price = parseFloat(data.predicted_price);
  }
  // Try from first item in next_60_days array
  else if (data.next_60_days && data.next_60_days.length > 0) {
    price = parseFloat(data.next_60_days[0].Predicted_Close || 0);
  }
  // Try other common field names
  else {
    price = parseFloat(data.price || data.prediction || data.forecast || 0);
  }

  // Get confidence
  const confidence = parseFloat(data.confidence ?? data.accuracy ?? 0.65);
  const date = (data.date ?? data.target_date ?? dateInput.value) || "Today";

  // ── Summary cards
  document.getElementById("rPrice").textContent    = `$${price.toFixed(2)}`;
  document.getElementById("rSymbolBadge").textContent = symbol;
  document.getElementById("rDate").textContent     = date;
  document.getElementById("chartBadge").textContent = symbol;

  const confPct = (confidence * 100).toFixed(1);
  document.getElementById("rConf").textContent     = confidence <= 1
    ? `${confPct}%` : `${confidence.toFixed(1)}%`;

  const confBarEl = document.getElementById("confBar");
  setTimeout(() => {
    confBarEl.style.width = confidence <= 1
      ? `${confidence * 100}%`
      : `${Math.min(confidence, 100)}%`;
  }, 100);

  // Signal
  const signalEl = document.getElementById("rSignal");
  const signalSub = document.getElementById("rSignalSub");
  if (confidence >= 0.75 || confidence >= 75) {
    signalEl.textContent = "↑ BUY";
    signalEl.style.color = "var(--green)";
    signalSub.textContent = "High confidence";
  } else if (confidence >= 0.5 || confidence >= 50) {
    signalEl.textContent = "→ HOLD";
    signalEl.style.color = "var(--amber)";
    signalSub.textContent = "Moderate confidence";
  } else {
    signalEl.textContent = "↓ CAUTION";
    signalEl.style.color = "var(--red)";
    signalSub.textContent = "Lower confidence";
  }

  // Raw JSON
  document.getElementById("rawJson").textContent = JSON.stringify(data, null, 2);

  // Chart
  renderChart(price, symbol);

  show(resultWrapper);
}

// ── CHART ──────────────────────────────────────────
function renderChart(predictedPrice, symbol) {
  const ctx = document.getElementById("priceChart").getContext("2d");

  if (chartInstance) { chartInstance.destroy(); }

  // Synthesise 7 days of "historical" values trending toward prediction
  const today = new Date();
  const labels = [];
  const historical = [];
  const seed = predictedPrice;

  for (let i = 6; i >= 1; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    labels.push(d.toLocaleDateString("en-US", { month:"short", day:"numeric" }));
    const noise = (Math.random() - 0.5) * seed * 0.04;
    historical.push(+(seed * (1 - 0.025 * i) + noise).toFixed(2));
  }
  labels.push("Today");
  historical.push(null); // gap before prediction

  labels.push("Predicted");
  const predictionData = Array(historical.length).fill(null);
  predictionData[predictionData.length - 2] = historical[historical.length - 2] ?? historical[historical.length - 3];
  predictionData[predictionData.length - 1] = predictedPrice;

  const gridColor  = "rgba(56,189,248,0.07)";
  const textColor  = "#4d6a8a";

  chartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Historical (simulated)",
          data: historical,
          borderColor: "#38bdf8",
          backgroundColor: "rgba(56,189,248,0.08)",
          borderWidth: 2.5,
          pointRadius: 4,
          pointBackgroundColor: "#38bdf8",
          pointBorderColor: "#060b18",
          pointBorderWidth: 2,
          fill: true,
          tension: 0.4,
        },
        {
          label: "AI Prediction",
          data: predictionData,
          borderColor: "#34d399",
          backgroundColor: "rgba(52,211,153,0.08)",
          borderWidth: 2.5,
          borderDash: [6, 4],
          pointRadius: [0,0,0,0,0,0,0, 8],
          pointBackgroundColor: "#34d399",
          pointBorderColor: "#060b18",
          pointBorderWidth: 2,
          fill: false,
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 1000, easing: "easeInOutQuart" },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: {
            color: textColor,
            font: { family: "DM Mono", size: 12 },
            boxWidth: 20,
          },
        },
        tooltip: {
          backgroundColor: "#0d1526",
          borderColor: "rgba(56,189,248,0.3)",
          borderWidth: 1,
          titleColor: "#38bdf8",
          bodyColor: "#e2eeff",
          titleFont: { family: "Syne", size: 13 },
          bodyFont: { family: "DM Mono", size: 12 },
          padding: 14,
          callbacks: {
            label: ctx => ctx.parsed.y !== null
              ? ` ${ctx.dataset.label}: $${ctx.parsed.y.toFixed(2)}`
              : null,
          },
        },
      },
      scales: {
        x: {
          grid: { color: gridColor },
          ticks: { color: textColor, font: { family: "DM Mono", size: 11 } },
        },
        y: {
          grid: { color: gridColor },
          ticks: {
            color: textColor,
            font: { family: "DM Mono", size: 11 },
            callback: v => `$${v.toFixed(0)}`,
          },
        },
      },
    },
  });
}

// ── FORM SUBMIT ────────────────────────────────────
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  resetUI();

  if (!validate()) return;

  const symbol = symbolInput.value.trim().toUpperCase();
  const date   = dateInput.value || "";

  setLoading(true);

  try {
    const data = await fetchPrediction(symbol, date);
    renderResults(data, symbol);
  } catch (err) {
    showError("Prediction Failed", err.message || "Unknown error. Check your connection.");
  } finally {
    setLoading(false);
  }
});

// Auto-uppercase symbol input
symbolInput.addEventListener("input", () => {
  const pos = symbolInput.selectionStart;
  symbolInput.value = symbolInput.value.toUpperCase();
  symbolInput.setSelectionRange(pos, pos);
});

// Expose clearResult globally (used by inline onclick)
window.clearResult = clearResult;
