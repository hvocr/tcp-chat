import socket
import threading

HOST = '0.0.0.0'
PORT = 65432

clients = []

def broadcast(message, sender_socket=None):
    """Send a message to every connected client except the sender."""
    for client in clients:
        if client != sender_socket:
            try:
                client.send(message.encode('utf-8'))
            except:
                remove_client(client)

def remove_client(client_socket):
    """Remove a client socket from the global list and close it."""
    if client_socket in clients:
        clients.remove(client_socket)
        client_socket.close()

def handle_client(client_socket, addr):
    """Runs in a separate thread for each client."""
    print(f"[Server] {addr} connected.")
    broadcast(f"[Server] A new user has joined the chat!", client_socket)
    
    while True:
        try:
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                break
            print(f"[Server] {addr} says: {message}")
            broadcast(f"{addr}: {message}", client_socket)
        except:
            break
    
    print(f"[Server] {addr} disconnected.")
    broadcast(f"[Server] A user has left the chat.", client_socket)
    remove_client(client_socket)

def start_server():
    print(f"[Server] Starting on port {PORT}...")
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print("[Server] Waiting for clients...")
    
    while True:
        client_socket, addr = server_socket.accept()
        clients.append(client_socket)
        thread = threading.Thread(target=handle_client, args=(client_socket, addr))
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    start_server()