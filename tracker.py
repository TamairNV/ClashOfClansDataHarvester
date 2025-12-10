import sys

from Fetcher import *
import threading
import time
from datetime import datetime
from Fetcher import FetchSession, clan, clanWar, warResults, attack
from TokenManager import get_valid_token # Import the helper we made in step 1
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

clan_tags = ["#9PGQPGL", "#8GGPQLPU", "#22RUUC2JC","#29U9COGLC",'#2LGGP2G82','#2RG22YYLL',
             "#2YQQQOJUP","#2LJJJ9LQO","#2QUY89R2","#2Y8G98UPU","#2G2VRCRPQ","#8U98O2JO",
             "#8RGY9RCC","#SVP9PY2U","#RVJUGOY2","#G2OGG9LJ","#G2G2JULR","#2GPLUCRLR","#JVUJR2QC"
            ,"#2GLCOG2JR","#22GOJJR8","#2RVGUQOR2","#JCCYQPYL","#2YO9JUL9R","#CPVJYJQV",
             "##2G28J89UQ","#8GR2GRJR","#2CC0CJVC","#2YVJU0GCU"]


def log(message):
    """Helper to print messages with a nice timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def run_periodically(minutes, func, job_name, *args, **kwargs):
    def loop():
        log(f"Job '{job_name}' scheduled every {minutes} min.")
        while True:
            try:
                # Run the passed function
                func(*args, **kwargs)
            except Exception as e:
                log(f"!! CRITICAL ERROR in '{job_name}': {e}")

            # Wait for the next interval
            time.sleep(minutes * 60)

    # Create and start the thread
    job_thread = threading.Thread(target=loop, daemon=True)
    job_thread.start()
    return job_thread


def main():
    log("System starting up...")

    # 1. GET THE TOKEN DYNAMICALLY
    log("Authenticating with Clash of Clans Developer Portal...")
    try:
        dotenv.load_dotenv()
        email = os.environ.get("COC_EMAIL")
        password = os.environ.get("COC_PASSWORD")

        dynamic_token = get_valid_token(email, password)
        log("Authentication successful! Token acquired.")
    except Exception as e:
        log(f"CRITICAL: Could not login to developer portal: {e}")
        return

    try:

        session = FetchSession(token=dynamic_token)

        clans = []


        log(f"Initializing {len(clan_tags)} clans...")
        for c in clan_tags:
            try:
                new_clan = clan(c, session)
                clans.append(new_clan)
                log(f"-> Loaded clan: {new_clan.name} ({new_clan.clanTag})")
            except Exception as e:
                log(f"!! Failed to load clan {c}: {e}")

        def saveActivity():
            log("Job Started: Activity Check")
            for c in clans:
                c.savePlayersActivity()
            log("Job Finished: Activity Check")

        def savePlayerData():
            log("Job Started: Player Snapshots")
            for c in clans:
                c.savePlayersSnapshot()
            log("Job Finished: Player Snapshots")

        def saveWarData():
            log("Job Started: War Status Update")
            for t in clan_tags:
                clanWar(session, t)
            log("Job Finished: War Status Update")

        def saveWarResults():
            log("Job Started: War Results Check")
            warResults.checkWarEnded(session)
            log("Job Finished: War Results Check")

        def saveWarAttacks():
            log("Job Started: Fetching New Attacks")
            attack.saveAttacks(session)
            log("Job Finished: Fetching New Attacks")

        # --- Start Scheduler ---

        log("Starting background schedulers...")

        # I added the job name as a parameter for better error logging
        run_periodically(5, saveActivity, "Activity Check")
        run_periodically(60, savePlayerData, "Player Snapshots")
        run_periodically(30, saveWarData, "War Status")
        run_periodically(5, saveWarResults, "War Results")
        run_periodically(10, saveWarAttacks, "Attack Fetcher")

        log("All systems operational. Waiting for jobs...")

        # Keep the main thread alive without burning CPU
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        log("Shutting down...")


if __name__ == '__main__':
    main()