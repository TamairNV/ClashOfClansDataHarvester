import sys
import os
import time
import socket
import threading
import asyncio
import dotenv
from datetime import datetime

# Path setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Fetcher import FetchSession, clan, clanWar, warResults, attack

# --- CONFIG ---
clan_tags = [
    "#9PGQPGL", "#8GGPQLPU", "#22RUUC2JC", "#29U9C0GLC", '#2LGGP2G82', '#2RG22YYLL',
    "#2YQQQ0JUP", "#2LJJJ9LQ0", "#2QUY89R2", "#2Y8G98UPU", "#2G2VRCRPQ", "#8U9802J0",
    "#8RGY9RCC", "#RVJUG0Y2", "#G20GG9LJ", "#G2G2JULR", "#2GPLUCRLR", "#JVUJR2QC",
    "#2GLC0G2JR", "#22G0JJR8", "#2RVGUQ0R2", "#JCCYQPYL", "#2Y09JUL9R", "#CPVJYJQV",
    "#2G28J89UQ", "#8GR2GRJR", "#2CC0CJVC", "#2YVJU0GCU"
]
internet_event = threading.Event()


def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def check_internet_connection(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False


def get_valid_token():
    # Helper for asyncio loop
    async def fetch():
        dotenv.load_dotenv()
        email = os.environ.get("COC_EMAIL")
        password = os.environ.get("COC_PASSWORD")
        import coc
        async with coc.Client() as client:
            await client.login(email, password)
            http = client.http
            if hasattr(http, 'keys'):
                return next(iter(http.keys))
            raise Exception("No API keys found.")

    return asyncio.run(fetch())


def run_job_safe(interval_minutes, func, job_name):

    log(f"Thread '{job_name}' initialized.")

    while True:

        internet_event.wait()

        try:
            # 2. Execute the job
            func()

        except Exception as e:
            log(f"!! Error in '{job_name}': {e}")
            # We don't exit. We just log and sleep.

        # 3. Sleep for the interval
        time.sleep(interval_minutes * 60)


def main():
    log("=== CLASH HARVESTER STARTED (Pure Python Mode) ===")

    # 1. Initial Internet Wait
    while not check_internet_connection():
        log("Waiting for internet to start...")
        time.sleep(10)

    internet_event.set()  # Green light!

    # 2. Initialize Session
    try:
        token = get_valid_token()
        session = FetchSession(token=token)
    except Exception as e:
        log(f"CRITICAL: Failed to get initial token: {e}")
        # In a real infinite script, we might want to loop here too,
        # but if we can't login at boot, something is wrong with config.
        sys.exit(1)

    # 3. Initialize Clans
    clans = []
    log(f"Loading {len(clan_tags)} clans...")
    for tag in clan_tags:
        try:
            clans.append(clan(tag, session))
        except Exception as e:
            log(f"Skipping clan {tag}: {e}")

    # 4. Define Job Wrappers
    def job_activity():
        for c in clans: c.savePlayersActivity()

    def job_snapshot():
        for c in clans: c.savePlayersSnapshot()

    def job_war_status():
        for t in clan_tags: clanWar(session, t)

    def job_war_results():
        warResults.checkWarEnded(session)

    def job_attacks():
        attack.saveAttacks(session)

    # 5. Launch Threads (Daemon=True ensures they die if main script is killed)
    threading.Thread(target=run_job_safe, args=(5, job_activity, "Activity"), daemon=True).start()
    threading.Thread(target=run_job_safe, args=(60, job_snapshot, "Snapshot"), daemon=True).start()
    threading.Thread(target=run_job_safe, args=(30, job_war_status, "WarStatus"), daemon=True).start()
    threading.Thread(target=run_job_safe, args=(5, job_war_results, "WarResults"), daemon=True).start()
    threading.Thread(target=run_job_safe, args=(10, job_attacks, "Attacks"), daemon=True).start()

    log("All systems GO. Monitoring connection...")

    # 6. Infinite Watchdog Loop
    while True:
        time.sleep(10)

        is_connected = check_internet_connection()

        if is_connected and not internet_event.is_set():
            log("Internet RESTORED. Resuming threads.")
            internet_event.set()  # Wake up all threads


        elif not is_connected and internet_event.is_set():
            log("!! Internet LOST. Pausing threads.")
            internet_event.clear()  # Freeze all threads


if __name__ == '__main__':
    main()