from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/apply-config':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            print("Received /apply-config:", body.decode())
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Redirect to stdout to make logs visible in terminal
        print(format % args)

if __name__ == '__main__':
    import sys
    host = '127.0.0.1'
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    print(f"Starting test apply-config server on {host}:{port}")
    HTTPServer((host, port), Handler).serve_forever()
