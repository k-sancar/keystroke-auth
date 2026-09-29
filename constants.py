INACTIVITY_TIME = 60
"""Time of inactivity after which the program stops automatically (seconds)"""

PAUSE_TIME = 5
"""Time between presses after which we flag that the presses have a pause between them (seconds)"""

MAX_UNVERIFIED = 5
"""Maximum number of unverified logs to keep"""

WARN_THRESHOLD = 4
"""Number of unverified logs that triggers Executor"""

MIN_FREQ = 3
"""Number of times a key must be pressed to be considered for baseline"""

SESSION_FEATURE_WINDOW = 3
"""Window containing last N values of a feature to be used for median calculation"""

MIN_PAUSE_HISTORY = 3
"""Minimum number of recent pauses to consider for outlier detection"""

PAUSE_WINDOW = 20
"""Window containing information about pauses between key presses"""

OUTLIER_THRESHOLD = 10
"""Number of outlier pauses that triggers Executor"""

MAX_CONTAMINATION_RATIO = 0.2
"""Maximum allowed contamination ratio for the Isolation Forest model"""

APP_NAME = "KeystrokeSecurityDaemon"
"""Name of the application for autostart in Windows Registry"""

KEYRING_USER_KEY = "db_encryption_key"

DIR_NAME = ".keystroke_auth"
"""Directory name for storing baseline records and logs"""

LOG_FILE = "daemon_background.log"
"""Log file name for daemon background process"""

DB_FILE = "baseline_records.db"
"""Database file name for storing baseline records"""

BASELINE_TABLE_PREFIX = "raw_baseline"
"""Prefix for baseline table names"""

BLOCK_SIZE = 50
"""Number of keys to compose a block"""

MIN_DIGRAMS = 2
"""Minimum number of dynamic digrams to consider"""

DIGRAM_SCALING_FACTOR = 300
"""Scaling factor for determining the number of digrams to select based on the number of unique digrams"""

MAX_DIGRAMS = 12 
"""Hard maximum number of digrams to select for the feature set"""

COLLECTION_THRESHOLD = 1050
"""Number of records required to be collected before processing and storing in the database"""

VERIFICATION_BUFFER_SIZE = 5
"""Number of blocks to keep in the verification buffer before processing and verifying user identity"""

RETRAIN_BLOCK_INTERVAL = 50
"""Number of blocks after which the model should be retrained with new data"""

STABLE_DIGRAM_QUANTILE = 0.25
"""Quantile for determining stable digrams based on variance"""