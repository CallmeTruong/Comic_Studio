import requests

resp = requests.post("http://localhost:8000/api/generate", json={
    "prompt": "Test dog",
    "layoutStyle": "manga",
    "mangaLayout": "style1"
})

print(resp.status_code)
for line in resp.iter_lines():
    print(line.decode('utf-8'))
