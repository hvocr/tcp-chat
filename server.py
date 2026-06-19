import socket
import threading
import time

HOST = '0.0.0.0'
PORT = 65432

nicknames = {}

def recv_exact(client_socket, size):
    """Receive exactly `size` bytes from the socket. Returns None if connection fails."""
    data = b''
    while len(data) < size:
        try:
            chunk = client_socket.recv(size - len(data))
            if not chunk:
                return None
            data += chunk
        except:
            return None
    return data

def send_message(client_socket, message):
    """Send a length-prefixed message."""
    try:
        msg_bytes = message.encode('utf-8')
        header = len(msg_bytes).to_bytes(4, 'big')
        client_socket.sendall(header + msg_bytes)
        return True
    except:
        return False

def broadcast(message, sender_socket=None):
    """Send a message to every connected client except the sender."""
    for client in list(nicknames.keys()):
        if client != sender_socket:
            send_message(client, message)

def remove_client(client_socket):
    """Clean up a disconnected client."""
    if client_socket in nicknames:
        nickname = nicknames[client_socket]
        del nicknames[client_socket]
        client_socket.close()
        print(f"[Server] {nickname} removed.")
        broadcast(f"[Server] {nickname} has left the chat.")

def handle_client(client_socket, addr):
    """Runs in a separate thread for each client."""
    print(f"[Server] {addr} connected. Waiting for nickname...")
    
    # 1. Receive nickname (first message)
    nickname_bytes = recv_exact(client_socket, 4)
    if not nickname_bytes:
        client_socket.close()
        return
    
    nickname_len = int.from_bytes(nickname_bytes, 'big')
    nickname_data = recv_exact(client_socket, nickname_len)
    if not nickname_data:
        client_socket.close()
        return
    
    nickname = nickname_data.decode('utf-8').strip()
    if not nickname:
        client_socket.close()
        return
    
    # 2. Store the nickname
    nicknames[client_socket] = nickname
    print(f"[Server] {nickname} ({addr}) joined!")
    broadcast(f"[Server] {nickname} has joined the chat!", client_socket)
    
    # 3. Main message loop (now with length-prefixing!)
    while True:
        # Read the 4-byte header
        header = recv_exact(client_socket, 4)
        if header is None:
            break
        
        msg_len = int.from_bytes(header, 'big')
        msg_bytes = recv_exact(client_socket, msg_len)
        if msg_bytes is None:
            break
        
        raw_message = msg_bytes.decode('utf-8').strip()
        if not raw_message:
            continue
        
        # --- COMMAND PARSING ---
        if raw_message.startswith('/'):
            parts = raw_message.split(' ', 2)
            command = parts[0].lower()
            
            if command == '/users':
                user_list = ", ".join(nicknames.values())
                send_message(client_socket, f"[Server] Active users: {user_list}")
                continue
            
            elif command == '/msg' and len(parts) >= 3:
                target = parts[1]
                private_msg = parts[2]
                found = False
                for sock, name in nicknames.items():
                    if name.lower() == target.lower():
                        send_message(sock, f"[Private from {nickname}]: {private_msg}")
                        send_message(client_socket, f"[Private to {target}]: {private_msg}")
                        found = True
                        break
                if not found:
                    send_message(client_socket, f"[Server] User '{target}' not found.")
                continue
            else:
                send_message(client_socket, f"[Server] Unknown command. Available: /users, /msg <user> <message>")
                continue
        
        # --- NORMAL BROADCAST ---
        print(f"[Server] {nickname} says: {raw_message}")
        broadcast(f"{nickname}: {raw_message}", client_socket)
    
    # 4. Clean up
    remove_client(client_socket)

def start_server():
    print(f"[Server] Starting on port {PORT}...")
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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