import paramiko
import threading
import socket
import json
import time
import pinggy.fileno as fileno
import queue
import select

HOST_KEY="SHA256:nFd5rfJMGuZXvfeRzJ/BtT3TfksAxTWMajcrHRcI7AM"

URL_REQUEST = "\r\n".join([ "GET /urls HTTP/1.0",
                            "Host: pinggy.io",
                            "User-Agent: PinggyPythonSdk",
                            ""
                        ])

class Connection():
    def __init__(self, token = None, mode=None, server="a.pinggy.io", port=443):
        self.transport = None
        self.token = token
        self.mode = mode if mode in ["http", "tcp", "tls"] else ""
        self.server = server
        self.port = port
        self.lock = threading.Lock()
        self.connected = False
        self.forwardingStarted = False
        self.urls = []
        self.transportThread = None
        self.listeningSocket = None
        self.transportThreadLock = threading.Lock()
    
    def _connectSocket(self):
        sock = socket.socket(type = socket.SOCK_STREAM)
        sock.connect((self.server,self.port))
        return sock

    def close(self):
        if self.transport is not None:
            self.transport.close()
            self.transport = None
    
    def connect(self):
        self.lock.acquire()
        try:
            self.transport = paramiko.Transport(self._connectSocket())
            
            user = "auth"
            if self.mode is not None and self.mode != "":
                user = self.mode + "+" + user
            if self.token is not None and self.token != "":
                user = self.token + "+" + user
            self.transport.connect(username=user, password="nopass")
            self.connected = True
        finally:
            self.lock.release()
    
    def _fetchUrls(self):
        if not self.forwardingStarted:
            return
        chan = self.transport.open_channel("direct-tcpip", ("localhost",4300), ("localhost", 4300))
        chan.sendall(URL_REQUEST.encode())
        rcv = b""
        reqLine = ""
        headers = []
        bodyStarted = False
        cLen = 0
        while True:
            r = chan.recv(1024)
            # print(r)
            if len(r) == 0:
                break
            # print(r)
            rcv += r
            while not bodyStarted:
                p = rcv.find(b"\n")
                if p < 0:
                    break
                h = rcv[:p].strip(b"\r")
                rcv = rcv[p+1:]
                h = h.decode(encoding="utf8")
                if h == "":
                    bodyStarted = True
                    break
                if reqLine == "":
                    reqLine = h
                else:
                    header = h.split(":",1)
                    headers.append(header)
                    # print(header)
                    if header[0].upper() == "CONTENT-LENGTH":
                        cLen = int(header[1])
            # print(cLen, len(rcv))
            if bodyStarted and len(rcv) == cLen:
                break
        if len(rcv) == 0:
            raise Exception("No Body")
        dt = json.loads(rcv)
        if "urls" in dt:
            self.urls = dt["urls"]
    
    # def _acceptChan(self, chan, fromAddr, toAddr):
    #     print("New channel", chan, " from: ", fromAddr, " to: ", toAddr)
    #     if chan is None:
    #         print(self.transport.get_exception())
    #         return
    #     self.acceptQueue.put(chan)
    #     self.wfd.set()

    def copy(self, sock1, sock2):
        try:
            while True:
                dt = sock1.recv(2048)
                # print(f"recv {len(dt)} from {sock1} to {sock2}")
                if len(dt) == 0:
                    break
                sock2.sendall(dt)
        finally:
            # print(f"closing {sock1}, {sock2}")
            sock1.close()
            sock2.close()

    def _acceptLoop(self, serverAddr):
        # print(f"waiting for connection at {self.transport}")
        while True:
            chan = self.transport.accept()
            if chan is None:
                return False #the transport is closed
                #do stuff
            # print(f"chan: {chan} recved")
            sock = socket.socket()
            try:
                sock.connect(serverAddr)
                # print(f"chan: {chan} and sock: {sock} connected")
                threading.Thread(target=self.copy, args=(sock, chan,)).start()
                threading.Thread(target=self.copy, args=(chan, sock,)).start()
            except:
                sock.close()
                chan.close()
        return True
    
    def startForwarding(self, serverAddr):
        # print("Start listening")
        # print(f"forwarding to http://{serverAddr[0]}:{serverAddr[1]}")
        self.lock.acquire()
        if self.forwardingStarted:
            return
        try:
            self.transport.request_port_forward(f"{serverAddr[0]}:{serverAddr[1]}", 0)
            self.forwardingStarted = True
            self._fetchUrls()
            self.transportThread = threading.Thread(target=self._acceptLoop, args=(serverAddr,))
            self.transportThread.start()
            # self.rfd, self.wfd = fileno.getInfoPipe()
            # print(self.urls)

        finally:
            self.lock.release()

    def wait(self):
        self.transportThreadLock.acquire()
        try:
            if self.transportThread is not None:
                self.transportThread.join()
                self.transportThread = None
        except KeyboardInterrupt:
            pass
        finally:
            self.transportThreadLock.release()
    
    def startListening(self, port=0, host="localhost"):
        self.lock.acquire()
        if self.listeningSocket is not None:
            return self.listeningSocket
        try:
            sock = socket.create_server((host, port))
            self.listeningSocket = sock
        except Exception as e:
            print(e)
        finally:
            self.lock.release()
        
        if self.listeningSocket is not None:
            self.startForwarding(self.listeningSocket.getsockname())
        
        return self.listeningSocket

    def getUrls(self):
        return self.urls