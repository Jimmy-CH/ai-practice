import requests

BASE = "http://127.0.0.1:8000"

# 健康检查
print(requests.get(f"{BASE}/health").json())

# 上传文件
with open("test.txt", "rb") as f:
    print(requests.post(f"{BASE}/upload", files={"file": f}).json())

# 问答
print(requests.post(f"{BASE}/v1/ask", json={"question": "你好"}).json())
