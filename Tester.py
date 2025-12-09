import os
from dotenv import load_dotenv
from DBManager import DBManager

# ANSI Colors for pretty output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


class DataValidator:
    def __init__(self):
        load_dotenv()
        host = os.environ.get("DB_HOST")
        password = os.environ.get("DB_PASSWORD")
        user = os.environ.get("DB_USER")
        db_name = os.environ.get("DB_NAME")

        print(f"🔌 Connecting to database: {db_name}...")
        self.db = DBManager(host, user, password, db_name)

    def log(self, status, message, count=0):
        if status == "PASS":
            print(f"[{GREEN}PASS{RESET}] {message}")
        elif status == "FAIL":
            print(f"[{RED}FAIL{RESET}] {message} (Found: {count})")
        elif status == "WARN":
            print(f"[{YELLOW}WARN{RESET}] {message} (Found: {count})")

    def run_check(self, name, sql, description, severity="FAIL"):
        """
        Generic function to run a SQL check.
        If count > 0, it logs a FAIL or WARN.
        """
        try:
            # We assume the SQL query returns a COUNT of bad records
            result = self.db.execute(sql)
            bad_count = result[0][0]

            if bad_count == 0:
                self.log("PASS", name)
            else:
                self.log(severity, f"{name}: {description}", bad_count)
        except Exception as e:
            print(f"[{RED}ERROR{RESET}] Could not run check '{name}': {e}")

    def validate_all(self):
        print("\n--- 🔍 STARTING DATA VALIDATION ---\n")

        # --- 1. LOGICAL CHECKS (Impossible Values) ---
        self.run_check(
            "Attack Stars Range",
            "SELECT count(*) FROM Attack WHERE stars < 0 OR stars > 3;",
            "Attacks found with < 0 or > 3 stars."
        )

        self.run_check(
            "Attack Destruction Range",
            "SELECT count(*) FROM Attack WHERE destruction < 0 OR destruction > 100;",
            "Attacks found with invalid destruction %."
        )

        self.run_check(
            "Self-Attacks",
            "SELECT count(*) FROM Attack WHERE attackerTag = defenderTag;",
            "Players attacking themselves."
        )

        self.run_check(
            "War Time Logic",
            "SELECT count(*) FROM ClanWar WHERE endTime < startTime;",
            "Wars where End Time is before Start Time."
        )

        # --- 2. INTEGRITY CHECKS (Missing Links) ---
        self.run_check(
            "Orphaned Attacks",
            """
            SELECT count(*) FROM Attack a 
            LEFT JOIN WarPlayer wp ON a.attackerTag = wp.playerTag AND a.warID = wp.warID 
            WHERE wp.playerTag IS NULL;
            """,
            "Attacks linking to a player not in the WarPlayer roster."
        )

        self.run_check(
            "Orphaned Snapshots",
            """
            SELECT count(*) FROM PlayerSnapshot ps 
            LEFT JOIN Player p ON ps.playerTag = p.playerTag 
            WHERE p.playerTag IS NULL;
            """,
            "Player snapshots that exist for a deleted/missing Player."
        )

        # --- 3. WAR COMPLETION CHECKS ---
        self.run_check(
            "Missing War Results",
            """
            SELECT count(*) FROM ClanWar cw 
            LEFT JOIN WarResults wr ON cw.warID = wr.warID 
            WHERE cw.state = 'warEnded' AND wr.warID IS NULL;
            """,
            "Ended wars that have no final results calculated.",
            severity="WARN"
        )

        self.run_check(
            "Impossible War Scores",
            """
            SELECT count(*) FROM WarResults 
            WHERE totalStars > (SELECT teamSize * 3 FROM ClanWar WHERE ClanWar.warID = WarResults.warID);
            """,
            "War Results where stars exceed maximum possible (TeamSize * 3)."
        )

        # --- 4. DUPLICATE CHECKS ---
        self.run_check(
            "Duplicate Active Wars",
            """
            SELECT count(*) FROM (
                SELECT clanTag1, count(*) as c FROM ClanWar 
                WHERE state = 'inWar' 
                GROUP BY clanTag1 HAVING c > 1
            ) as sub;
            """,
            "Clans marked as 'inWar' multiple times simultaneously."
        )

        print("\n--- ✅ VALIDATION COMPLETE ---\n")


if __name__ == "__main__":
    validator = DataValidator()
    validator.validate_all()