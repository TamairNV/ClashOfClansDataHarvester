import os

from dotenv import load_dotenv

from DBManager import DBManager
from Fetcher import warResults, FetchSession

load_dotenv()
host = os.environ.get("DB_HOST")
password = os.environ.get("DB_PASSWORD")
user = os.environ.get("DB_USER")
db_name = os.environ.get("DB_NAME")

print(f"🔌 Connecting to database: {db_name}...")
print(host,user,password,db_name)
db = DBManager(host, user, password, db_name)

print(db.execute("SELECT COUNT(*) FROM Attack"))
warResults.checkWarEnded(FetchSession())