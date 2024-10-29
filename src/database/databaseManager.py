import json

import psycopg2

from src.settings.filepaths import DB_SETTINGS_PATH


class DatabaseManager:
    def __init__(self, db_name):
        self.settings = self.load_db_settings(db_name)

        self.connection = psycopg2.connect(
            user=self.settings['DB_USER'],
            password=self.settings['DB_PASSWORD'],
            host=self.settings['DB_HOST'],
            port=self.settings['DB_PORT'],
            database=self.settings['DB']
        )

    @staticmethod
    def load_db_settings(db_name):
        with open(DB_SETTINGS_PATH, "r") as f:
            databases = json.load(f)
            settings = databases[db_name]
            return settings

    def execute_query(self, query):
        cursor = self.connection.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        return result


if __name__ == "__main__":
    db_manager = DatabaseManager('TPC-H')
    res = db_manager.execute_query("SELECT * FROM nation LIMIT 10")
    print(res)