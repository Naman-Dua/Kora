import psutil

def get_system_vitals():
    return {
        "cpu": psutil.cpu_percent(interval=0.1),
        "ram": psutil.virtual_memory().percent,
        "battery": psutil.sensors_battery().percent if psutil.sensors_battery() else "AC Power"
    }

def check_health():
    vitals = get_system_vitals()
    if vitals['cpu'] > 90: return "Sir, CPU usage is critical."
    if vitals['ram'] > 90: return "Memory load is nearly full, sir."
    return None