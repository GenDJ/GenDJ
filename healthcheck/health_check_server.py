import http.server
import socketserver

class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/readyz":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")

def run_server():
    try:
        with socketserver.TCPServer(("", 8080), HealthCheckHandler) as httpd:
            print("Health check server running at port 8080") # This print will go to container logs
            httpd.serve_forever()
    except Exception as e:
        print(f"Health check server failed: {e}") # This print will go to container logs
        exit(1)

if __name__ == "__main__":
    run_server()