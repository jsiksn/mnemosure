# Deploying the demo to Alibaba Cloud (ECS + Docker)

This deploys the Mnemosure **demo web server** to a single Alibaba Cloud ECS
instance as one Docker container. The container serves the scenario browser,
memory warehouse, before/after evaluation panels, and the live `/ask` grounded
recall.

> **Scope.** This is about the *demo*. The product itself (`pip install
> mnemosure` — the memory library + MCP server) is unchanged and is not part of
> this image; the deployment files live only in the repository. See the
> [main README](../README.md).

---

## What you need

- An **Alibaba Cloud account** (the free tier is enough for a small ECS instance).
- A **Qwen / DashScope API key** (`DASHSCOPE_API_KEY`). The demo calls Qwen only
  for the live `/ask`; everything else renders from committed snapshots, so the
  page loads even without a key.

You do **not** need a container registry (ACR) or any registry credentials — the
image is built directly on the ECS instance. The repository is public, so no
GitHub token is needed to clone it.

---

## 1. Create the ECS instance

1. In the ECS console, create an instance:
   - Image: **Ubuntu 22.04** (or Alibaba Cloud Linux 3).
   - Type: a small shared instance (e.g. 1–2 vCPU / 2 GB) is fine for the demo.
   - Public IP: **assign one** (or bind an EIP) so it's reachable.
   - Set a login (SSH key pair recommended, or a password).
2. In the instance's **Security Group**, add an **inbound rule**:
   - Protocol **TCP**, port **8000**, source `0.0.0.0/0` (open to all for the demo).
   - (Keep port 22 open only to your own IP for SSH.)

> Serving on port **80** instead? Map it at run time with `-p 80:8000` (step 4)
> and open port 80 in the security group.

## 2. Install Docker on the instance

SSH in, then:

```bash
# Ubuntu
sudo apt-get update && sudo apt-get install -y docker.io git
sudo systemctl enable --now docker
```

## 3. Get the code and build the image

```bash
git clone https://github.com/jsiksn/mnemosure.git
cd mnemosure
sudo docker build -t mnemosure-demo .
```

The build installs `requirements.txt` (which includes FastAPI/uvicorn) and copies
the source plus the precomputed demo snapshots into the image. No API key is
baked in.

## 4. Run the container

```bash
sudo docker run -d --name mnemosure-demo \
  -p 8000:8000 \
  -e DASHSCOPE_API_KEY="your-dashscope-api-key" \
  --restart unless-stopped \
  mnemosure-demo
```

- `-e DASHSCOPE_API_KEY=...` injects the key at run time (never in the image).
- `--restart unless-stopped` brings the demo back after a reboot.

**If a default model's quota is exhausted**, override it per run without touching
code (see `mnemosure/config.py` for the defaults) — the live `/ask` uses the
embedding, rerank, and *brain* models (not the flash model):

```bash
  -e MNEMOSURE_MODEL_BRAIN="<another-qwen-model>" \
```

## 5. Verify

```bash
# health check (no Qwen call)
curl http://<PUBLIC_IP>:8000/health
# -> {"status":"ok","scenarios":["nxtbot","pricing"]}
```

Then open `http://<PUBLIC_IP>:8000/` in a browser and confirm:

- the scenario switcher, memory warehouse, and before/after panels render
  (these come from the snapshot — they work even with no key);
- asking a question returns a grounded answer with a confidence level and cited
  sources (this is the live `/ask` — needs a valid key and quota).

For the submission, capture the **public URL** and a **screenshot** of the demo
running.

---

## Operations notes

- **Logs:** `sudo docker logs -f mnemosure-demo`
- **Update to the latest code:** `git pull && sudo docker build -t mnemosure-demo . && sudo docker rm -f mnemosure-demo` then re-run step 4.
- **Stop / remove:** `sudo docker rm -f mnemosure-demo`
- **Security:** a public demo means anyone can hit `/ask` and spend your Qwen
  quota. After judging, stop the instance (or rotate the key). The key lives only
  in the container's environment, never in the image or in git.
