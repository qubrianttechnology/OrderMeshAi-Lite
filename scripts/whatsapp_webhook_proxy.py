"""Loopback proxy exposing only the existing WhatsApp webhook to a test tunnel."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import httpx
import json

MAX_BODY = 1024 * 1024

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Verification query strings contain a secret.

    def do_GET(self):
        self.forward()

    def do_POST(self):
        self.forward()

    def forward(self):
        parsed = urlsplit(self.path)
        if parsed.path != '/webhooks/whatsapp' or parsed.scheme or parsed.netloc:
            self.send_error(404)
            return
        if self.headers.get('Transfer-Encoding'):
            self.send_error(400)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            self.send_error(400)
            return
        if length < 0 or length > MAX_BODY:
            self.send_error(413)
            return
        self.connection.settimeout(15)
        body = self.rfile.read(length)
        headers = {k: self.headers[k] for k in ('Content-Type', 'X-Hub-Signature-256') if k in self.headers}
        try:
            with httpx.Client(timeout=25, trust_env=False, follow_redirects=False) as client:
                response = client.request(self.command, 'http://127.0.0.1:8000' + self.path, content=body, headers=headers)
            if self.command == 'POST' and response.status_code == 404:
                try:
                    payload = json.loads(body)
                    ids = [change.get('value', {}).get('metadata', {}).get('phone_number_id') for entry in payload.get('entry', []) for change in entry.get('changes', [])]
                    safe_ids = [value for value in ids if isinstance(value, str) and value.isdigit() and len(value) <= 128]
                    print(json.dumps({'unregistered_phone_ids': safe_ids}), flush=True)
                except (ValueError, TypeError, AttributeError):
                    pass
            self.send_response(response.status_code)
            self.send_header('Content-Type', response.headers.get('Content-Type', 'text/plain'))
            self.send_header('Content-Length', str(len(response.content)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(response.content)
        except httpx.HTTPError:
            self.send_error(502)

if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8011), Handler).serve_forever()
