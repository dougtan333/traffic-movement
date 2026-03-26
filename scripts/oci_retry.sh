#!/bin/bash
# Oracle Cloud ARM Instance Auto-Retry
# Tries to create the AMIP ARM instance every 5 minutes
# Sends a macOS notification + sound when successful
# Run: bash /Users/doug/Projects/Traffic\ Movement/scripts/oci_retry.sh

set -euo pipefail

# --- Config ---
COMPARTMENT="ocid1.tenancy.oc1..aaaaaaaagv2li7ws3xahfmqoqpuusgak7vvgsx43htu6qf7vkuep75dv4rpa"
AD="oqzU:AP-MELBOURNE-1-AD-1"
SUBNET="ocid1.subnet.oc1.ap-melbourne-1.aaaaaaaak6rikhdsorn3zi7pqfjzyy5jeqpgbum35xdot6ba42mazwelqtja"
IMAGE="ocid1.image.oc1.ap-melbourne-1.aaaaaaaaimfxx3irwscxoedb26cempjgkrjhsifv743ikwankwcmxem6nuoq"
SHAPE="VM.Standard.A1.Flex"
SSH_KEY_FILE="/Users/doug/.ssh/oracle_amip.pub"
DISPLAY_NAME="amip"
OCPUS=4
MEMORY_GB=24
INTERVAL=2700  # 45 minutes

LOG="/Users/doug/Projects/Traffic Movement/logs/oci_retry.log"
SSH_KEY=$(cat "$SSH_KEY_FILE")
ATTEMPT=0

echo "========================================" | tee -a "$LOG"
echo "$(date): AMIP Oracle ARM Instance Retry" | tee -a "$LOG"
echo "Trying every $((INTERVAL/60)) minutes"   | tee -a "$LOG"
echo "Press Ctrl+C to stop"                     | tee -a "$LOG"
echo "========================================" | tee -a "$LOG"

while true; do
    ATTEMPT=$((ATTEMPT + 1))
    echo "" | tee -a "$LOG"
    echo "$(date): Attempt #$ATTEMPT" | tee -a "$LOG"

    RESULT=$(oci compute instance launch \
        --compartment-id "$COMPARTMENT" \
        --availability-domain "$AD" \
        --subnet-id "$SUBNET" \
        --image-id "$IMAGE" \
        --shape "$SHAPE" \
        --display-name "$DISPLAY_NAME" \
        --assign-public-ip true \
        --shape-config "{\"ocpus\": $OCPUS, \"memoryInGBs\": $MEMORY_GB}" \
        --ssh-authorized-keys-file "$SSH_KEY_FILE" \
        --output json 2>&1) || true

    if echo "$RESULT" | grep -q '"lifecycle-state"'; then
        # SUCCESS!
        PUBLIC_IP=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['data'].get('public-ip','pending'))" 2>/dev/null || echo "pending")
        INSTANCE_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])" 2>/dev/null || echo "unknown")

        echo "" | tee -a "$LOG"
        echo "============================================" | tee -a "$LOG"
        echo "SUCCESS! Instance created on attempt #$ATTEMPT" | tee -a "$LOG"
        echo "Instance ID: $INSTANCE_ID" | tee -a "$LOG"
        echo "Public IP: $PUBLIC_IP" | tee -a "$LOG"
        echo "============================================" | tee -a "$LOG"
        echo "$RESULT" >> "$LOG"

        # macOS notification with sound
        osascript -e "display notification \"ARM instance created! Check the log for details.\" with title \"AMIP Oracle SUCCESS\" sound name \"Glass\""
        # Also say it out loud
        say "AMIP Oracle instance created successfully"

        echo ""
        echo "Instance is provisioning. Get the public IP with:"
        echo "  oci compute instance list-vnics --instance-id $INSTANCE_ID | grep public-ip"
        echo ""
        echo "Then SSH in with:"
        echo "  ssh -i ~/.ssh/oracle_amip ubuntu@<PUBLIC_IP>"
        exit 0
    fi

    # Failed — check why
    if echo "$RESULT" | grep -q "Out of capacity"; then
        echo "  Out of capacity — will retry in $((INTERVAL/60)) min" | tee -a "$LOG"
    elif echo "$RESULT" | grep -q "LimitExceeded"; then
        echo "  Limit exceeded — instance may already exist! Check console." | tee -a "$LOG"
        osascript -e "display notification \"Limit exceeded — check if instance exists\" with title \"AMIP Oracle\" sound name \"Submarine\""
        exit 1
    elif echo "$RESULT" | grep -q "NotAuthorized\|NotAuthenticated"; then
        echo "  Auth error — check OCI config" | tee -a "$LOG"
        echo "  $RESULT" | head -5 | tee -a "$LOG"
        exit 1
    else
        echo "  Other error — will retry" | tee -a "$LOG"
        echo "  $(echo "$RESULT" | grep -o '"message":[^,]*' | head -1)" | tee -a "$LOG"
    fi

    sleep $INTERVAL
done
