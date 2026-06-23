import socket
import time
import threading

def test_connection():
    print("Testing server connection...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        s.connect(('127.0.0.1', 65432))
        s.close()
        print("✅ Server is up!")
    except:
        print("❌ Server not running. Start it with 'py server_async.py'")

if __name__ == "__main__":
    test_connection()