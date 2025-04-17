import socket

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 12345))
    print('Port 12345 is available')
    sock.close()
except Exception as e:
    print(f'Port 12345 is in use: {e}') 