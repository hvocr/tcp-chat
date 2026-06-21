import asyncio
import sys

HOST = '0.0.0.0'
PORT = 65432

# Data structures
clients = {}          # {writer: {'nickname': name, 'room': room_name}}
rooms = {}            # {room_name: set(writers)}

DEFAULT_ROOM = "general"

def get_room(room_name):
    """Get or create a room."""
    if room_name not in rooms:
        rooms[room_name] = set()
    return rooms[room_name]

def remove_client_from_room(writer):
    """Remove a writer from their current room."""
    if writer in clients:
        room_name = clients[writer]['room']
        if room_name in rooms:
            rooms[room_name].discard(writer)
            if not rooms[room_name]:
                del rooms[room_name]  # Clean up empty rooms

def send_message(writer, message):
    """Send a length-prefixed message to a specific client."""
    try:
        msg_bytes = message.encode('utf-8')
        header = len(msg_bytes).to_bytes(4, 'big')
        writer.write(header + msg_bytes)
        return True
    except:
        return False

async def broadcast_to_room(message, room_name, sender_writer=None):
    """Send a message to everyone in a specific room."""
    if room_name not in rooms:
        return
    for writer in list(rooms[room_name]):
        if writer != sender_writer:
            send_message(writer, message)
            await writer.drain()

async def broadcast(message, sender_writer=None):
    """Legacy broadcast to all clients (kept for compatibility, but we use room broadcasts now)."""
    # We'll just broadcast to the sender's room for simplicity.
    if sender_writer in clients:
        room = clients[sender_writer]['room']
        await broadcast_to_room(message, room, sender_writer)
    else:
        # Fallback: send to all clients
        for writer in list(clients.keys()):
            if writer != sender_writer:
                send_message(writer, message)
                await writer.drain()

def remove_client(writer):
    """Clean up a disconnected client."""
    if writer in clients:
        nickname = clients[writer]['nickname']
        room_name = clients[writer]['room']
        print(f"[Server] {nickname} removed from {room_name}.")
        remove_client_from_room(writer)
        del clients[writer]
        writer.close()
        # Notify the room they left
        asyncio.create_task(broadcast_to_room(f"[Server] {nickname} has left the chat.", room_name))

async def handle_client(reader, writer):
    """Handles a single client connection asynchronously."""
    addr = writer.get_extra_info('peername')
    print(f"[Server] {addr} connected. Waiting for nickname...")

    # 1. Receive nickname
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

    # 2. Assign to default room
    clients[writer] = {'nickname': nickname, 'room': DEFAULT_ROOM}
    rooms.setdefault(DEFAULT_ROOM, set()).add(writer)
    
    print(f"[Server] {nickname} ({addr}) joined {DEFAULT_ROOM}!")
    await broadcast_to_room(f"[Server] {nickname} has joined the chat.", DEFAULT_ROOM, writer)
    send_message(writer, f"[Server] Welcome, {nickname}! You are in the '{DEFAULT_ROOM}' room.")
    await writer.drain()

    # 3. Main message loop
    try:
        while True:
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
                current_room = clients[writer]['room']
                current_nick = clients[writer]['nickname']

                # --- /join <room> ---
                if command == '/join' and len(parts) >= 2:
                    target_room = parts[1].strip()
                    if target_room == current_room:
                        send_message(writer, f"[Server] You are already in '{target_room}'.")
                        await writer.drain()
                        continue
                    
                    # Leave current room
                    remove_client_from_room(writer)
                    # Join new room
                    clients[writer]['room'] = target_room
                    rooms.setdefault(target_room, set()).add(writer)
                    
                    # Notify both rooms
                    await broadcast_to_room(f"[Server] {current_nick} has left the chat.", current_room, writer)
                    await broadcast_to_room(f"[Server] {current_nick} has joined the chat.", target_room, writer)
                    
                    send_message(writer, f"[Server] You are now in the '{target_room}' room.")
                    await writer.drain()
                    continue

                # --- /users ---
                elif command == '/users':
                    if current_room in rooms:
                        user_list = ", ".join([clients[w]['nickname'] for w in rooms[current_room]])
                        send_message(writer, f"[Server] Users in {current_room}: {user_list}")
                    else:
                        send_message(writer, f"[Server] You are in a non-existent room?")
                    await writer.drain()
                    continue

                # --- /rooms ---
                elif command == '/rooms':
                    room_list = []
                    for room_name, writers in rooms.items():
                        room_list.append(f"{room_name} ({len(writers)} users)")
                    msg = f"[Server] Available rooms: " + ", ".join(room_list)
                    send_message(writer, msg)
                    await writer.drain()
                    continue

                # --- /msg ---
                elif command == '/msg' and len(parts) >= 3:
                    target = parts[1]
                    private_msg = parts[2]
                    found = False
                    # Find target in the current room (or globally? Usually globally).
                    # We'll search globally for simplicity, but we can restrict to room.
                    for w, data in clients.items():
                        if data['nickname'].lower() == target.lower():
                            send_message(w, f"[Private from {current_nick}]: {private_msg}")
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
                    send_message(writer, f"[Server] Unknown command. Available: /join, /rooms, /users, /msg <user> <message>")
                    await writer.drain()
                    continue

            # --- NORMAL BROADCAST ---
            current_room = clients[writer]['room']
            current_nick = clients[writer]['nickname']
            print(f"[Server] {current_nick} ({current_room}): {raw_message}")
            await broadcast_to_room(f"{current_nick}: {raw_message}", current_room, writer)

    except (asyncio.IncompleteReadError, ConnectionError, BrokenPipeError):
        pass
    finally:
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