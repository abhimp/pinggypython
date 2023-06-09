import paramiko
import threading
import socket
import json
import time
import pinggy.fileno as fileno
import queue

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
        self.rfd, wfd = None, None
        self.acceptQueue = queue.Queue()
    
    def _connectSocket(self):
        sock = socket.socket(type = socket.SOCK_STREAM)
        sock.connect((self.server,self.port))
        return sock
    
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
    
    def _acceptChan(self, chan, fromAddr, toAddr):
        print("New channel", chan, " from: ", fromAddr, " to: ", toAddr)
        if chan is None:
            print(self.transport.get_exception())
            return
        self.acceptQueue.put(chan)
        self.wfd.set()
    
    def startLisener(self):
        print("Start listening")
        self.lock.acquire()
        if self.forwardingStarted:
            return
        try:
            self.transport.request_port_forward("localhost:4000", 0, self._acceptChan)
            self.forwardingStarted = True
            self._fetchUrls()

            self.rfd, self.wfd = fileno.getInfoPipe()
            print(self.urls)
        finally:
            self.lock.release()

    def bind(self, address):
        pass

    def listen(self):
        self.startLisener()

    def _accept(self):
        while True:
            chan = self.transport.accept()
            print("Accepted a connection: ", chan)
            if chan is None:
                print(self.transport.get_exception())
                continue
            self.acceptQueue.put(chan)
            self.wfd.set()

    def fileno(self):
        print("Requested for file no")
        self.lock.acquire()
        try:
            if self.rfd is None:
                self.rfd, self.wfd = fileno.getInfoPipe()
                # x = threading.Thread(target=self._accept, args=())
                # x.start()
            return self.rfd.fileno()
        finally:
            self.lock.release()

    def accept(self):
        print("call accept")
        self.lock.acquire()
        try:
            chan = self.acceptQueue.get()
            self.rfd.clear()
            return chan
        finally:
            self.lock.release()

