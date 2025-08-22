import json
import psycopg2
import smbus2
import time
import os
import yaml
from datetime import datetime
from bmp280 import BMP280

# 設定ファイル読み込み関数
def load_config():
    with open('config.yaml', encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_sensor_data():
    """sensor_data.jsonを読み込む"""
    file_path = os.path.join(os.path.dirname(__file__), 'sensor_data.json')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# 初回設定ファイル読み込み
config = load_config()
sensor_data = load_sensor_data()

# BMP280設定
I2C_PORT = config['I2C_PORT']
BMP280_ADDRESS = config['BMP280_ADDRESS']
bus = smbus2.SMBus(I2C_PORT)
bmp280 = BMP280(i2c_dev=bus)

# 定数（初期値）
SEA_LEVEL_PRESSURE = config['SEA_LEVEL_PRESSURE']
ELEVATION = config['ELEVATION']
RELOAD_INTERVAL = config.get('RELOAD_INTERVAL', 600)

update_sea_level_pressure = sensor_data.get('sea_level_pressure', SEA_LEVEL_PRESSURE)
update_elevation = sensor_data.get('elevation', ELEVATION)

# PostgreSQL接続情報
DB_HOST = config['DB_HOST']
DB_PORT = config['DB_PORT']
DB_NAME = config['DB_NAME']
DB_USER = config['DB_USER']
DB_PASSWORD = config['DB_PASSWORD']

# テーブル名
ALTITUDE_LOG_TABLE = config['ALTITUDE_LOG_TABLE']

def calculate_altitude_sea_level(pressure_hpa, temperature_c, sea_level_pressure):
    temperature_k = temperature_c + 273.15
    return ((((sea_level_pressure / pressure_hpa) ** 0.1903) - 1) * temperature_k) / 0.0065

def main():
    global update_sea_level_pressure, update_elevation, SEA_LEVEL_PRESSURE, ELEVATION, RELOAD_INTERVAL
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    # テーブル作成（初回のみ）
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {ALTITUDE_LOG_TABLE} (
            timestamp TIMESTAMP PRIMARY KEY,
            altitude REAL,
            temperature REAL,
            pressure REAL,
            sea_level_pressure REAL,
            elevation REAL
        )
    """)
    conn.commit()

    last_reload = time.time()
    try:
        while True:
            now_time = time.time()
            # 設定ファイルの定期再読み込み
            if now_time - last_reload >= RELOAD_INTERVAL:
                sensor_data = load_sensor_data()
                update_sea_level_pressure = sensor_data.get('sea_level_pressure', SEA_LEVEL_PRESSURE)
                update_elevation = sensor_data.get('elevation', ELEVATION)
                last_reload = now_time

            temperature = bmp280.get_temperature()  # ℃
            pressure = bmp280.get_pressure()  # hPa
            altitude = calculate_altitude_sea_level(pressure, temperature, update_sea_level_pressure)
            now = datetime.now()

            cur.execute(
                f"INSERT INTO {ALTITUDE_LOG_TABLE} (timestamp, altitude, temperature, pressure, sea_level_pressure, elevation) VALUES (%s, %s, %s, %s, %s, %s)",
                (now, altitude, temperature, pressure, update_sea_level_pressure, update_elevation)
            )
            conn.commit()
            print(f"{now} Altitude: {altitude:.2f}m, Temp: {temperature:.2f}C, Pressure: {pressure:.2f}hPa")
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()