# Keystroke Dynamics Verification System

A Windows background daemon that continuously authenticates users based on their unique typing behavior using keystroke dynamics and machine learning.

Unlike standard password prompts that verify identity only at login, this system operates continuously in the background. If an unauthorized user takes over the keyboard, the system detects the anomaly in typing cadence and immediately locks the system.

---

## System Architecture & Workflow

The daemon is divided into single responsibility modules:

1. **Data Collection (`input.py`):** Captures raw keystroke timings in real-time (Press, Release) globally using low-level hooks. Dynamically calculates inactivity thresholds (AFK) using logarithmic standard deviation to prevent natural pauses from skewing data, while ignoring OS auto-repeat spam and hardware rollover anomalies.
2. **Feature Engineering (`digram.py`):** Processes raw timings into biometric metrics per key transition (digram):
   * **H (Hold time):** How long a key is pressed.
   * **UD (Up-Down time):** Flight time between releasing the first key and pressing the next.
   * **DD (Down-Down time):** Time between consecutive key presses.
   * **UU (Up-Up time):** Time between consecutive key releases.
   * **Ratios (`H1/UD`, `H2/UD`):** Advanced proportional features.
3. **ML Detection (`detector.py`):** Evaluates live data blocks against historical baselines using an unsupervised Isolation Forest model.
4. **Execution (`executor.py`):** Handles OS-level security lockdowns (e.g., triggering native workstation locks).
5. **Coordination (`coordinator.py`):** Manages multi-threaded event streams, data buffers, and operational modes (Collect vs. Verify).
6. **Daemon & Lifecycle (`daemon.py`, `main.py`):** Runs seamlessly in the background at system startup via Windows session notifications (Lock/Unlock) using `pythonw.exe`.

---

## Machine Learning Approach

This project utilizes an **Isolation Forest** (`scikit-learn`) for unsupervised anomaly detection. 

### Stable Digram Selection
Instead of analyzing every random key combination, the pipeline identifies the user's most reliable typing patterns:
* Filters out rare digrams based on frequency thresholds.
* Calculates the sum of variance across all biometric metrics for each digram.
* Isolates the most stable digrams (lowest variance).
* Supports using multiple user profiles
---

## 🔒 Security & Data Privacy

Keystroke timings are highly sensitive biometric data. This project implements strict security controls:
* **Zero Plaintext Storage:** Raw data is stored in a local SQLite database encrypted with **SQLCipher**.
* **OS-Level Key Management:** The cryptographic key is never hardcoded. It is generated securely and stored exclusively in the host operating system's native Credential Manager via the `keyring` library.
* **Active Protection & Lockdown:** Triggers native OS work-station locking (`Win+L`) upon detecting typing anomalies, user inactivity or rhythm spoofing attempts (evasion detection).
* **Offline Operation:** 100% of the computation happens locally. No data ever leaves the machine.
---

## Runtime Behavior

The daemon is designed to run transparently in the background.

- It automatically starts whenever the user unlocks the Windows session.
- On startup, it checks whether a biometric profile already exists.
- If no profile is found, it enters **Collection Mode** and records the initial typing profile.
- If one or more profiles exist, it immediately enters **Verification Mode** and continuously authenticates the active user.
- Pressing `Esc` terminates the current monitoring session. The daemon automatically starts again after the next workstation unlock.
---

## Usage

Create a new biometric profile:

```powershell
py main.py add
```
> **Note:** The `add` command is intended for enrolling additional user profiles. During normal operation, the daemon automatically enters Collection Mode if no profile exists.

Delete all stored profiles and force a new enrollment on the next launch:

```powershell
py main.py reset
```

Normal execution (background daemon):

```powershell
py main.py
```

When launched without arguments, the application runs as a background daemon. After each Windows unlock event it automatically decides whether to collect a new profile or verify an existing one.
---

### Prerequisites & Installation

1. Create and activate a virtual environment:
   ```powershell
   py -m venv venv
   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
   .\venv\Scripts\Activate.ps1
