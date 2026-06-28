import uvicorn

if __name__ == "__main__":
    # 0.0.0.0 so Tailscale/LAN-connected devices (e.g. the Looper Remote Android app) can reach
    # this server, not just the local machine. The per-company 8-char code is the actual gate.
    uvicorn.run("app.main:app", host="0.0.0.0", port=8731, reload=False)
