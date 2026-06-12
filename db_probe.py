import pymysql
import urllib.parse
import os
from dotenv import load_dotenv

load_dotenv()

url = urllib.parse.urlparse(os.getenv("MYSQL_PUBLIC_URL"))

conn = pymysql.connect(
    host=url.hostname,
    user=url.username,
    password=url.password,
    database=url.path.replace("/", ""),
    port=int(url.port),
    cursorclass=pymysql.cursors.DictCursor
)

cursor = conn.cursor()

cursor.execute("SELECT DATABASE()")
print("DATABASE:", cursor.fetchone())

cursor.execute("SELECT * FROM teachers")
print("TEACHERS:", cursor.fetchall())

conn.close()