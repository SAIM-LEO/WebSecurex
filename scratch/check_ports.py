import socket
s = socket.socket(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
try:
    s.connect(('127.0.0.1', 8000))
    print("Port 8000 is OPEN")
except:
    print("Port 8000 is CLOSED")
finally:
    s.close()

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.connect(('127.0.0.1', 3000))
    print("Port 3000 is OPEN")
except:
    print("Port 3000 is CLOSED")
finally:
    s.close()
