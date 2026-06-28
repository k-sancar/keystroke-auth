# Keystroke Dynamics Verification System

A machine-learning-powered security daemon that continuously authenticates users based on their unique typing behavior. 

Unlike standard password prompts that verify identity only at login, this system operates continuously in the background. If an unauthorized user takes over the keyboard, the system detects the anomaly in typing cadence and immediately terminates access.

> **⚠️ Note:** > This public repository contains the **Safe Proof-of-Concept** version. Upon detecting an intruder, this version cleanly terminates its own process and logs an alert. It **does not** lock your operating system or intercept your mouse/keyboard globally. A private, hardened version with an active keylogging defense is being developed here:
https://github.com/KeystrokeID/keystroke-auth

---

## System Architecture & Workflow

The daemon is divided into single responsibility modules:

1. **Data Collection (`input.py`):** Captures raw keystroke timings in real-time (Press, Release). Dynamically calculates inactivity thresholds (AFK) using logarithmic standard deviation to prevent natural pauses from skewing the data.
2. **Feature Engineering (`digram.py`):** Processes raw timings into 4 core biometric metrics per key transition (digram):
   * **H (Hold time):** How long a key is pressed.
   * **UD (Up-Down time):** Flight time between releasing the first key and pressing the next.
   * **DD (Down-Down time):** Time between consecutive key presses.
   * **UU (Up-Up time):** Time between consecutive key releases.
3. **ML Detection (`detector.py`):** Evaluates live data blocks against the historical baseline to detect anomalies.
4. **Execution (`executor.py`):** Handles the fallback/lockdown logic if an intrusion is detected.
5. **Coordination (`coordinator.py`):** Manages threads, data buffers, and operational modes.

---

## Machine Learning Approach

This project utilizes an **Isolation Forest** (`scikit-learn`) for unsupervised anomaly detection. 

### Feature Selection (The "Golden Digrams")
Instead of analyzing every random key combination, the pipeline identifies the user's most reliable typing patterns:
* Filters out rare digrams (Minimum frequency = 3).
* Calculates the sum of variance across all biometric metrics for each digram.
* Isolates the **top 25% most stable digrams** (lowest variance).
* Sorts them by highest frequency to guarantee availability during normal typing.

### Resilient Imputation Strategy
When a user types a block of text, they may not use all of their "Golden Digrams". To handle missing values (`NaN`) in the live DataFrame without breaking the ML model, the system uses a smart, Double-tier fallback mechanism:
1. **Session Memory:** Uses the median of the last 3 occurrences of that specific digram in the current session.
2. **Baseline Median:** If no recent data exists, it falls back to the user's historical median for that digram.

---

## 🔒 Security & Data Privacy

Keystroke timings are highly sensitive biometric data. This project implements strict data protection:
* **Zero Plaintext Storage:** Raw data is stored in a local SQLite database encrypted with **SQLCipher**.
* **OS-Level Key Management:** The cryptographic key is never hardcoded. It is generated securely and stored exclusively in the host operating system's native Credential Manager via the `keyring` library.
* **Offline Operation:** 100% of the computation happens locally. No data ever leaves the machine.

---

### Prerequisites
Install the required dependencies:
```bash
pip install -r requirements.txt