import sqlite3

DB_FILE = "sensor_data.db"


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT,
                tank_level REAL,
                system_status TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def insert_sensor_data(sensor_id, tank_level, system_status):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sensor_data (sensor_id, tank_level, system_status)
            VALUES (?, ?, ?)
        """,
            (sensor_id, tank_level, system_status),
        )
        conn.commit()
