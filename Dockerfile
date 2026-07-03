# Mnemosure 데모 웹 서버 컨테이너.
#
# 주의: pip 패키지(`pip install mnemosure`)는 코어-only(메모리+MCP)라 데모가 없다.
# 그래서 이미지는 requirements.txt 기반으로 빌드하고 소스를 통째로 넣어 데모를 띄운다.
# API 키는 이미지에 굽지 않는다 — 런타임에 -e DASHSCOPE_API_KEY=... 로 주입한다(.dockerignore가 .env 제외).
FROM python:3.12-slim

WORKDIR /app

# 1) 의존성 먼저 설치(레이어 캐시 활용). requirements 에 fastapi·uvicorn 포함.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 2) 소스 + 데모 + 사전계산 스냅샷 복사.
#    - mnemosure/ : 코어 + demo/(index.html 포함)
#    - scripts/   : run_demo.py (실행기)
#    - data/      : 시나리오별 memories.json·results.json (키 없이 렌더되는 스냅샷)
#    - pyproject.toml : storage 경로 해석이 '레포 컨텍스트'를 인식하도록
COPY mnemosure/ ./mnemosure/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY pyproject.toml README.md ./

# 3) 실행 환경. 컨테이너는 외부 공개용이라 0.0.0.0 바인딩.
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

CMD ["python", "scripts/run_demo.py"]
