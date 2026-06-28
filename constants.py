from pathlib import Path

INACTIVITY_TIME = 900
"""Time of inactivity after which the keystroke gathering stops automatically (seconds)"""

PAUSE_TIME = 1
"""Time between presses after which we flag that the presses have a pause between them (seconds)"""

LOG_FILE = Path("logs.csv")
"""Path to the log file"""

MAX_UNVERIFIED = 5
"""Maximum number of unverified logs to keep"""

WARN_THRESHOLD = 3

"""Number of unverified logs that triggers Executor"""
BASELINE_PATH = 'Records/baseline.csv'

MIN_FREQ = 3