import socket
import threading
import time
import msvcrt
import sys

HOST = '127.0.0.1'
PORT = 65432

def recv_exact(client_socket, size):
    """Receive exactly `size` bytes from the socket."""
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

def receive_messages(client_socket, message_queue, connected_flag):
    """Background thread: listens for messages and puts them in a queue."""
    while connected_flag[0]:
        try:
            header = recv_exact(client_socket, 4)
            if header is None:
                message_queue.append("[Server] Disconnected.")
                connected_flag[0] = False
                break
            msg_len = int.from_bytes(header, 'big')
            msg_bytes = recv_exact(client_socket, msg_len)
            if msg_bytes is None:
                message_queue.append("[Server] Disconnected.")
                connected_flag[0] = False
                break
            
            message = msg_bytes.decode('utf-8')
            message_queue.append(message)
            
        except Exception as e:
            message_queue.append("[Server] Disconnected.")
            connected_flag[0] = False
            break

def connect_with_retry():
    """Attempt to connect with exponential backoff."""
    delay = 1
    while True:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5.0)
            client_socket.connect((HOST, PORT))
            client_socket.settimeout(None)
            return client_socket
        except:
            print(f"[Client] Connection failed. Retrying in {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, 60)

def start_client():
    # 1. Get nickname
    nickname = input("Enter your nickname: ").strip()
    if not nickname:
        nickname = "Anonymous"
    
    # 2. Connect
    print("[Client] Connecting to server...")
    client_socket = connect_with_retry()
    print("[Client] Connected!")
    
    # 3. Send nickname
    if not send_message(client_socket, nickname):
        print("[Client] Failed to send nickname. Exiting.")
        return
    
    print(f"[Client] Connected as '{nickname}'!")
    print("Commands: /users, /msg <nickname> <message>, /quit")
    print("Type your messages below. Press Enter to send.\n")
    
    # 4. Message queue and connection flag
    message_queue = []
    connected_flag = [True]
    
    # 5. Start background listener
    receive_thread = threading.Thread(
        target=receive_messages, 
        args=(client_socket, message_queue, connected_flag), 
        daemon=True
    )
    receive_thread.start()
    
    # 6. Non-blocking input loop
    input_buffer = ""
    prompt = "You: "
    print(prompt, end="", flush=True)
    
    while True:
        # --- CHECK FOR DISCONNECTION ---
        if not connected_flag[0]:
            print("\n[Client] Lost connection. Reconnecting...")
            client_socket.close()
            client_socket = connect_with_retry()
            print("[Client] Reconnected!")
            send_message(client_socket, nickname)
            connected_flag[0] = True
            message_queue.clear()  # <--- FIX: Clear stale messages
            
            # Restart receiver thread
            receive_thread = threading.Thread(
                target=receive_messages, 
                args=(client_socket, message_queue, connected_flag), 
                daemon=True
            )
            receive_thread.start()
            # Re-print prompt
            print(prompt, end="", flush=True)
            continue
        
        # --- CHECK FOR INCOMING MESSAGES ---
        while message_queue:
            msg = message_queue.pop(0)
            # Clear the current line, print message, re-print prompt
            sys.stdout.write("\r" + " " * 80 + "\r")
            print(msg)
            sys.stdout.write(prompt + input_buffer)
            sys.stdout.flush()
        
        # --- CHECK FOR KEYBOARD INPUT ---
        if msvcrt.kbhit():
            char = msvcrt.getch()
            
            if char == b'\r':  # Enter key
                sys.stdout.write("\n")
                sys.stdout.flush()
                if input_buffer.lower() == '/quit':
                    break
                if input_buffer.strip():
                    if not send_message(client_socket, input_buffer):
                        print("\n[Client] Failed to send. Reconnecting...")
                        client_socket.close()
                        client_socket = connect_with_retry()
                        send_message(client_socket, nickname)
                        connected_flag[0] = True
                        message_queue.clear()  # <--- FIX: Clear stale messages here too
                        receive_thread = threading.Thread(
                            target=receive_messages, 
                            args=(client_socket, message_queue, connected_flag), 
                            daemon=True
                        )
                        receive_thread.start()
                        print("[Client] Reconnected!")
                input_buffer = ""
                sys.stdout.write(prompt + input_buffer)
                sys.stdout.flush()
                
            elif char == b'\x08':  # Backspace
                if input_buffer:
                    input_buffer = input_buffer[:-1]
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
                    
            elif char == b'\x03':  # Ctrl+C
                break
                
            else:
                # Regular character
                try:
                    char_str = char.decode('utf-8')
                    if char_str.isprintable():
                        input_buffer += char_str
                        sys.stdout.write(char_str)
                        sys.stdout.flush()
                except:
                    pass
        
        # Small sleep to prevent CPU spinning
        time.sleep(0.01)
    
    client_socket.close()
    print("\n[Client] Disconnected.")

if __name__ == "__main__":
    start_client()