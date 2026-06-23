# 🔐 Encrypted Multi-Room Chat Server

A production-grade, asynchronous chat server built in Python. Supports **TLS encryption**, **dynamic chat rooms**, **private messaging**, and **auto-reconnect** — all powered by Python's `asyncio` for handling thousands of concurrent connections.

---

## ✨ Features

- **⚡ AsyncIO Backend** – Handles 10,000+ concurrent connections using a single-threaded event loop.
- **🔒 TLS Encryption** – All traffic is encrypted with SSL/TLS (self-signed certs supported for development).
- **🏠 Dynamic Rooms** – Users can create and join rooms on the fly with `/join`.
- **📨 Private Messaging** – Whisper to specific users with `/msg`.
- **🔄 Auto-Reconnect** – Client automatically retries with exponential backoff if the server goes down.
- **🛡️ DoS Protection** – Messages are limited to 1MB to prevent memory exhaustion attacks.
- **👤 Nickname Uniqueness** – Case-insensitive nickname enforcement to prevent impersonation.
- **📦 Custom Framed Protocol** – Length-prefixed binary protocol prevents message corruption (no more "squished" packets).
- **💻 Cross-Platform Client** – Runs on Windows, macOS, and Linux (no platform-specific hacks).
