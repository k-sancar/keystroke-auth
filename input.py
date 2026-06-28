from pynput import keyboard
import time
import pathlib
import queue
import math
import statistics
from collections import deque
import keyring
import secrets
from sqlcipher3 import dbapi2 as sqlite

from constants import INACTIVITY_TIME, PAUSE_TIME

class KeystrokeRecorder:
    def __init__(self):

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
        if len(self.recent_pauses) < 3:
            return current_pause > PAUSE_TIME
            
        safe_pauses = [max(0.0001, p) for p in self.recent_pauses]
        log_pauses = [math.log(p) for p in safe_pauses]
        
        med_log = statistics.median(log_pauses)
        std_log = statistics.stdev(log_pauses)
        
        upper_threshold = math.exp(med_log + 3 * std_log)
        final_upper = max(PAUSE_TIME, upper_threshold) 
        
        lower_threshold = math.exp(med_log - 3 * std_log)
        final_lower = min(0.02, lower_threshold) 

        return current_pause > final_upper or current_pause < final_lower

    def save_records(self):
        if not self.records_for_db:
            print("[!] No data to save.")
            return

        db_key = self._get_or_create_key()

        try:
            with sqlite.connect(self.db_path) as conn:
                conn.execute(f"PRAGMA key = '{db_key}';")
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS raw_baseline (
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

                conn.executemany("""
                    INSERT INTO raw_baseline 
                    (key_pressed, prev_key, type, h_time, ud_time, dd_time, uu_time, afk_flag) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, self.records_for_db)
                
            print(f"\n[+] Saved {len(self.records_for_db)} records to the encrypted database:")
            print(f"    Path: {self.db_path}")

            self.records_for_db.clear()
            
        except Exception as e:
            print(f"[!] Critical error while saving to database: {e}")

    def on_press(self, key):
        current_time = time.perf_counter()
        current_pause = current_time - (self.last_press_time if self.last_press_time else current_time)
        afk_flag = self.is_outlier(current_pause)
        self.last_activity_time = current_time

        if key not in self.press_times:
            ud_time = current_time - (self.last_release_time if self.last_release_time else current_time)
            dd_time = current_pause
            self.press_times[key] = [current_time, ud_time, dd_time, self.last_key_pressed, afk_flag]

            if not afk_flag and current_pause > 0:
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
        self.record_queue.put(record_string)
        
        self.records_for_db.append((str_key, str_prev, type_str, h_time, ud_time, dd_time, uu_time, bool(afk_flag)))

        if key == keyboard.Key.esc:
            return False

    def stream_records(self):
        while self.is_running or not self.record_queue.empty():
            try:
                yield self.record_queue.get(timeout=0.1)
            except queue.Empty:
                continue

    def start(self):
        print(f"[*] Began listening. (AFK detection time: {INACTIVITY_TIME}s, Finish: ESC)")
        self.is_running = True
        with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as listener:
            try:
                while listener.running:
                    if time.perf_counter() - self.last_activity_time > INACTIVITY_TIME:
                        print("\n[!] Inactivity detected. Stopping listener and saving records.")
                        listener.stop()
                        break
                    time.sleep(1)
            except KeyboardInterrupt:
                listener.stop()
            
        self.is_running = False
        self.save_records()