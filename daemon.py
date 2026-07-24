import sys
import pathlib
import threading
import winreg
import win32api
import win32gui
import win32ts
import keyring
from sqlcipher3 import dbapi2 as sqlite

from coordinator import KeystrokeCoordinator

class KeystrokeDaemon:
    def __init__(self, main_script_path: str):
        self.coordinator = KeystrokeCoordinator()
        self.is_active = False
        self.app_dir = pathlib.Path.home() / ".keystroke_auth"
        self.db_path = self.app_dir / "baseline_records.db"
        self.main_script_path = main_script_path

    def setup_autostart(self):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "KeystrokeSecurityDaemon"
        
        python_exe = sys.executable.replace("python.exe", "pythonw.exe")
        command = f'"{python_exe}" "{self.main_script_path}"'

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)
            print("[+] Autostart successfully configured in Registry.")
        except Exception as e:
            print(f"[!] Autostart configuration error: {e}")

    def get_total_profiles(self) -> int:
        if not self.db_path.exists():
            return 0
            
        db_key = keyring.get_password("KeystrokeSecurityDaemon", "db_encryption_key")
        if not db_key:
            return 0

        try:
            with sqlite.connect(self.db_path) as conn:
                conn.execute(f"PRAGMA key = '{db_key}';")
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'raw_baseline%';")
                tables = [row[0] for row in cursor.fetchall()]

        except Exception as e:
            print(f"[!] Database size verification error: {e}")
            return 0
            
        return len(tables)

    def start_monitoring(self):
        if self.is_active:
            return

        total_profiles = self.get_total_profiles()
        if total_profiles == 1:
            print("\n[*] Wake up. Found 1 profile in database.")
        else:
            print(f"\n[*] Wake up. Found {total_profiles} profiles in database.")

        self.is_active = True
        if total_profiles >= 1:
            print("[+] Database sufficient. Starting mode: VERIFY")
            threading.Thread(target=self.coordinator.verify_user, daemon=True).start()
        else:
            print("[-] Database incomplete. Starting mode: COLLECT")
            threading.Thread(target=self.coordinator.collect_data, daemon=True).start()

    def stop_monitoring(self):
        if not self.is_active:
            return
            
        print("\n[*] Screen locked. Suspending collection/verification processes.")
        self.coordinator.stop_session()
        self.is_active = False

    def wndproc(self, hwnd, msg, wparam, lparam):
        if msg == 0x02B1:
            if wparam == 0x8:
                self.start_monitoring()
            elif wparam == 0x7:
                self.stop_monitoring()
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def run(self):
        self.setup_autostart()
        
        wc = win32gui.WNDCLASS()
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = "KeystrokeDaemonHiddenWindow"
        wc.lpfnWndProc = self.wndproc
        
        try:
            win32gui.RegisterClass(wc)
        except Exception:
            pass
            
        hwnd = win32gui.CreateWindow(
            wc.lpszClassName, "KeystrokeDaemon",
            0, 0, 0, 0, 0, 0, 0, wc.hInstance, None
        )
        
        win32ts.WTSRegisterSessionNotification(hwnd, win32ts.NOTIFY_FOR_THIS_SESSION)
        
        print("[*] Daemon running in background. Waiting for system events...")
        
        self.start_monitoring()
        
        win32gui.PumpMessages()