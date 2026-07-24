import pandas as pd
import numpy as np
import pathlib
import keyring
from sqlcipher3 import dbapi2 as sqlite

from constants import MIN_FREQ

class KeystrokePipeline:
    def __init__(self, block_size: int = 50):
        self.block_size = block_size
        self.df_digrams = None
        self.global_selected_digrams = set()
        self.df_final_blocks = None
        self.baseline_means = {}

    def _parse_raw_record(self, record_str, last_h):
        if record_str.startswith("Key,"): 
            return None, last_h
            
        parts = [p.strip() for p in record_str.split(',')]
        if len(parts) < 8: 
            return None, last_h
            
        columns = ['Key', 'Previous Key', 'Type', 'H', 'UD', 'DD', 'UU', 'afk_flag']
        row = dict(zip(columns, parts))
        
        for col in ['H', 'UD', 'DD', 'UU']:
            try: row[col] = float(row[col])
            except ValueError: row[col] = 0.0
            
        current_h = row['H']
        
        key = str(row['Key']).replace("'", "").replace("Key.", "")
        prev_key = str(row['Previous Key']).replace("'", "").replace("Key.", "")
        
        if prev_key == 'None' or str(row['afk_flag']).lower() == 'true' or last_h is None:
            return None, current_h
            
        h1 = last_h
        h2 = current_h
        ud = row['UD']
        
        if ud == 0: ud = 0.001
            
        digram_data = {
            'Digram': prev_key + key,
            'H1': h1,
            'H2': h2,
            'UD': ud,
            'DD': row['DD'],
            'UU': row['UU'],
            'H1/UD': h1 / ud,
            'H2/UD': h2 / ud
        }
        
        return digram_data, current_h

    def _calculate_single_block(self, df):
        features = ['H1', 'H2', 'UD', 'DD', 'UU', 'H1/UD', 'H2/UD']
        
        if df.empty:
            return pd.DataFrame()
            
        df_grouped = df.groupby('Digram')[features].mean().reset_index()
        df_grouped['dummy'] = 0
        
        df_wide = df_grouped.pivot(index='dummy', columns='Digram', values=features)
        df_wide.columns = [f"{col[0]}_{col[1]}" for col in df_wide.columns]
        
        return df_wide
    
    def process_stream(self, record_stream : iter):
        buffer = []
        last_h = None
        
        for record_str in record_stream:
            digram_data, last_h = self._parse_raw_record(record_str, last_h)
            if digram_data:
                buffer.append(digram_data)
                
            if len(buffer) >= self.block_size:
                df_temp = pd.DataFrame(buffer)
                block = self._calculate_single_block(df_temp)
                if not block.empty:
                    yield block
                buffer = []
    
    def _generate_digrams(self, table_name="raw_baseline"):
        app_dir = pathlib.Path.home() / ".keystroke_auth"
        db_path = app_dir / "baseline_records.db"
        
        if not db_path.exists():
            print(f"[!] Error: Database file {db_path} not found.")
            return False
            
        db_key = keyring.get_password("KeystrokeSecurityDaemon", "db_encryption_key")
        if not db_key:
            print("[!] Error: Encryption key missing from Windows Credential Manager.")
            return False

        try:
            with sqlite.connect(db_path) as conn:
                conn.execute(f"PRAGMA key = '{db_key}';")
                
                query = f"""
                    SELECT 
                        key_pressed AS 'Key', 
                        prev_key AS 'Previous Key', 
                        type AS 'Type', 
                        h_time AS 'H', 
                        ud_time AS 'UD', 
                        dd_time AS 'DD', 
                        uu_time AS 'UU', 
                        afk_flag
                    FROM {table_name}
                """
                df = pd.read_sql_query(query, conn)
                
        except Exception as e:
            print(f"[!] Database read error: {e}")
            return False

        if df.empty:
            print(f"[!] Error: No records found in the database for table {table_name}.")
            return False

        df.columns = df.columns.str.strip()
        numeric_cols = ['H', 'UD', 'DD', 'UU']
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        df['H1'] = df['H'].shift(1)
        df['H2'] = df['H']

        df['Key'] = df['Key'].astype(str).str.replace("'", "", regex=False).str.replace("Key.", "", regex=False).str.strip()
        df['Previous Key'] = df['Previous Key'].astype(str).str.replace("'", "", regex=False).str.replace("Key.", "", regex=False).str.strip()
        df['Digram'] = df['Previous Key'] + df['Key']

        df = df.dropna(subset=['H1']) 
        df = df[df['Previous Key'] != 'None']
        
        if 'afk_flag' in df.columns:
            df['afk_flag'] = df['afk_flag'].astype(str).str.strip().str.lower()
            df = df[df['afk_flag'] != 'true']
            df = df[df['afk_flag'] != '1'] 
        
        df['H1/UD'] = df['H1'] / df['UD']
        df['H2/UD'] = df['H2'] / df['UD']

        final_columns = ['Digram', 'H1', 'H2', 'UD', 'DD', 'UU', 'H1/UD', 'H2/UD']
        if 'Type' in df.columns: final_columns.insert(1, 'Type')
            
        self.df_digrams = df[final_columns].copy()
        self.df_digrams.replace([np.inf, -np.inf], np.nan, inplace=True)
        self.df_digrams.dropna(inplace=True)
        
        return True

    def _select_optimal_digrams(self):
        features = ['H1', 'H2', 'UD', 'DD', 'UU', 'H1/UD', 'H2/UD']
        freq = self.df_digrams.groupby('Digram').size()

        valid_digrams = freq[freq >= MIN_FREQ].index
        df_filtered = self.df_digrams[self.df_digrams['Digram'].isin(valid_digrams)]
        
        if df_filtered.empty:
            return []

        freq_filtered = df_filtered.groupby('Digram').size()
        var_sum = df_filtered.groupby('Digram')[features].var().sum(axis=1)

        stats = pd.DataFrame({
            'Variance_Sum': var_sum,
            'Frequency': freq_filtered
        }).fillna(999).sort_values(by='Variance_Sum')

        variance_limit = stats['Variance_Sum'].quantile(0.25)
        stable_digrams = stats[stats['Variance_Sum'] <= variance_limit].copy()
        
        stable_digrams = stable_digrams.sort_values(by='Frequency', ascending=False)
        
        dynamic_max = max(2, len(self.df_digrams) // 300)
        HARD_MAX = 12 
        n_final = min(dynamic_max, HARD_MAX, len(stable_digrams))
        
        if n_final == 0:
            n_final = 1
            return stats.head(n_final).index.tolist()
        else:
            return stable_digrams.head(n_final).index.tolist()

    def _create_blocks(self, specific_digrams):
        df = self.df_digrams.copy()
        df['Block_ID'] = np.arange(len(df)) // self.block_size
        
        df = df[df['Digram'].isin(specific_digrams)]
        if df.empty:
            self.df_final_blocks = pd.DataFrame()
            return

        features = ['H1', 'H2', 'UD', 'DD', 'UU', 'H1/UD', 'H2/UD']
        df_grouped = df.groupby(['Block_ID', 'Digram'])[features].mean().reset_index()

        df_wide = df_grouped.pivot(index='Block_ID', columns='Digram', values=features)
        df_wide.columns = [f"{col[0]}_{col[1]}" for col in df_wide.columns]
        self.baseline_means = df_wide.mean().to_dict()

        df_wide = df_wide.interpolate(method='linear').ffill().bfill()
        self.df_final_blocks = df_wide.fillna(0)

    def build_user_profile(self, output_csv: str, table_name: str = "raw_baseline"):
        print(f"[*] Extracting baseline data from local secure database (table: {table_name}) ...")
        
        if not self._generate_digrams(table_name):
            return False
            
        specific_digrams = self._select_optimal_digrams()
        if not specific_digrams:
            print(f"[!] No stable digrams found for {table_name}.")
            return False
            
        print(f"[*] Selected {len(specific_digrams)} most stable digrams for '{table_name}'.")
        
        self.global_selected_digrams.update(specific_digrams)
        
        self._create_blocks(specific_digrams)
        
        if not self.df_final_blocks.empty:
            self.df_final_blocks.to_csv(output_csv, index=False)
            print(f"[+] Successfully completed! Created {len(self.df_final_blocks)} blocks.")
            return True
        else:
            print("[!] Error: Resulting DataFrame is empty.")
            return False