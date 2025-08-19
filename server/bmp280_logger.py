import bme280
import psycopg2
import smbus2
import time
import yaml
from datetime import datetime

# 設定ファイル読み込み関数
def load_config():
    with open('config.yaml', encoding='utf-8') as f:
        return yaml.safe_load(f)

# 初回設定ファイル読み込み
config = load_config()

# BME280設定
I2C_PORT = config['I2C_PORT']
BME280_ADDRESS = config['BME280_ADDRESS']
bus = smbus2.SMBus(I2C_PORT)
calibration_params = bme280.load_calibration_params(bus, BME280_ADDRESS)

# 定数（初期値）
SEA_LEVEL_PRESSURE = config['SEA_LEVEL_PRESSURE']
ELEVATION = config['ELEVATION']
RELOAD_INTERVAL = config.get('RELOAD_INTERVAL', 600)

# PostgreSQL接続情報
DB_HOST = config['DB_HOST']
DB_PORT = config['DB_PORT']
DB_NAME = config['DB_NAME']
DB_USER = config['DB_USER']
DB_PASSWORD = config['DB_PASSWORD']

# テーブル名
TABLE_NAME = config['TABLE_NAME']

def calculate_altitude_sea_level(pressure_hpa, temperature_c, sea_level_pressure):
    temperature_k = temperature_c + 273.15
    return ((((sea_level_pressure / pressure_hpa) ** 0.1903) - 1) * temperature_k) / 0.0065

def main():
    global SEA_LEVEL_PRESSURE, ELEVATION, RELOAD_INTERVAL
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    # テーブル作成（初回のみ）
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
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
                config = load_config()
                SEA_LEVEL_PRESSURE = config['SEA_LEVEL_PRESSURE']
                ELEVATION = config['ELEVATION']
                RELOAD_INTERVAL = config.get('RELOAD_INTERVAL', 600)
                last_reload = now_time

            data = bme280.sample(bus, BME280_ADDRESS, calibration_params)
            temperature = data.temperature  # ℃
            pressure = data.pressure  # hPa
            altitude = calculate_altitude_sea_level(pressure, temperature, SEA_LEVEL_PRESSURE)
            now = datetime.now()

            cur.execute(
                f"INSERT INTO {TABLE_NAME} (timestamp, altitude, temperature, pressure, sea_level_pressure, elevation) VALUES (%s, %s, %s, %s, %s, %s)",
                (now, altitude, temperature, pressure, SEA_LEVEL_PRESSURE, ELEVATION)
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