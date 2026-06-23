import socket
import threading
import time
import sys
import ssl
import queue

HOST = '127.0.0.1'
PORT = 65432

def create_ssl_socket():
    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context.wrap_socket(raw_sock, server_hostname=HOST)

def recv_exact(client_socket, size):
    data = b''
    while len(data) < size:
        try:
            chunk = client_socket.recv(size - len(data))
            if not chunk:
                return None
            data += chunk
        except (ConnectionError, socket.timeout):
            return None
    return data

def send_message(client_socket, message):
    try:
        msg_bytes = message.encode('utf-8')
        header = len(msg_bytes).to_bytes(4, 'big')
        client_socket.sendall(header + msg_bytes)
        return True
    except (ConnectionError, BrokenPipeError, socket.error):
        return False

def receive_messages(client_socket, msg_queue, stop_flag):
    """Background thread: listens for messages and puts them in a queue."""
    while not stop_flag.is_set():
        try:
            header = recv_exact(client_socket, 4)
            if header is None:
                msg_queue.put("[Server] Disconnected.")
                stop_flag.set()
                break
            
            msg_len = int.from_bytes(header, 'big')
            msg_bytes = recv_exact(client_socket, msg_len)
            if msg_bytes is None:
                msg_queue.put("[Server] Disconnected.")
                stop_flag.set()
                break
            
            message = msg_bytes.decode('utf-8')
            msg_queue.put(message)
            
        except (UnicodeDecodeError, ValueError):
            continue
        except Exception as e:
            msg_queue.put(f"[Client] Error: {type(e).__name__}: {e}")
            stop_flag.set()
            break

def flush_messages(msg_queue):
    """Print all pending messages from the queue."""
    while not msg_queue.empty():
        try:
            msg = msg_queue.get_nowait()
            print(f"\n{msg}")
        except queue.Empty:
            break

def connect_with_retry(stop_flag):
    delay = 1
    while not stop_flag.is_set():
        try:
            ssl_sock = create_ssl_socket()
            ssl_sock.settimeout(5.0)
            ssl_sock.connect((HOST, PORT))
            ssl_sock.settimeout(None)
            return ssl_sock
        except (ConnectionError, socket.timeout, OSError):
            print(f"[Client] Connection failed. Retrying in {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, 60)
        except KeyboardInterrupt:
            stop_flag.set()
            return None
    return None

def start_client():
    nickname = input("Enter your nickname: ").strip()
    if not nickname:
        nickname = "Anonymous"
    
    stop_flag = threading.Event()
    msg_queue = queue.Queue()
    
    print("[Client] Connecting to server (TLS)...")
    client_socket = connect_with_retry(stop_flag)
    if client_socket is None:
        return
    
    if not send_message(client_socket, nickname):
        print("[Client] Failed to send nickname. Server might be down.")
        return
    
    # Start the background receiver thread
    receiver = threading.Thread(
        target=receive_messages, 
        args=(client_socket, msg_queue, stop_flag),
        daemon=True
    )
    receiver.start()
    
    print(f"[Client] Connected as '{nickname}'!")
    print("Commands: /users, /msg <user> <msg>, /quit, /join, /rooms")
    print("Type your messages below.\n")
    
    # Main thread handles sending + message display
    while not stop_flag.is_set():
        # Step 1: Print any pending messages BEFORE showing the prompt
        flush_messages(msg_queue)
        
        # Step 2: Show the prompt and wait for input
        try:
            message = input("You: ")
            if message.lower() == '/quit':
                break
            
            if message.strip():
                if not send_message(client_socket, message):
                    print("[Client] Failed to send. Reconnecting...")
                    client_socket.close()
                    client_socket = connect_with_retry(stop_flag)
                    if not client_socket:
                        break
                    send_message(client_socket, nickname)
                    print("[Client] Reconnected securely!")
        except KeyboardInterrupt:
            break
        except (ConnectionError, BrokenPipeError):
            print("\n[Client] Connection lost. Reconnecting...")
            client_socket.close()
            client_socket = connect_with_retry(stop_flag)
            if not client_socket:
                break
            send_message(client_socket, nickname)
            print("[Client] Reconnected securely!")
    
    stop_flag.set()
    client_socket.close()
    print("\n[Client] Disconnected.")

if __name__ == "__main__":
    start_client()