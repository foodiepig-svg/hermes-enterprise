# Detection thresholds for Hermes Enterprise

# Lease: minimum deviation from market rate to flag (default 10%)
LEASE_MARKET_THRESHOLD = 0.10

# Lease: months before expiry to flag as at-risk (default 6)
LEASE_EXPIRY_RISK_MONTHS = 6

# AP: minimum amount match % for near-duplicate detection (default 80%)
AP_NEAR_DUPLICATE_THRESHOLD = 0.80

# AP: days early to flag suspicious early payments (default 15)
AP_EARLY_PAYMENT_DAYS = 15

# AP: % rate drift to flag vendor contract drift (default 20%)
AP_RATE_DRIFT_THRESHOLD = 0.20

# AP: % of total spend to flag vendor concentration (default 30%)
AP_VENDOR_CONCENTRATION_THRESHOLD = 0.30

# AR: days overdue to flag as high risk (default 45)
AR_HIGH_RISK_DAYS = 45

# AR: days overdue to flag as critical risk (default 60)
AR_CRITICAL_RISK_DAYS = 60

# GL: round number threshold — amounts above this with all-zero cents flag as suspicious (default 10000)
GL_ROUND_NUMBER_THRESHOLD = 10000

# GL: minimum duplicate score to flag (default 0.85)
GL_DUPLICATE_SCORE_THRESHOLD = 0.85

# LLM: model to use (grok models via Groq)
LLM_MODEL = "grok-3"
LLM_PROVIDER = "groq"

# Output
OUTPUT_DIR = "output"
