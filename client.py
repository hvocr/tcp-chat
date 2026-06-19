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
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((HOST, PORT))
    except:
        print("[Client] Could not connect to server. Make sure it's running.")
        return
    
    print("[Client] Connected to chat server! Type your messages below.")
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
        try:
            client_socket.send(message.encode('utf-8'))
        except:
            print("[Client] Connection lost.")
            break
    
    client_socket.close()

if __name__ == "__main__":
    start_client()