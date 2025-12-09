from Fetcher import *
import threading
import time
from datetime import datetime

clan_tags = ["#2LRJ2888Y", "#8GGPQLPU", "#22RUUC2JC"]


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

    try:
        session = FetchSession()
        clans = []

        log(f"Initializing {len(clan_tags)} clans...")
        for c in clan_tags:
            new_clan = clan(c, session)
            clans.append(new_clan)
            log(f"-> Loaded clan: {new_clan.name} ({new_clan.clanTag})")

        # --- Define Jobs with Logging ---

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