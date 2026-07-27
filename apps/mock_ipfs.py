from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import hashlib
import cgi
import threading

storage = {}

class IPFSHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.startswith("/api/v0/add"):
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST'}
            )
            file_data = form['file'].file.read()
            # Generate a pseudo CID
            cid = "Qm" + hashlib.sha256(file_data).hexdigest()[:44]
            storage[cid] = file_data
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {"Name": "manifest.json", "Hash": cid, "Size": str(len(file_data))}
            self.wfile.write(json.dumps(response).encode())
            
        elif self.path.startswith("/api/v0/cat"):
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            cid = query.get("arg", [""])[0]
            
            if cid in storage:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(storage[cid])
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
            
    def log_message(self, format, *args):
        pass # suppress logs for clean output

def run_mock_ipfs():
    server = HTTPServer(('127.0.0.1', 5001), IPFSHandler)
    print("Mock IPFS Node running on http://127.0.0.1:5001")
    server.serve_forever()

if __name__ == '__main__':
    run_mock_ipfs()
