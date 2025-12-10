import sys
import os
import time
import socket
import threading
import asyncio
import coc
import dotenv
from datetime import datetime

# 1. Adjust Path to find local modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 2. Local Imports
from Fetcher import FetchSession, clan, clanWar, warResults, attack


clan_tags = [
    "#9PGQPGL", "#8GGPQLPU", "#22RUUC2JC", "#29U9COGLC", '#2LGGP2G82', '#2RG22YYLL',
    "#2YQQQOJUP", "#2LJJJ9LQO", "#2QUY89R2", "#2Y8G98UPU", "#2G2VRCRPQ", "#8U98O2JO",
    "#8RGY9RCC", "#SVP9PY2U", "#RVJUGOY2", "#G2OGG9LJ", "#G2G2JULR", "#2GPLUCRLR", "#JVUJR2QC",
    "#2GLCOG2JR", "#22GOJJR8", "#2RVGUQOR2", "#JCCYQPYL", "#2YO9JUL9R", "#CPVJYJQV",
    "##2G28J89UQ", "#8GR2GRJR", "#2CC0CJVC", "#2YVJU0GCU"
]


def log(message):
    """Helper to print messages with a nice timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def check_internet_connection(host="8.8.8.8", port=53, timeout=3):

    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False


def get_valid_token():

    async def fetch():
        dotenv.load_dotenv()
        email = os.environ.get("COC_EMAIL")
        password = os.environ.get("COC_PASSWORD")

        async with coc.Client() as client:

            await client.login(email, password)

            http = client.http
            if hasattr(http, 'keys'):
                # Return the first available key
                return next(iter(http.keys))

            raise Exception("Login successful, but no API keys found.")

    return asyncio.run(fetch())


def get_valid_token_robust():

    while True:
        try:
            log("Attempting to acquire API Token...")
            if not check_internet_connection():
                log("!! No Internet Connection. Retrying in 10s...")
                time.sleep(10)
                continue

            token = get_valid_token()
            return token

        except Exception as e:
            log(f"!! Error acquiring token: {e}")
            log("Retrying in 10s...")
            time.sleep(10)


def run_periodically(minutes, func, job_name, *args, **kwargs):

    def loop():
        log(f"Job '{job_name}' scheduled every {minutes} min.")
        while True:
            try:
                func(*args, **kwargs)
            except Exception as e:
                log(f"!! CRITICAL ERROR in '{job_name}': {e}")

            # Wait for the next interval
            time.sleep(minutes * 60)

    job_thread = threading.Thread(target=loop, daemon=True)
    job_thread.start()
    return job_thread


def run_bot_logic():

    try:

        dynamic_token = get_valid_token_robust()
        log("Authentication successful! Token acquired.")

        # 2. SETUP SESSION
        clans = []
        session = FetchSession(token=dynamic_token)

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

        # 4. START SCHEDULER
        log("Starting background schedulers...")
        run_periodically(5, saveActivity, "Activity Check")
        run_periodically(60, savePlayerData, "Player Snapshots")
        run_periodically(30, saveWarData, "War Status")
        run_periodically(5, saveWarResults, "War Results")
        run_periodically(10, saveWarAttacks, "Attack Fetcher")

        log("All systems operational. Entering Watchdog Loop...")

        # 5. WATCHDOG LOOP
        while True:
            time.sleep(5)
            # Check for internet loss
            if not check_internet_connection():
                log("CRITICAL: Internet Connection Lost! Restarting bot to refresh session...")
                return False  # Trigger restart

    except KeyboardInterrupt:
        log("Shutting down...")
        return True  # Exit cleanly
    except Exception as e:
        log(f"CRITICAL ERROR in main loop: {e}")
        return False  # Trigger restart


def main():

    while True:
        should_exit = run_bot_logic()

        if should_exit:
            break

        log("System restarting in 5 seconds...")
        time.sleep(5)


if __name__ == '__main__':
    main()