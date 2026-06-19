import socket
import threading

HOST = '0.0.0.0'
PORT = 65432

# Dictionary: {client_socket: nickname}
nicknames = {}

def broadcast(message, sender_socket=None):
    """Send a message to every connected client except the sender."""
    for client in list(nicknames.keys()):
        if client != sender_socket:
            try:
                client.send(message.encode('utf-8'))
            except:
                remove_client(client)

def remove_client(client_socket):
    """Clean up a disconnected client."""
    if client_socket in nicknames:
        nickname = nicknames[client_socket]
        del nicknames[client_socket]
        client_socket.close()
        print(f"[Server] {nickname} removed from active clients.")
        broadcast(f"[Server] {nickname} has left the chat.")

def handle_client(client_socket, addr):
    """Runs in a separate thread for each client."""
    print(f"[Server] {addr} connected. Waiting for nickname...")
    
    # STEP 1: Receive the nickname (first message is treated as nickname)
    try:
        nickname = client_socket.recv(1024).decode('utf-8').strip()
        if not nickname:
            remove_client(client_socket)
            return
    except:
        remove_client(client_socket)
        return
    
    # STEP 2: Store the nickname
    nicknames[client_socket] = nickname
    print(f"[Server] {nickname} ({addr}) has joined the chat!")
    broadcast(f"[Server] {nickname} has joined the chat!", client_socket)
    
    # STEP 3: Listen for messages from this client
    while True:
        try:
            message = client_socket.recv(1024).decode('utf-8').strip()
            if not message:
                break
            print(f"[Server] {nickname} says: {message}")
            broadcast(f"{nickname}: {message}", client_socket)
        except:
            break
    
    # STEP 4: Clean up
    remove_client(client_socket)

def start_server():
    print(f"[Server] Starting on port {PORT}...")
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print("[Server] Waiting for clients...")
    
    while True:
        client_socket, addr = server_socket.accept()
        thread = threading.Thread(target=handle_client, args=(client_socket, addr))
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    start_server()