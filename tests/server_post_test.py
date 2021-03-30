from urllib import request
import json

req = request.Request('https://80overland.com/test.php', method="POST")
req.add_header('Content-Type', 'application/json')
data = {
    "hello": "world"
}
data = json.dumps(data)
data = data.encode()
r = request.urlopen(req, data=data)
content = r.read()
print(content)