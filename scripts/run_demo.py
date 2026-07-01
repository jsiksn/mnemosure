"""
데모 웹 서버 실행기.

먼저 scripts/gen_demo_data.py 를 1회 돌려 data/memories.json·demo_results.json 을 만든 뒤 실행.
실행:  python scripts/run_demo.py   →  http://127.0.0.1:8000

(uvicorn 직접 실행도 가능:  uvicorn mnemosure.demo.server:app --port 8000)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import uvicorn  # noqa: E402

from mnemosure.demo.server import app  # noqa: E402

if __name__ == "__main__":
    print("데모 서버: http://127.0.0.1:8000  (Ctrl+C로 종료)")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
