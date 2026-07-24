import threading
import pandas as pd
import time
import os
import pathlib
import keyring
from sqlcipher3 import dbapi2 as sqlite
from collections import deque

from input import KeystrokeRecorder
from digram import KeystrokePipeline
from detector import SecurityModel
from executor import Executor

class KeystrokeCoordinator:
    def __init__(self, window_size=50):
        self.executor = Executor()
        
        self.recorder = KeystrokeRecorder(on_torpedo_callback=self.executor.torpedo)
        self.pipeline = KeystrokePipeline(block_size=window_size)
        
        self.model = SecurityModel()
        
        self.baselines = [] 
        self.verification_buffer = deque(maxlen=5) 
        
        self.is_verifying = False
        self._recorder_thread = None

    def collect_data(self):
        if self.recorder.is_running:
            return

        print("[*] Started collecting baseline data into secure SQLite database...")
        self.recorder.start()

    def load_baseline(self):
        print("[*] Searching for baseline tables in secure database...")
        db_path = pathlib.Path.home() / ".keystroke_auth" / "baseline_records.db"
        db_key = keyring.get_password("KeystrokeSecurityDaemon", "db_encryption_key")
        
        if not db_path.exists() or not db_key:
            print("[!] Database file or encryption key not found.")
            return False

        tables = []
        try:
            with sqlite.connect(db_path) as conn:
                conn.execute(f"PRAGMA key = '{db_key}';")
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'raw_baseline%';")
                tables = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"[!] Database access error: {e}")
            return False

        if not tables:
            print("[!] No tables matching 'raw_baseline%' found.")
            return False

        loaded_any = False
        temp_processed = "temp_processed_baseline.csv"
        
        for table in tables:
            try:
                if self.pipeline.build_user_profile(temp_processed, table_name=table):
                    df = pd.read_csv(temp_processed)
                    df['verification_flag'] = 'verified'
                    
                    self.baselines.append(df) 
                    
                    os.remove(temp_processed)
                    print(f"[+] Profile '{table}' loaded. Locked {len(df)} 'verified' records.")
                    loaded_any = True
            except Exception as e:
                print(f"[!] Baseline processing error for {table}: {e}")
                if os.path.exists(temp_processed):
                    os.remove(temp_processed)
        
        return loaded_any

    def _cleanup_unverified_logs(self, block):
        block = block.copy()
        block['verification_flag'] = 'not_verified'
        block['timestamp'] = time.time()
        self.verification_buffer.append(block)

    def _check_unverified_threshold(self, anomaly_count: int) -> bool:
        return anomaly_count >= 4

    def verify_user(self):
        if self.is_verifying:
            return

        if not self.baselines:
            if not self.load_baseline():
                print("[!] No baselines. Aborting.")
                return

        print("\n" + "="*40)
        print("REAL-TIME KEYSTROKE VERIFICATION ACTIVE")
        print("="*40 + "\n")
        
        self.is_verifying = True
        self.recorder.is_running = True  
        self._recorder_thread = threading.Thread(target=self.recorder.start, kwargs={"mode": "verify"}, daemon=True)
        self._recorder_thread.start()

        blocks_since_last_train = 0

        try:
            def tracked_stream():
                for r in self.recorder.stream_records():
                    yield r

            for block in self.pipeline.process_stream(tracked_stream()):

                self._cleanup_unverified_logs(block)
                blocks_since_last_train += 1

                if len(self.verification_buffer) < 5 or not self.baselines:
                    print(f" [Coordinator] Buffer has {len(self.verification_buffer)}/5. Collecting more...")
                    continue

                if self.model.needs_training(blocks_since_last_train):
                    buffer_df = pd.concat(list(self.verification_buffer), ignore_index=True)
                    self.model.train(self.baselines, buffer_df)
                    blocks_since_last_train = 0

                anomaly_count = self.model.evaluate_buffer(list(self.verification_buffer))
                print(f"[{time.strftime('%H:%M:%S')}] Buffer scanned. Most similar style anomalies: {anomaly_count}/5")

                if self._check_unverified_threshold(anomaly_count):
                    self.executor.torpedo("Intruder detected on keyboard (Threshold 4/5 across all models)")
                    self.verification_buffer.clear()
                    self.model.session_memory.clear()

        except KeyboardInterrupt:
            print("\n[!] Verification interrupted by user.")
        finally:
            self.stop_session()

    def stop_session(self):
        self.recorder.is_running = False
        self.is_verifying = False
        
        if self._recorder_thread and self._recorder_thread.is_alive():
            self._recorder_thread.join(timeout=2)
            
        print("\n[*] Session ended.")

    def reset_database(self):
        db_path = pathlib.Path.home() / ".keystroke_auth" / "baseline_records.db"
        
        if db_path.exists():
            os.remove(db_path)
            print("[+] Encrypted database file has been permanently deleted (Wipe).")
        else:
            print("[-] Database does not exist. Nothing to wipe.")