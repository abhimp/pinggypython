from pinggy import Connection
import http.server as httpServer

def serve_on_custom_socket():
    conn = Connection(server="t.pinggy.io")
    conn.connect()
    conn.listen()
    server_address = ('', 8000)  # Use any available port
    http_server = httpServer.HTTPServer(server_address, httpServer.SimpleHTTPRequestHandler)
    http_server.socket = conn

    # Start the server and keep it running
    http_server.serve_forever()

if __name__ == "__main__":
    serve_on_custom_socket()