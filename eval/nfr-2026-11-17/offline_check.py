"""NFR03: run upload -> index -> chat inside the stack while its network has no route out.

Runs inside the service container (stdlib only). Reads ADMIN_EMAIL / ADMIN_PASSWORD from the container env.
"""
import json
import os
import socket
import time
import urllib.error
import urllib.request
import uuid

API = "http://localhost:8000"
FILES = ["/tmp/offline/08_QC_Procedure_Dried_Mango.txt", "/tmp/offline/06_Supply_Agreement.pdf"]
QUESTION = "What are the critical control points in our dried mango QC procedure?"
report = {"started": time.strftime("%Y-%m-%d %H:%M:%S %z")}


def outbound(host, port):
    try:
        socket.create_connection((host, port), timeout=5).close()
        return "connected"
    except OSError as error:
        return f"blocked ({type(error).__name__}: {error})"


report["outbound_huggingface.co:443"] = outbound("huggingface.co", 443)
report["outbound_1.1.1.1:443"] = outbound("1.1.1.1", 443)


def call(method, path, body=None, token=None, content_type="application/json", timeout=300):
    headers = {"content-type": content_type} if body is not None else {}
    if token:
        headers["authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if content_type == "application/json" and body is not None else body
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read() or b"null")


token = call("POST", "/auth/login", {"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]})["access_token"]

boundary = uuid.uuid4().hex
parts = []
for path in FILES:
    name = os.path.basename(path)
    kind = "application/pdf" if name.endswith(".pdf") else "text/plain"
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{name}"\r\nContent-Type: {kind}\r\n\r\n'.encode()
        + open(path, "rb").read() + b"\r\n"
    )
body = b"".join(parts) + f"--{boundary}--\r\n".encode()
t = time.time()
uploaded = call("POST", "/files", body, token, f"multipart/form-data; boundary={boundary}")
report["uploaded"] = [f["path"] for f in uploaded]

for _ in range(120):
    states = [call("GET", f"/files/{f['id']}/index-status", token=token)["index_status"] for f in uploaded]
    if all(s in ("completed", "failed") for s in states):
        break
    time.sleep(2)
report["index_status"] = states
report["index_seconds"] = round(time.time() - t, 1)

t = time.time()
answer = call("POST", "/chat", {"query": QUESTION}, token)
report["chat_seconds"] = round(time.time() - t, 1)
report["question"] = QUESTION
report["answer"] = answer["answer"]
report["refused"] = answer["refused"]
report["citations"] = [{"title": c.get("title"), "heading": c.get("heading")} for c in answer["citations"]]
report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S %z")
print(json.dumps(report, indent=2))
