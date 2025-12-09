import mariadb
import sys


class DBManager:
    def __init__(self, host, user, password, database):
        try:
            self.conn = mariadb.connect(
                host=host,
                user=user,
                password=password,
                database=database
            )
        except mariadb.Error as e:
            print(f"Error connecting to MariaDB: {e}")
            sys.exit(1)

    def execute(self, sql, params=None):
        """
        Executes a query.
        Returns list of tuples for SELECT.
        Returns row count for INSERT/UPDATE/DELETE.
        """
        cursor = self.conn.cursor()
        try:
            # params should be a tuple, e.g., (value1, value2)
            cursor.execute(sql, params or ())

            # Check if it's a read operation
            if sql.strip().upper().startswith("SELECT"):
                result = cursor.fetchall()
                cursor.close()
                return result

            # For write operations
            else:
                self.conn.commit()
                rows = cursor.rowcount
                cursor.close()
                return rows

        except mariadb.Error as e:
            print(f"Query Error: {e}")
            return None

    def close(self):
        self.conn.close()