#!/usr/bin/env python3
"""
Wrapper script to run the bot with a health check HTTP server for Cloud Run
"""
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for Cloud Run health checks"""
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running')

    def log_message(self, format, *args):
        # Suppress HTTP server logs
        pass

def start_health_server():
    """Start HTTP server for Cloud Run health checks"""
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Health check server running on port {port}")
    server.serve_forever()

if __name__ == '__main__':
    # Start health check server in background thread
    print("Starting health check server...")
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    # Give the server a moment to start
    import time
    time.sleep(2)
    print("Health check server started successfully")

    # Import and run the main bot
    print("Starting Telegram bot...")
    from main import main
    main()
