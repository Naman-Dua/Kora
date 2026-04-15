import psutil

def get_system_context():
    processes = [p.name().lower() for p in psutil.process_iter(attrs=['name'])]
    
    if any(app in str(processes) for app in ["code.exe", "pycharm", "sublime"]):
        return "Master is currently coding in a development environment."
    elif "chrome.exe" in str(processes) or "msedge.exe" in str(processes):
        return "Master is currently researching on the web."
    elif "zoom.exe" in str(processes) or "teams.exe" in str(processes):
        return "Master is in a meeting."
    else:
        return "Master is currently at the main workstation."