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

    def execute(self, sql, params=None):
        with self.lock:  # <--- Lock the connection during execution
            cursor = self.conn.cursor()
            try:
                cursor.execute(sql, params or ())
                if sql.strip().upper().startswith("SELECT"):
                    result = cursor.fetchall()
                    cursor.close()
                    return result
                else:
                    # self.conn.commit() # Not needed if autocommit=True
                    rows = cursor.rowcount
                    cursor.close()
                    return rows
            except mariadb.Error as e:
                print(f"Query Error: {e}")
                return None

    def close(self):
        self.conn.close()