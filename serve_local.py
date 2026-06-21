#!/usr/bin/env python3
"""Simple HTTP server for local network access to YT Suite"""
import http.server
import socketserver
import os
from pathlib import Path

class LocalHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Serve index.html for all routes
        if self.path == '/' or self.path == '' or not self.path.startswith('/'):
            self.path = '/local_index.html'
        return super().do_GET()
    
    def end_headers(self):
        # Add CORS headers for local network access
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

if __name__ == '__main__':
    os.chdir(Path(__file__).parent)
    PORT = 8080
    
    with socketserver.TCPServer(("0.0.0.0", PORT), LocalHandler) as httpd:
        print(f"🚀 YT Suite running on:")
        print(f"   Local:   http://localhost:{PORT}/")
        print(f"   Network: http://172.24.224.1:{PORT}/")
        print(f"   Backend: http://172.24.224.1:8000/api")
        print(f"\nOpen http://172.24.224.1:8080/ on your phone (same WiFi)")
        print(f"Press Ctrl+C to stop")
        httpd.serve_forever()
