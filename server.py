import socket

HOST = '0.0.0.0'  #listen on all network interfaces
PORT = 65432      #a safe port above 1024

print(f"[Server] Starting on port {PORT}...")
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print("[Server] Waiting for a client to connect...")
    conn, addr = server_socket.accept()
    print(f"[Server] Connected to {addr}")
    with conn:
        while True:
            data = conn.recv(1024)
            if not data:
                break  #client disconnected
            message = data.decode('utf-8')
            print(f"[Server] Received: {message}")
            # Send a confirmation back to the client
            conn.sendall(b"Server says: Message received!")

    print("[Server] Client disconnected.")