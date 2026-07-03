"""
데모 웹 서버 실행기.

먼저 scripts/gen_demo_data.py 를 1회 돌려 data/memories.json·demo_results.json 을 만든 뒤 실행.
실행:  python scripts/run_demo.py   →  http://127.0.0.1:8000

바인딩은 환경변수로 바꾼다(코드 수정 없이):
  - HOST : 바인딩 주소. 기본 127.0.0.1(로컬 전용). 외부 공개(컨테이너·클라우드)에선 0.0.0.0.
  - PORT : 포트. 기본 8000.
컨테이너/배포에서는 HOST=0.0.0.0 을 주입한다(Dockerfile 참고).

(uvicorn 직접 실행도 가능:  uvicorn mnemosure.demo.server:app --host 0.0.0.0 --port 8000)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import uvicorn  # noqa: E402

from mnemosure.demo.server import app  # noqa: E402

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"데모 서버: http://{host}:{port}  (Ctrl+C로 종료)")
    uvicorn.run(app, host=host, port=port, log_level="warning")
