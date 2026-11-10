from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import hashlib
from urllib.parse import urlparse, parse_qs

storage = {}

class IPFSHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.startswith("/api/v0/add"):
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            # Extract payload bytes from multipart or raw JSON
            file_data = b""
            if b"Content-Type: application/json" in body or b"filename=" in body:
                # Find payload boundary
                header_end = body.find(b"\r\n\r\n")
                if header_end != -1:
                    tail = body[header_end + 4:]
                    # Strip closing multipart boundary
                    boundary_idx = tail.rfind(b"\r\n--")
                    if boundary_idx != -1:
                        file_data = tail[:boundary_idx]
                    else:
                        file_data = tail
                else:
                    file_data = body
            else:
                file_data = body

            # Generate deterministic pseudo CID
            cid = "Qm" + hashlib.sha256(file_data).hexdigest()[:44]
            storage[cid] = file_data
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {"Name": "manifest.json", "Hash": cid, "Size": str(len(file_data))}
            self.wfile.write(json.dumps(response).encode())
            
        elif self.path.startswith("/api/v0/cat"):
            query = parse_qs(urlparse(self.path).query)
            cid = query.get("arg", [""])[0]
            if cid.startswith("ipfs://"):
                cid = cid.replace("ipfs://", "")
            
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

    def do_GET(self):
        if self.path.startswith("/ipfs/"):
            cid = self.path.replace("/ipfs/", "")
            if cid in storage:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(storage[cid])
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "IPFS mock active"}).encode())

    def log_message(self, format, *args):
        pass # Clean output

def run_mock_ipfs():
    server = HTTPServer(('127.0.0.1', 5001), IPFSHandler)
    print("Mock IPFS Node running on http://127.0.0.1:5001")
    server.serve_forever()

if __name__ == '__main__':
    run_mock_ipfs()
