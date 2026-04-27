import psutil
import re

def list_running_processes(limit=15):
    """Return a list of top running processes by name."""
    processes = []
    for proc in psutil.process_iter(['name', 'cpu_percent']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    # Sort by CPU usage
    processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
    names = [p['name'] for p in processes[:limit]]
    # Remove duplicates while preserving order
    seen = set()
    unique_names = [x for x in names if not (x in seen or seen.add(x))]
    
    return "Running apps include: " + ", ".join(unique_names) + "."

def kill_process_by_name(name):
    """Find and kill processes by name (case-insensitive)."""
    count = 0
    target = name.lower()
    if not target.endswith(".exe"):
        target += ".exe"
        
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'].lower() == target:
                proc.kill()
                count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if count > 0:
        return {"action": "process_kill", "reply": f"Successfully terminated {count} instance(s) of {name}.", "success": True}
    else:
        # Try a partial match if no exact match found
        for proc in psutil.process_iter(['name']):
            try:
                if name.lower() in proc.info['name'].lower():
                    proc.kill()
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if count > 0:
            return {"action": "process_kill", "reply": f"Successfully terminated {count} instance(s) matching '{name}'.", "success": True}
            
    return {"action": "process_kill", "reply": f"I couldn't find any running process named '{name}'.", "success": False, "error": "Process not found"}

def is_process_request(text):
    patterns = [
        r"what(?:'s| is) running",
        r"(?:list|show) (?:running )?(?:apps|processes)",
        r"(?:kill|terminate|stop|force close) (.+)",
    ]
    normalized = text.lower().strip()
    return any(re.search(p, normalized) for p in patterns)

def handle_process_command(text):
    normalized = text.lower().strip()
    
    # List
    if any(p in normalized for p in ["what's running", "what is running", "list running", "show running", "list apps"]):
        return {"action": "process_list", "reply": list_running_processes()}
        
    # Kill
    match = re.search(r"(?:kill|terminate|stop|force close) (.+)", normalized)
    if match:
        name = match.group(1).strip().strip("'\"")
        # Remove filler words
        name = re.sub(r"^(?:the |app |program )", "", name)
        return {"action": "process_kill", "reply": kill_process_by_name(name)}
        
    return None
