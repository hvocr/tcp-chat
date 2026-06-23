import asyncio
import sys
import ssl

HOST = '0.0.0.0'
PORT = 65432
MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB limit to prevent DoS attacks

# Data structures
clients = {}          # {writer: {'nickname': name, 'room': room_name}}
rooms = {}            # {room_name: set(writers)}
DEFAULT_ROOM = "general"

# Async lock to protect shared state (clients and rooms)
state_lock = asyncio.Lock()

def send_message(writer, message):
    """Send a length-prefixed message. Returns False if it fails."""
    try:
        msg_bytes = message.encode('utf-8')
        if len(msg_bytes) > MAX_MESSAGE_SIZE:
            return False
        header = len(msg_bytes).to_bytes(4, 'big')
        writer.write(header + msg_bytes)
        return True
    except (BrokenPipeError, ConnectionError, AttributeError):
        return False

async def broadcast_to_room(message, room_name, sender_writer=None):
    if room_name not in rooms:
        return
    for writer in list(rooms[room_name]):
        if writer != sender_writer and not writer.is_closing():
            try:
                send_message(writer, message)
                await writer.drain()
            except (ConnectionError, BrokenPipeError):
                pass

async def remove_client(writer):
    async with state_lock:
        if writer not in clients:
            return
        nickname = clients[writer]['nickname']
        room_name = clients[writer]['room']
        
        # Remove from room
        if room_name in rooms:
            rooms[room_name].discard(writer)
            if not rooms[room_name]:
                del rooms[room_name]
        
        # Remove from global dict
        del clients[writer]
    
    print(f"[Server] {nickname} removed from {room_name}.")
    writer.close()
    await asyncio.create_task(broadcast_to_room(f"[Server] {nickname} has left the chat.", room_name))

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"[Server] {addr} connected.")

    try:
        # 1. Receive nickname
        header = await reader.readexactly(4)
        nickname_len = int.from_bytes(header, 'big')
        
        if nickname_len > MAX_MESSAGE_SIZE:
            send_message(writer, "[Server] Error: Nickname too long.")
            await writer.drain()
            writer.close()
            return
            
        nickname_bytes = await reader.readexactly(nickname_len)
        nickname = nickname_bytes.decode('utf-8').strip()
        
        if not nickname:
            writer.close()
            return

        # 2. Check for duplicate nickname (case-insensitive)
        async with state_lock:
            for existing_writer, data in clients.items():
                if data['nickname'].lower() == nickname.lower():
                    send_message(writer, f"[Server] Error: Nickname '{nickname}' is already taken.")
                    await writer.drain()
                    writer.close()
                    return

            # 3. Assign to default room
            clients[writer] = {'nickname': nickname, 'room': DEFAULT_ROOM}
            rooms.setdefault(DEFAULT_ROOM, set()).add(writer)
        
        print(f"[Server] {nickname} ({addr}) joined {DEFAULT_ROOM}!")
        await broadcast_to_room(f"[Server] {nickname} has joined the chat.", DEFAULT_ROOM, writer)
        send_message(writer, f"[Server] Welcome, {nickname}! You are in '{DEFAULT_ROOM}'.")
        await writer.drain()

        # 4. Main message loop
        while True:
            header = await reader.readexactly(4)
            msg_len = int.from_bytes(header, 'big')
            
            # DoS Protection
            if msg_len > MAX_MESSAGE_SIZE:
                send_message(writer, "[Server] Error: Message exceeds size limit (1MB).")
                await writer.drain()
                break
                
            msg_bytes = await reader.readexactly(msg_len)
            raw_message = msg_bytes.decode('utf-8').strip()
            
            if not raw_message:
                continue

            # Get current state (copy needed for async operations)
            async with state_lock:
                current_room = clients[writer]['room']
                current_nick = clients[writer]['nickname']

            # --- COMMAND PARSING ---
            if raw_message.startswith('/'):
                parts = raw_message.split(' ', 2)
                command = parts[0].lower()

                # /join
                if command == '/join' and len(parts) >= 2:
                    target_room = parts[1].strip()
                    if target_room == current_room:
                        send_message(writer, f"[Server] You are already in '{target_room}'.")
                        await writer.drain()
                        continue
                    
                    # Leave old, join new (protected by lock)
                    async with state_lock:
                        if current_room in rooms:
                            rooms[current_room].discard(writer)
                            if not rooms[current_room]:
                                del rooms[current_room]
                        
                        clients[writer]['room'] = target_room
                        rooms.setdefault(target_room, set()).add(writer)
                    
                    await broadcast_to_room(f"[Server] {current_nick} has left the chat.", current_room, writer)
                    await broadcast_to_room(f"[Server] {current_nick} has joined the chat.", target_room, writer)
                    
                    send_message(writer, f"[Server] You are now in '{target_room}'.")
                    await writer.drain()
                    continue

                # /users
                elif command == '/users':
                    async with state_lock:
                        if current_room in rooms:
                            user_list = ", ".join([clients[w]['nickname'] for w in rooms[current_room]])
                            send_message(writer, f"[Server] Users in {current_room}: {user_list}")
                        else:
                            send_message(writer, f"[Server] You are in a non-existent room?")
                    await writer.drain()
                    continue

                # /rooms
                elif command == '/rooms':
                    async with state_lock:
                        room_list = [f"{r} ({len(w)} users)" for r, w in rooms.items()]
                    msg = f"[Server] Available rooms: " + ", ".join(room_list)
                    send_message(writer, msg)
                    await writer.drain()
                    continue

                # /msg
                elif command == '/msg' and len(parts) >= 3:
                    target = parts[1]
                    private_msg = parts[2]
                    found = False
                    
                    async with state_lock:
                        for w, data in clients.items():
                            if data['nickname'].lower() == target.lower():
                                send_message(w, f"[Private from {current_nick}]: {private_msg}")
                                send_message(writer, f"[Private to {target}]: {private_msg}")
                                await w.drain()
                                found = True
                                break
                    
                    if not found:
                        send_message(writer, f"[Server] User '{target}' not found.")
                    
                    await writer.drain()
                    continue

                else:
                    send_message(writer, f"[Server] Unknown command. Available: /join, /rooms, /users, /msg <user> <message>")
                    await writer.drain()
                    continue

            # --- NORMAL BROADCAST ---
            print(f"[Server] {current_nick} ({current_room}): {raw_message}")
            await broadcast_to_room(f"{current_nick}: {raw_message}", current_room, writer)

    except (asyncio.IncompleteReadError, ConnectionError, BrokenPipeError, UnicodeDecodeError, ValueError):
        # Client disconnected gracefully or malformed data
        pass
    except Exception as e:
        print(f"[Server] Unhandled error: {type(e).__name__}: {e}")
    finally:
        await remove_client(writer)

async def main():
    print(f"[Async Server] Starting TLS on port {PORT}...")
    
    try:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain('cert.pem', 'key.pem')
        print("[Async Server] SSL certificate loaded successfully.")
    except FileNotFoundError:
        print("[Async Server] ERROR: cert.pem or key.pem not found!")
        print("Generate them using: py generate_cert.py")
        return

    server = await asyncio.start_server(handle_client, HOST, PORT, ssl=ssl_context)
    async with server:
        print(f"[Async Server] Waiting for encrypted clients...")
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Async Server] Shutting down gracefully...")
        sys.exit(0)