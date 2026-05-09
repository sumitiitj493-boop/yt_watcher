#!/usr/bin/env python3
import http.server
import socketserver
import os
import urllib.request
import urllib.error
from pathlib import Path
import json

class SPAProxyHandler(http.server.SimpleHTTPRequestHandler):
    """Serve SPA with /api proxy to backend"""
    
    def do_GET(self):
        # If it's an API call, proxy to backend
        if self.path.startswith('/api/'):
            return self.proxy_to_backend()
        
        # If it's a file that exists, serve it
        if self.path.startswith('/') and '.' in self.path.split('/')[-1]:
            return super().do_GET()
        
        # For any other route, serve index.html (SPA)
        self.path = '/index.html'
        return super().do_GET()
    
    def do_POST(self):
        # Proxy POST requests to backend
        if self.path.startswith('/api/'):
            return self.proxy_to_backend()
        return self.send_error(404)
    
    def proxy_to_backend(self):
        """Forward API requests to backend on localhost:8000"""
        backend_url = f'http://localhost:8000{self.path}'
        
        try:
            # Get request body if POST
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None
            
            # Create request to backend
            req = urllib.request.Request(
                backend_url,
                data=body,
                headers={k: v for k, v in self.headers.items() if k.lower() not in ['host', 'content-length']}
            )
            req.get_method = lambda: self.command
            
            # Forward request
            response = urllib.request.urlopen(req, timeout=30)
            
            # Send response back to client
            self.send_response(response.status)
            for header, value in response.headers.items():
                if header.lower() not in ['content-encoding']:  # Skip encoding headers
                    self.send_header(header, value)
            self.end_headers()
            
            # Copy response body
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)
                    
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'detail': str(e.reason)}).encode())
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'detail': f'Backend unavailable: {str(e)}'}).encode())

if __name__ == '__main__':
    # Change to dist directory
    os.chdir(Path(__file__).parent / 'frontend' / 'dist')
    
    PORT = 8080
    Handler = SPAProxyHandler
    
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"Serving SPA frontend at http://0.0.0.0:{PORT}")
        print(f"Proxying /api/* to http://localhost:8000")
        print(f"Static files from: {os.getcwd()}")
        httpd.serve_forever()

