import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from collections import defaultdict, deque

class SecurityModel:
    def __init__(self, random_state=42):
        self.random_state = random_state
        self.model = None
        
        self.session_memory = defaultdict(lambda: deque(maxlen=3)) 
        
        self.current_medians = None

    def needs_training(self, blocks_since_last_train: int) -> bool:
        return self.model is None or blocks_since_last_train >= 50

    def train(self, df_mix: pd.DataFrame):
        exclude_cols = ['verification_flag', 'source_class', 'status', 'timestamp']
        features = [col for col in df_mix.columns if col not in exclude_cols]

        df_features = df_mix[features].copy()
        
        self.current_medians = df_features.median()
        
        contamination_ratio = 5 / len(df_mix)
        
        if contamination_ratio >= 0.2:
             raise ValueError(f"Contamination ratio {contamination_ratio:.4f} is too high. Need more user data.")

        self.model = IsolationForest(
            contamination=contamination_ratio,
            random_state=self.random_state,
            n_jobs=-1  
        )
        
        print(f"[*] Isolation Forest training. Contamination: {contamination_ratio:.4f}")
        self.model.fit(df_features)

    def evaluate_buffer(self, buffer_list: list) -> int:
        if self.model is None:
            raise ValueError("Model wasn't trained.")

        buffer_df = pd.concat(buffer_list, ignore_index=True)
        exclude_cols = ['verification_flag', 'source_class', 'status', 'timestamp']
        features = [col for col in buffer_df.columns if col not in exclude_cols]

        df_features = buffer_df[features].copy()
        df_features = df_features.reindex(columns=self.current_medians.index)


        for col in df_features.columns:
            valid_values = df_features[col].dropna().tolist()
            if valid_values:
                self.session_memory[col].extend(valid_values)


        session_medians_dict = {}
        for col, vals in self.session_memory.items():
            if len(vals) == 3:
                session_medians_dict[col] = np.median(vals)
            else:
                session_medians_dict[col] = np.nan
                
        session_medians = pd.Series(session_medians_dict, dtype=float)


        df_for_model = df_features.copy()

        df_for_model = df_for_model.fillna(session_medians)
        df_for_model = df_for_model.fillna(self.current_medians)

        predictions = self.model.predict(df_for_model)
        anomaly_count = (predictions == -1).sum()
        
        return anomaly_count, df_for_model