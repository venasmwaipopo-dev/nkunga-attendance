import pymysql
import urllib.parse
import os
from dotenv import load_dotenv

load_dotenv()

url = urllib.parse.urlparse(os.getenv("MYSQL_PUBLIC_URL"))

try:
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
    result = cursor.fetchone()

    print("✅ CONNECTED SUCCESSFULLY!")
    print("DATABASE:", result)

    conn.close()

except Exception as e:
    print("❌ CONNECTION FAILED:")
    print(e)