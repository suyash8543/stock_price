"""
🚀 StockSeer - Complete Application Launcher
Run this script to start everything
"""

import subprocess
import time
import os
import webbrowser

print("\n" + "="*70)
print("  🚀 STOCKSEER - STOCK PRICE PREDICTION APP")
print("="*70)

backend_dir = r"d:\Project\Stock price  project\stockseer-project\stockseer\backend"

# Kill any existing Python processes on these ports
print("\n[1] Cleaning up old processes...")
subprocess.run("taskkill /F /IM python.exe /FI \"WINDOWTITLE eq *python*\" 2>nul", shell=True, capture_output=True)
time.sleep(2)

# Start backend
print("[2] Starting FastAPI Backend on port 8000...")
print("    📍 Backend: http://127.0.0.1:8000")

env = os.environ.copy()
env['PORT'] = '8000'
env['FLASK_ENV'] = 'development'

backend_proc = subprocess.Popen(
    ['python', 'app.py'],
    cwd=backend_dir,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Wait for backend to start
time.sleep(3)

print("[3] Backend started successfully! ✅")
print("\n" + "="*70)
print("  ✅ ALL SYSTEMS RUNNING")
print("="*70)
print("\n📊 ENDPOINTS:")
print("   • Health Check: http://127.0.0.1:8000/health")
print("   • API Predict:  http://127.0.0.1:8000/api/predict")
print("   • Type: POST with JSON: {\"symbol\": \"AAPL\"}")
print("\n📖 DOCUMENTATION:")
print("   • API Docs: http://127.0.0.1:8000/docs")
print("\n🧪 TEST COMMANDS:")
print('   curl -X POST http://127.0.0.1:8000/api/predict -H "Content-Type: application/json" -d "{\\"symbol\\": \\"AAPL\\"}"')
print("\n" + "="*70)
print("\n✨ Backend is running! Use the endpoints above to test.")
print("   Press Ctrl+C to stop the server.\n")

try:
    backend_proc.wait()
except KeyboardInterrupt:
    print("\n\n[STOP] Shutting down...")
    backend_proc.terminate()
    time.sleep(1)
    backend_proc.kill()
    print("✅ Backend stopped")

