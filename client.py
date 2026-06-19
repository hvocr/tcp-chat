import socket
import threading

HOST = '127.0.0.1'
PORT = 65432

def receive_messages(client_socket):
    """Background thread: continuously listens for incoming messages."""
    while True:
        try:
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                break
            # \r clears the line so "You: " prompt doesn't get messy
            print(f"\r{message}\nYou: ", end="")
        except:
            print("\n[Client] Disconnected from server.")
            break

def start_client():
    # Ask for nickname BEFORE connecting
    nickname = input("Enter your nickname: ").strip()
    if not nickname:
        nickname = "Anonymous"
    
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((HOST, PORT))
    except:
        print("[Client] Could not connect to server. Make sure it's running.")
        return
    
    # STEP 1: Send the nickname as the VERY FIRST message
    client_socket.send(nickname.encode('utf-8'))
    
    print(f"[Client] Connected as '{nickname}'!")
    print("Type '/quit' to exit.\n")
    
    # Start the background listener thread
    receive_thread = threading.Thread(target=receive_messages, args=(client_socket,))
    receive_thread.daemon = True
    receive_thread.start()
    
    # Main thread handles user input
    while True:
        message = input("You: ")
        if message.lower() == '/quit':
            break
        if message.strip():
            try:
                client_socket.send(message.encode('utf-8'))
            except:
                print("[Client] Connection lost.")
                break
    
    client_socket.close()

if __name__ == "__main__":
    start_client()