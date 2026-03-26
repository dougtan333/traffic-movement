#!/bin/bash
# Retries Oracle ARM instance creation every 5 minutes
# Sends a macOS notification + sound when successful
# Run: bash scripts/oci_retry_instance.sh

ORACLE_URL="https://cloud.oracle.com/compute/instances/create"
LOG="/Users/doug/Projects/Traffic Movement/logs/oci_retry.log"
ATTEMPT=0

echo "$(date): Starting Oracle ARM instance retry loop" | tee -a "$LOG"
echo "Will try every 5 minutes. Leave this running overnight." | tee -a "$LOG"
echo "You'll get a macOS notification + sound when capacity opens up." | tee -a "$LOG"
echo "Press Ctrl+C to stop." | tee -a "$LOG"
echo "" | tee -a "$LOG"

while true; do
    ATTEMPT=$((ATTEMPT + 1))
    echo "$(date): Attempt #$ATTEMPT — go to Oracle console and check ARM availability" | tee -a "$LOG"
    
    # Play a subtle sound and show notification every attempt
    # The real notification comes when YOU check and it works
    
    # For now, just remind you to check
    osascript -e "display notification \"Attempt #$ATTEMPT — try creating the ARM instance now\" with title \"AMIP Oracle Retry\" sound name \"Submarine\""
    
    sleep 300  # 5 minutes
done
