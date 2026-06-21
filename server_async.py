import asyncio
import sys

HOST = '0.0.0.0'
PORT = 65432

# Dictionary: {writer: nickname}
clients = {}

def send_message(writer, message):
    """Send a length-prefixed message to a specific client."""
    try:
        msg_bytes = message.encode('utf-8')
        header = len(msg_bytes).to_bytes(4, 'big')
        writer.write(header + msg_bytes)
        return True
    except:
        return False

async def broadcast(message, sender_writer=None):
    """Send a message to every connected client except the sender."""
    for writer, nickname in list(clients.items()):
        if writer != sender_writer:
            send_message(writer, message)
            await writer.drain()  # Important: Actually send the bytes

def remove_client(writer):
    """Clean up a disconnected client."""
    if writer in clients:
        nickname = clients[writer]
        del clients[writer]
        writer.close()
        print(f"[Server] {nickname} removed.")
        asyncio.create_task(broadcast(f"[Server] {nickname} has left the chat."))

async def handle_client(reader, writer):
    """Handles a single client connection asynchronously."""
    addr = writer.get_extra_info('peername')
    print(f"[Server] {addr} connected. Waiting for nickname...")

    # 1. Receive nickname (with length-prefix)
    try:
        header = await reader.readexactly(4)
        nickname_len = int.from_bytes(header, 'big')
        nickname_bytes = await reader.readexactly(nickname_len)
        nickname = nickname_bytes.decode('utf-8').strip()
        if not nickname:
            raise Exception("Empty nickname")
    except (asyncio.IncompleteReadError, Exception):
        writer.close()
        return

    # 2. Store the client
    clients[writer] = nickname
    print(f"[Server] {nickname} ({addr}) joined!")
    await broadcast(f"[Server] {nickname} has joined the chat!", writer)

    # 3. Main command/message loop
    try:
        while True:
            # Read the 4-byte header
            header = await reader.readexactly(4)
            msg_len = int.from_bytes(header, 'big')
            msg_bytes = await reader.readexactly(msg_len)
            raw_message = msg_bytes.decode('utf-8').strip()
            
            if not raw_message:
                continue

            # --- COMMAND PARSING ---
            if raw_message.startswith('/'):
                parts = raw_message.split(' ', 2)
                command = parts[0].lower()

                if command == '/users':
                    user_list = ", ".join(clients.values())
                    send_message(writer, f"[Server] Active users: {user_list}")
                    await writer.drain()
                    continue

                elif command == '/msg' and len(parts) >= 3:
                    target = parts[1]
                    private_msg = parts[2]
                    found = False
                    for w, name in clients.items():
                        if name.lower() == target.lower():
                            send_message(w, f"[Private from {nickname}]: {private_msg}")
                            send_message(writer, f"[Private to {target}]: {private_msg}")
                            await w.drain()
                            await writer.drain()
                            found = True
                            break
                    if not found:
                        send_message(writer, f"[Server] User '{target}' not found.")
                        await writer.drain()
                    continue
                else:
                    send_message(writer, f"[Server] Unknown command. Available: /users, /msg <user> <message>")
                    await writer.drain()
                    continue

            # --- NORMAL BROADCAST ---
            print(f"[Server] {nickname} says: {raw_message}")
            await broadcast(f"{nickname}: {raw_message}", writer)

    except (asyncio.IncompleteReadError, ConnectionError, BrokenPipeError):
        # Client disconnected or network error
        pass
    finally:
        # Clean up when the loop exits
        remove_client(writer)

async def main():
    print(f"[Async Server] Starting on port {PORT}...")
    server = await asyncio.start_server(handle_client, HOST, PORT)
    
    async with server:
        print(f"[Async Server] Waiting for clients...")
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Async Server] Shutting down gracefully...")
        sys.exit(0)