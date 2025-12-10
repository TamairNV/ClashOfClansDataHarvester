#!/bin/bash


# 2. Define Log File (Hardcoded full path is safer)
LOGFILE="/home/tnv/Desktop/ClashOfClansDataHarvester/harvest_debug.log"

# 3. Move to directory
cd /home/tnv/Desktop/ClashOfClansDataHarvester/ || exit

# 4. Set Terminal
export TERM=xterm

# 5. Initialization Timestamp (Writes directly to file, bypassing Python)
echo "--- NEW REBOOT SESSION STARTED AT $(date) ---" >> "$LOGFILE"

# 6. Run Screen
# The -u flag forces Python to print immediately.
/usr/bin/screen -dmS Harvest bash -c "./venv/bin/python3 -u tracker.py 2>&1 | tee -a $LOGFILE"