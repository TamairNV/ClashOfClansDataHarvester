#!/bin/bash

# 1. Define a log file for the Python script ITSELF (so we can see if Python crashes)
LOGFILE="/home/tnv/Desktop/ClashOfClansDataHarvester/harvest_debug.log"
sleep 60
# 2. Go to the directory
cd /home/tnv/Desktop/ClashOfClansDataHarvester/ || exit

# 3. CRITICAL FIX: Tell screen what kind of terminal to use
export TERM=xterm

# 4. Run screen
# We modify the command to redirect Python's output to our logfile INSIDE the screen session.
# If Python crashes, the error will be in 'harvest_debug.log'
/usr/bin/screen -dmS Harvest bash -c "./venv/bin/python3 tracker.py > $LOGFILE 2>&1"

