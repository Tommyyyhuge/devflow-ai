"""
Simple HTTP/HTTPS Proxy Server
Listens on port 7890, forwards requests to target servers.
Supports HTTP CONNECT for HTTPS tunneling.
Usage: python proxy_server.py
"""

import socket
import threading
import select
from urllib.parse import urlparse


class ProxyHandler(threading.Thread):
    def __init__(self, client_socket):
        super().__init__(daemon=True)
        self.client_socket = client_socket

    def run(self):
        try:
            request = self.client_socket.recv(4096)
            if not request:
                return

            first_line = request.split(b'\r\n')[0].decode('utf-8', errors='ignore')
            method, target, _ = first_line.split(' ', 2)

            if method == 'CONNECT':
                self._handle_connect(target)
            else:
                self._handle_http(request, target)
        except Exception as e:
            print(f"[Proxy] Error: {e}")
        finally:
            self.client_socket.close()

    def _handle_connect(self, target):
        """Handle HTTPS CONNECT method"""
        host, port = target.split(':') if ':' in target else (target, '443')
        port = int(port)

        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.connect((host, port))
            self.client_socket.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            self._relay(self.client_socket, server_socket)
        except Exception as e:
            self.client_socket.sendall(f'HTTP/1.1 502 Bad Gateway\r\n\r\n{e}'.encode())

    def _handle_http(self, request, target):
        """Handle HTTP requests"""
        parsed = urlparse(target if target.startswith('http') else f'http://{target}')
        host = parsed.hostname
        port = parsed.port or 80

        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.connect((host, port))
            server_socket.sendall(request)
            self._relay(self.client_socket, server_socket)
        except Exception as e:
            print(f"[Proxy] HTTP error: {e}")

    def _relay(self, client, server):
        """Relay data between client and server"""
        while True:
            readable, _, _ = select.select([client, server], [], [], 1)
            if not readable:
                continue

            for sock in readable:
                data = sock.recv(4096)
                if not data:
                    return
                if sock is client:
                    server.sendall(data)
                else:
                    client.sendall(data)


def start_proxy(host='127.0.0.1', port=7890):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(100)

    print(f"[Proxy] HTTP/HTTPS Proxy running on {host}:{port}")
    print(f"[Proxy] Configure git: git config http.proxy http://{host}:{port}")
    print(f"[Proxy] Press Ctrl+C to stop")

    try:
        while True:
            client, addr = server.accept()
            handler = ProxyHandler(client)
            handler.start()
    except KeyboardInterrupt:
        print("\n[Proxy] Shutting down...")
    finally:
        server.close()


if __name__ == '__main__':
    start_proxy()
