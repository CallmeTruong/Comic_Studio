import requests

resp = requests.post("http://localhost:8000/api/generate", json={
    "prompt": "Test dog",
    "layoutStyle": "manga",
    "mangaLayout": "style1",
    "steps": 20,
    "guidance": 7.5,
    "lora": "comicBabes_v2",
    "negativePrompt": "",
    "seed": ""
})

print(resp.status_code)
if resp.status_code != 200:
    print(resp.text)
else:
    for line in resp.iter_lines():
        print(line.decode('utf-8'))
