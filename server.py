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

def send_private(target_nickname, message, sender_socket):
    """Send a private message to a specific user by nickname."""
    # Find the socket that matches the target nickname
    for client_socket, nickname in nicknames.items():
        if nickname.lower() == target_nickname.lower():
            try:
                sender_nick = nicknames[sender_socket]
                client_socket.send(f"[Private from {sender_nick}]: {message}".encode('utf-8'))
                # Also send a confirmation to the sender so they know it was delivered
                sender_socket.send(f"[Private to {target_nickname}]: {message}".encode('utf-8'))
                return True
            except:
                return False
    return False  # Target not found

def remove_client(client_socket):
    """Clean up a disconnected client."""
    if client_socket in nicknames:
        nickname = nicknames[client_socket]
        del nicknames[client_socket]
        client_socket.close()
        print(f"[Server] {nickname} removed from active clients.")
        broadcast(f"[Server] {nickname} has left the chat.")

def get_active_users():
    """Return a comma-separated list of all nicknames."""
    return ", ".join(nicknames.values())

def handle_client(client_socket, addr):
    """Runs in a separate thread for each client."""
    print(f"[Server] {addr} connected. Waiting for nickname...")
    
    # STEP 1: Receive the nickname
    try:
        nickname = client_socket.recv(1024).decode('utf-8').strip()
        if not nickname:
            remove_client(client_socket)
            return
    except:
        remove_client(client_socket)
        return
    
    # Reserve "Server" as a system name (optional)
    if nickname.lower() == "server":
        client_socket.send("You cannot use 'Server' as a nickname.".encode('utf-8'))
        remove_client(client_socket)
        return
    
    nicknames[client_socket] = nickname
    print(f"[Server] {nickname} ({addr}) has joined the chat!")
    broadcast(f"[Server] {nickname} has joined the chat!", client_socket)
    
    # STEP 2: Listen for messages
    while True:
        try:
            raw_message = client_socket.recv(1024).decode('utf-8').strip()
            if not raw_message:
                break
            
            # --- COMMAND PARSING ---
            if raw_message.startswith('/'):
                parts = raw_message.split(' ', 2)  # Max split into 3 parts
                command = parts[0].lower()
                
                if command == '/users':
                    user_list = get_active_users()
                    client_socket.send(f"[Server] Active users: {user_list}".encode('utf-8'))
                    continue
                
                elif command == '/msg' and len(parts) >= 3:
                    target = parts[1]
                    private_msg = parts[2]
                    success = send_private(target, private_msg, client_socket)
                    if not success:
                        client_socket.send(f"[Server] User '{target}' not found.".encode('utf-8'))
                    continue
                
                else:
                    client_socket.send(f"[Server] Unknown command: {command}. Available: /users, /msg <user> <message>".encode('utf-8'))
                    continue
            
            # --- NORMAL BROADCAST ---
            print(f"[Server] {nickname} says: {raw_message}")
            broadcast(f"{nickname}: {raw_message}", client_socket)
            
        except:
            break
    
    # STEP 3: Clean up
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