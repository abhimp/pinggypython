import socket

class InfoPipe():
    def __init__(self):
        self.rd, self.wd = socket.socketpair()
        self._set = False
        self.closed = False
    
    def set(self):
        if self._set or self.closed:
            return
        self._set = True
        self.wd.send(b"*")

    def clear(self):
        if not self._set or self.closed:
            return
        self.rd.recv(1)
        self._set = False

    def fileno(self):
        return self.rd.fileno()
    
    def close(self):
        if self.closed:
            return
        self.rd.close()
        self.wd.close()
        self.closed = True

def getInfoPipe():
    p = InfoPipe()
    return p, p