import socket

HOST = '127.0.0.1'  #localhost
PORT = 65432

print(f"[Client] Connecting to {HOST}:{PORT}...")
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
    client_socket.connect((HOST, PORT))
    message = "Hello from the client!"
    print(f"[Client] Sending: {message}")
    client_socket.sendall(message.encode('utf-8'))
    response = client_socket.recv(1024)
    print(f"[Client] Server replied: {response.decode('utf-8')}")
print("[Client] Disconnected.")