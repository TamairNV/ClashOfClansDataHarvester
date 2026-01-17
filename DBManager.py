import mariadb
import sys
import threading  # <--- Import this


class DBManager:
    def __init__(self, host, user, password, database):
        self.lock = threading.Lock()  # <--- Create a Lock
        try:
            self.conn = mariadb.connect(
                host=host,
                user=user,
                password=password,
                database=database
            )
            self.conn.autocommit = True  # Helps with threading
        except mariadb.Error as e:
            print(f"Error connecting to MariaDB: {e}")
            sys.exit(1)

    def execute(self, query, params=None):
        try:
            # 1. PING: Check if connection is alive. Reconnect if dead.
            self.conn.ping(reconnect=True)
        except Exception as e:
            print(f"DB Connection Lost. Reconnecting... ({e})")
            try:
                # 2. HARD RECONNECT: Rerun the connect logic
                self.conn = mariadb.connect(
                    host=self.host, user=self.user,
                    password=self.password, database=self.database
                )
                self.conn.autocommit = True
            except Exception as e2:
                print(f"Reconnect failed: {e2}")
                return None  # Fail gracefully, don't crash

        # 3. Normal Execution
        cursor = self.conn.cursor()
        try:
            cursor.execute(query, params or ())
            if query.strip().upper().startswith("SELECT"):
                return cursor.fetchall()
            return cursor.lastrowid
        except Exception as e:
            print(f"Query Error: {e}")
            return None
        finally:
            cursor.close()

    def close(self):
        self.conn.close()