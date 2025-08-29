import sys
import time
import requests
import subprocess
import threading

def test_server_startup():
    """Test that the server starts up correctly without hanging"""
    print("Testing server startup...")
    
    # Start the server in a subprocess
    try:
        process = subprocess.Popen([
            sys.executable, "-m", "uvicorn", 
            "app.main:app", 
            "--host", "127.0.0.1", 
            "--port", "8001",
            "--log-level", "warning"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for server to start (max 10 seconds)
        start_time = time.time()
        server_started = False
        
        while time.time() - start_time < 10:
            try:
                response = requests.get("http://127.0.0.1:8001/", timeout=1)
                if response.status_code == 200:
                    server_started = True
                    break
            except requests.exceptions.RequestException:
                # Server not ready yet, wait a bit more
                time.sleep(0.5)
        
        if server_started:
            print("PASS: Server started successfully")
            print("PASS: Root endpoint accessible")
            
            # Test manifest endpoint
            try:
                response = requests.get("http://127.0.0.1:8001/manifest.json", timeout=5)
                if response.status_code == 200:
                    print("PASS: Manifest endpoint accessible")
                else:
                    print(f"FAIL: Manifest endpoint returned status {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"FAIL: Failed to access manifest endpoint: {e}")
        else:
            print("FAIL: Server failed to start within 10 seconds")
            
        # Terminate the process
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            
    except Exception as e:
        print(f"FAIL: Failed to start server: {e}")

if __name__ == "__main__":
    test_server_startup()