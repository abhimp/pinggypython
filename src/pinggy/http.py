from pinggy import Connection
import http.server as httpServer
import threading

def serveOnThread(httpServer):
    httpServer.serve_forever()

def serveFile():
    conn = Connection()
    conn.connect()
    serverAddress = ('', 0) # Use any available port
    hServer = httpServer.HTTPServer(serverAddress, httpServer.SimpleHTTPRequestHandler)
    hServer.socket = conn.startListening()
    try:

        # Start the server and keep it running
        t = threading.Thread(target=serveOnThread, args=(hServer,))
        t.start()
        print("You current files are served via following urls")
        for u in conn.getUrls():
            print(f"\t{u}")
        conn.wait()
    except Exception as e:
        print("!!!!Exception")
        print(e)
    finally:
        hServer.shutdown()
        conn.close()

if __name__ == "__main__":
    serveFile()