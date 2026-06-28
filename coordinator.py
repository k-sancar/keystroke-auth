import threading
import pandas as pd
import time
import os
import pathlib
from collections import deque

from input import KeystrokeRecorder
from digram import KeystrokePipeline
from detector import SecurityModel
from executor import Executor

class KeystrokeCoordinator:
    def __init__(self, window_size=50):
        self.recorder = KeystrokeRecorder()
        self.pipeline = KeystrokePipeline(block_size=window_size)
        
        self.model = SecurityModel()
        self.executor = Executor()
        
        self.main_df = pd.DataFrame()
        self.verification_buffer = deque(maxlen=5) 
        
        self.is_verifying = False
        self._recorder_thread = None

    def collect_data(self):
        if self.recorder.is_running:
            return

        print("[*] Started collecting baseline data into secure SQLite database...")
        self.recorder.start()

    def load_baseline(self):
        print("[*] Extracting baseline from secure database...")
        temp_processed = "temp_processed_baseline.csv"
        
        try:
            self.pipeline.build_user_profile(temp_processed)
            
            if os.path.exists(temp_processed):
                self.main_df = pd.read_csv(temp_processed)

                self.main_df['verification_flag'] = 'verified'
                self.main_df['source_class'] = 'historical'
                
                os.remove(temp_processed)
                print(f"[+] Baseline loaded. Locked {len(self.main_df)} 'verified' records.")
                return True
        except Exception as e:
            print(f"[!] Baseline processing error: {e}")
            if os.path.exists(temp_processed):
                os.remove(temp_processed)
        
        return False

    def _cleanup_unverified_logs(self, block):
        block = block.copy()
        block['verification_flag'] = 'not_verified'
        block['source_class'] = 'live_stream'
        block['timestamp'] = time.time()
        self.verification_buffer.append(block)

    def _check_unverified_threshold(self, anomaly_count: int) -> bool:
        return anomaly_count >= 3

    def verify_user(self):
        if self.is_verifying:
            return

        if not self.pipeline.selected_digrams:
            if not self.load_baseline():
                print("[!] No baseline. Aborting.")
                return

        print("\n" + "="*40)
        print("REAL-TIME KEYSTROKE VERIFICATION ACTIVE")
        print("="*40 + "\n")
        
        self.is_verifying = True
        self.recorder.is_running = True  
        self._recorder_thread = threading.Thread(target=self.recorder.start, daemon=True)
        self._recorder_thread.start()

        blocks_since_last_train = 0

        try:
            def tracked_stream():
                for r in self.recorder.stream_records():
                    print(f" [Stream] Recorder output: {r.strip()}") 
                    yield r

            print(f" [Coordinator] Golden digrams extracted from baseline: {len(self.pipeline.selected_digrams)}")

            for block in self.pipeline.process_stream(tracked_stream()):
                print(f" [Coordinator] Pipeline returned a block! Size: {block.shape}") 
                
                self._cleanup_unverified_logs(block)
                blocks_since_last_train += 1

                if len(self.verification_buffer) < 5 or self.main_df.empty:
                    print(f" [Coordinator] Buffer has {len(self.verification_buffer)}/5. Collecting more...")
                    continue

                if self.model.needs_training(blocks_since_last_train):
                    temp_df = pd.concat([self.main_df] + list(self.verification_buffer), ignore_index=True)
                    self.model.train(temp_df)
                    blocks_since_last_train = 0

                anomaly_count, df_for_model = self.model.evaluate_buffer(list(self.verification_buffer))
                print(f"[{time.strftime('%H:%M:%S')}] Buffer scanned. Anomalies found: {anomaly_count}/5")

                if self._check_unverified_threshold(anomaly_count):
                    self.executor.torpedo("Intruder detected on keyboard (Threshold 3/5)")

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