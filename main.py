import os
import pathlib
import sys
from daemon import KeystrokeDaemon
from coordinator import KeystrokeCoordinator

def setup_logging():
    log_dir = pathlib.Path.home() / ".keystroke_auth"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = open(log_dir / "daemon_background.log", "a", encoding="utf-8")
    
    sys.stdout = log_file
    sys.stderr = log_file

def main():

    script_path = os.path.abspath(__file__)
    os.chdir(os.path.dirname(script_path))

    if len(sys.argv) == 1:
        setup_logging()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "reset":
            print("[*] Initiating database reset...")
            coordinator = KeystrokeCoordinator()
            coordinator.reset_database()
            print("[+] Database reset complete.")
            print("[!] Note: Shut down your screen or terminate the 'pythonw.exe' background process to start a new data collection session.")
            return
            
        elif command == "add":
            print("[*] Initiating new profile collection...")
            coordinator = KeystrokeCoordinator()
            coordinator.collect_data()
            print("[+] Profile collection ended.")
            return

    script_path = os.path.abspath(__file__)
    daemon = KeystrokeDaemon(main_script_path=script_path)
    daemon.run()

if __name__ == "__main__":
    main()