from pathlib import Path

INACTIVITY_TIME = 60
"""Time of inactivity after which the program stops automatically (seconds)"""

PAUSE_TIME = 5
"""Time between presses after which we flag that the presses have a pause between them (seconds)"""

LOG_FILE = Path("logs.csv")
"""Path to the log file"""

MAX_UNVERIFIED = 5
"""Maximum number of unverified logs to keep"""

WARN_THRESHOLD = 3
"""Number of unverified logs that triggers Executor"""

BASELINE_PATH = 'Records/baseline.csv'
"""Path to the baseline file"""

MIN_FREQ = 3
"""Number of times a key must be pressed to be considered for baseline"""