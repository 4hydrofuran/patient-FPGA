import os,json,socket,struct,base64
class Bidi:
    def __init__(self):
        self.s=socket.create_connection(('127.0.0.1',9222),timeout=12);self.i=0
        key=base64.b64encode(os.urandom(16)).decode()
        request='GET /session HTTP/1.1\r\nHost: 127.0.0.1:9222\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: '+key+'\r\nSec-WebSocket-Version: 13\r\n\r\n'
        self.s.sendall(request.encode());head=b''
        while not head.endswith(b'\r\n\r\n'):head+=self.exact(1)
        if b' 101 ' not in head:raise RuntimeError('WebSocket upgrade failed: '+head.decode())
    def exact(self,n):
        data=b''
        while len(data)<n:
            p=self.s.recv(n-len(data))
            if not p:raise EOFError('Browser connection closed')
            data+=p
        return data
    def send(self,payload,opcode=1):
        key=os.urandom(4);n=len(payload)
        head=bytes([128|opcode,128|n]) if n<126 else bytes([128|opcode,128|126])+struct.pack('!H',n) if n<65536 else bytes([128|opcode,128|127])+struct.pack('!Q',n)
        self.s.sendall(head+key+bytes(x^key[i%4] for i,x in enumerate(payload)))
    def receive(self):
        parts=[]
        while True:
            a,b=self.exact(2);n=b&127
            if n==126:n=struct.unpack('!H',self.exact(2))[0]
            elif n==127:n=struct.unpack('!Q',self.exact(8))[0]
            mask=self.exact(4) if b&128 else None;p=self.exact(n)
            if mask:p=bytes(x^mask[i%4] for i,x in enumerate(p))
            op=a&15
            if op==8:raise EOFError('WebSocket close')
            if op==9:self.send(p,10);continue
            parts.append(p)
            if a&128:return json.loads(b''.join(parts))
    def call(self,method,params):
        self.i+=1;self.send(json.dumps(dict(id=self.i,method=method,params=params)).encode())
        while True:
            r=self.receive()
            if r.get('id')!=self.i:continue
            if r.get('type')=='error':raise RuntimeError(json.dumps(r))
            return r['result']
