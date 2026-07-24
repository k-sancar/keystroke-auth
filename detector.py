import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from collections import defaultdict, deque

class SecurityModel:
    def __init__(self, random_state=42):
        self.random_state = random_state
        self.models = [] 
        
        self.session_memory = defaultdict(lambda: deque(maxlen=3)) 
        
        self.current_medians_list = []

    def needs_training(self, blocks_since_last_train: int) -> bool:
        return not self.models or blocks_since_last_train >= 50

    def train(self, baselines: list, buffer_df: pd.DataFrame):
        self.models = []
        self.current_medians_list = []
        exclude_cols = ['verification_flag', 'status', 'timestamp']

        for baseline_df in baselines:
            baseline_features = [col for col in baseline_df.columns if col not in exclude_cols]
            
            buffer_subset = buffer_df.reindex(columns=baseline_features)
            
            df_mix = pd.concat([baseline_df[baseline_features], buffer_subset], ignore_index=True)

            medians = df_mix.median()
            self.current_medians_list.append(medians)
            
            df_features = df_mix.fillna(medians).fillna(0)
            
            contamination_ratio = 5 / len(df_mix)
            
            if contamination_ratio > 0.2:
                 raise ValueError(f"Contamination ratio {contamination_ratio:.4f} is too high. Need more user data.")

            model = IsolationForest(
                contamination=contamination_ratio,
                random_state=self.random_state,
                n_jobs=-1  
            )
            model.fit(df_features)
            self.models.append(model)
            
        print(f"[*] Ensemble training complete. {len(self.models)} models trained.")

    def evaluate_buffer(self, buffer_list: list) -> int:
        if not self.models:
            raise ValueError("Models weren't trained.")

        buffer_df = pd.concat(buffer_list, ignore_index=True)
        exclude_cols = ['verification_flag', 'status', 'timestamp']
        features = [col for col in buffer_df.columns if col not in exclude_cols]
        df_features_raw = buffer_df[features].copy()

        for col in df_features_raw.columns:
            valid_values = df_features_raw[col].dropna().tolist()
            if valid_values:
                self.session_memory[col].extend(valid_values)

        session_medians_dict = {}
        for col, vals in self.session_memory.items():
            if len(vals) == 3:
                session_medians_dict[col] = np.median(vals)
            else:
                session_medians_dict[col] = np.nan
                
        session_medians = pd.Series(session_medians_dict, dtype=float)

        best_anomaly_count = float('inf')

        for model, medians in zip(self.models, self.current_medians_list):
            df_features = df_features_raw.reindex(columns=medians.index)
            df_for_model = df_features.copy()

            df_for_model = df_for_model.fillna(session_medians)
            df_for_model = df_for_model.fillna(medians)

            predictions = model.predict(df_for_model)
            anomaly_count = (predictions == -1).sum()
            
            if anomaly_count < best_anomaly_count:
                best_anomaly_count = anomaly_count

        return best_anomaly_count