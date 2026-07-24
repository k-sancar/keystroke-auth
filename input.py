from pynput import keyboard, mouse
from collections import deque
from sqlcipher3 import dbapi2 as sqlite
import ctypes
import time
import pathlib
import queue
import math
import statistics
import keyring
import secrets
import sys

from constants import INACTIVITY_TIME, PAUSE_TIME

class KeystrokeRecorder:
    def __init__(self, on_torpedo_callback=None):
        self.on_torpedo_callback = on_torpedo_callback 
        self.app_dir = pathlib.Path.home() / ".keystroke_auth"
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.app_dir / "baseline_records.db"
        
        self.press_times = {}
        self.records_for_db = [] 
        self.record_queue = queue.Queue()
        
        self.is_running = False
        self.last_release_time = None
        self.last_press_time = None
        self.last_key_pressed = None
        self.last_activity_time = time.perf_counter()
        
        self.recent_pauses = deque(maxlen=20)
        self.recent_afk_flags = deque(maxlen=20)
        self.esc_pressed_once = False
        self.mode = "collect"

    def _get_or_create_key(self):
        service_name = "KeystrokeSecurityDaemon"
        user = "db_encryption_key"
        
        key = keyring.get_password(service_name, user)
        if not key:
            key = secrets.token_hex(32)
            keyring.set_password(service_name, user, key)
            print("[*] Generated new cryptographic key and saved to system Credential Manager.")
        return key

    def is_outlier(self, current_pause):
        if current_pause > PAUSE_TIME:
            return True
        if len(self.recent_pauses) < 3:
            return False
            
        safe_pauses = [max(0.0001, p) for p in self.recent_pauses]
        log_pauses = [math.log(p) for p in safe_pauses]
        
        med_log = statistics.median(log_pauses)
        std_log = max(0.1, statistics.stdev(log_pauses))
        
        upper_threshold = math.exp(med_log + 3 * std_log)
        
        lower_threshold = math.exp(med_log - 3 * std_log)

        return current_pause > upper_threshold or current_pause < lower_threshold

    def save_records(self):
        if self.mode == "verify":
            self.records_for_db.clear()
            return

        if not self.records_for_db:
            return 

        if len(self.records_for_db) < 1050:
            print("\n[!] Rejecting records: lack of required 1050 entries.")
            self.records_for_db.clear()
            return

        db_key = self._get_or_create_key()
        session_table = f"raw_baseline_{int(time.time())}"

        try:
            with sqlite.connect(self.db_path) as conn:
                conn.execute(f"PRAGMA key = '{db_key}';")
                
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {session_table} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key_pressed TEXT,
                        prev_key TEXT,
                        type TEXT,
                        h_time REAL,
                        ud_time REAL,
                        dd_time REAL,
                        uu_time REAL,
                        afk_flag BOOLEAN,
                        recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.executemany(f"""
                    INSERT INTO {session_table} 
                    (key_pressed, prev_key, type, h_time, ud_time, dd_time, uu_time, afk_flag) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, self.records_for_db)
                
            print(f"\n[+] Success! Saved {len(self.records_for_db)} records to new table: {session_table}")
            print(f"    Encrypted database: {self.db_path}")
            self.records_for_db.clear()
            
        except Exception as e:
            print(f"\n[!] Critical error while saving to database: {e}")

    def on_press(self, key):

        if key in self.press_times:
            return
        
        current_time = time.perf_counter()
        current_pause = current_time - (self.last_press_time if self.last_press_time else current_time)
        afk_flag = self.is_outlier(current_pause)
        self.last_activity_time = current_time

        self.recent_afk_flags.append(afk_flag)
        
        if self.mode == "verify" and sum(self.recent_afk_flags) >= 10:
            print("\n\n[!] Too many typing anomalies (10/20). Evasion attempt detected.")
            if self.on_torpedo_callback:
                self.on_torpedo_callback("Too many typing anomalies (10/20). Evasion attempt detected.")
            else:
                ctypes.windll.user32.LockWorkStation()
            self.is_running = False
            return False

        ud_time = current_time - (self.last_release_time if self.last_release_time else current_time)
        dd_time = current_pause
        self.press_times[key] = [current_time, ud_time, dd_time, self.last_key_pressed, afk_flag]

        if PAUSE_TIME > current_pause >= 0.02:
            self.recent_pauses.append(current_pause)

        self.last_press_time = current_time
        self.last_key_pressed = str(key)

    def on_release(self, key):
        current_release_time = time.perf_counter()
        self.last_activity_time = current_release_time
        uu_time = current_release_time - (self.last_release_time if self.last_release_time else current_release_time)
        self.last_release_time = current_release_time

        popped_data = self.press_times.pop(key, [None, None, None, None, None])
        start_time, ud_time, dd_time, prev_key, afk_flag = popped_data

        if start_time is None:
            return

        h_time = current_release_time - start_time
        type_str = "not faked" 

        str_key = str(key).replace("'", "")
        str_prev = str(prev_key).replace("'", "") if prev_key else "None"
        record_string = f"{str_key}, {str_prev}, {type_str}, {h_time}, {ud_time}, {dd_time}, {uu_time}, {afk_flag}"

        if key == keyboard.Key.esc:
            if self.mode == "verify":
                print("\n[+] Verification completed.")
                return False
                
            if len(self.records_for_db) >= 1050:
                print("\n\n[+] Collected sufficient data. Stopping listening.")
                return False
            else:
                if not self.esc_pressed_once:
                    print(f"\n\n[!] WARNING: Missing {1050 - len(self.records_for_db)} entries. Table will not be saved.")
                    print("[!] Press ESC again to cancel and delete data, or any other key to continue typing.")
                    self.esc_pressed_once = True
                else:
                    print("\n[-] Session cancelled. Data deleted from memory.")
                    self.records_for_db.clear()
                    return False
        else:
            if self.mode == "collect" and self.esc_pressed_once:
                print(f"\n[*] Resumed data collection. Keep typing...", end="")
                self.esc_pressed_once = False

        if self.mode == "verify":
            self.record_queue.put(record_string)
        self.records_for_db.append((str_key, str_prev, type_str, h_time, ud_time, dd_time, uu_time, bool(afk_flag)))

        if self.mode == "collect":
            print(f"\r[*] Collecting data: {len(self.records_for_db)} / 1050 entries (minimum)", end="", flush=True)

    def on_mouse_activity(self, *args):
        self.last_activity_time = time.perf_counter()

    def stream_records(self):
        while self.is_running or not self.record_queue.empty():
            try:
                yield self.record_queue.get(timeout=0.1)
            except queue.Empty:
                continue

    def start(self, mode="collect"):
        self.mode = mode
        self.records_for_db.clear()
        self.press_times.clear()

        self.last_press_time = None
        self.last_release_time = None
        self.last_key_pressed = None

        self.last_activity_time = time.perf_counter()
        self.recent_afk_flags.clear()
        self.recent_pauses.clear()
        
        with self.record_queue.mutex:
            self.record_queue.queue.clear()
        if self.mode == "collect":
            print(f"[*] Began listening (Mode: Collect). (AFK detection: {INACTIVITY_TIME}s, Finish: ESC)")
        else:
            print(f"[*] Began listening (Mode: Verify). (AFK detection: {INACTIVITY_TIME}s, Finish: ESC)")
            
        self.is_running = True
        self.esc_pressed_once = False

        mouse_listener = mouse.Listener(
            on_move=self.on_mouse_activity,
            on_click=self.on_mouse_activity,
            on_scroll=self.on_mouse_activity
        )
        mouse_listener.start()
        
        with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as listener:
            try:
                while listener.running:
                    if not self.is_running:
                        listener.stop()
                        mouse_listener.stop()
                        break                    
                    if time.perf_counter() - self.last_activity_time > INACTIVITY_TIME:
                        print("\n\n[!] Inactivity detected. Locking screen and stopping listener.")
                        ctypes.windll.user32.LockWorkStation()
                        if self.mode == "collect" and len(self.records_for_db) < 1050:
                            print("[-] Session rejected: Not enough entries (<1050) before disconnection.")
                            self.records_for_db.clear()
                        listener.stop()
                        mouse_listener.stop()
                        break
                    time.sleep(1)
            except KeyboardInterrupt:
                listener.stop()
                mouse_listener.stop()
            
        self.is_running = False
        self.save_records()
        sys.stdout.flush()
        sys.stderr.flush()