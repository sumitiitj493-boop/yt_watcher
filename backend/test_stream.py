import urllib.request
req = urllib.request.Request('http://127.0.0.1:8000/api/stream/G-6.%20Depth-First%20Search%20(DFS)%20%EF%BD%9C%20C%2B%2B%20and%20Java%20%EF%BD%9C%20Traversal%20Technique%20in%20Graphs%20(Qzf1a--rhp8).mp4')
req.add_header('Range', 'bytes=0-100')
try:
    r = urllib.request.urlopen(req)
    print(r.getcode())
except Exception as e:
    print(e)
