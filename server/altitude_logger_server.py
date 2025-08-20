import time
import grpc
import os
import psycopg2
import sys
import yaml

from concurrent import futures
from datetime import datetime
from psycopg2 import sql

sys.path.append(os.path.join(os.path.dirname(__file__), '../proto'))
import altitude_logger_pb2
import altitude_logger_pb2_grpc

# 設定ファイル読み込み関数
def load_config():
    with open('config.yaml', encoding='utf-8') as f:
        return yaml.safe_load(f)

# 設定ファイル読み込み
config = load_config()

PORT = config['PORT']
SLEEP_TIME = config['SLEEP_TIME']
AUTH_MODE = config['AUTH_MODE']

# PostgreSQL接続情報
DB_HOST = config['DB_HOST']
DB_PORT = config['DB_PORT']
DB_NAME = config['DB_NAME']
DB_USER = config['DB_USER']
DB_PASSWORD = config['DB_PASSWORD']
ALTITUDE_LOG_TABLE = config['ALTITUDE_LOG_TABLE']
ACCESS_KEYS_TABLE = config['ACCESS_KEYS_TABLE']

# アクセスキーの有効性をDBから判定
def is_valid_access_key(access_key):
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        with conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {ACCESS_KEYS_TABLE} (
                    id SERIAL PRIMARY KEY,
                    access_key VARCHAR(128) UNIQUE NOT NULL,
                    description VARCHAR(256),
                    enabled BOOLEAN DEFAULT TRUE
                )
            """)
            base_query = sql.SQL("SELECT enabled FROM {} WHERE access_key = %s").format(
                sql.Identifier(ACCESS_KEYS_TABLE)
            )
            cur.execute(base_query, (access_key,))
            row = cur.fetchone()
        return bool(row) and row[0] is True
    except Exception as e:
        print(f"[ACCESS KEY CHECK ERROR] {e}", flush=True)
        return False
    finally:
        if conn:
            conn.close()

def fetch_altitude_logs(start_dt=None, end_dt=None):
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        with conn.cursor() as cur:
            base_query = sql.SQL("SELECT timestamp, altitude, temperature, pressure, sea_level_pressure, elevation FROM {}").format(
                                                        sql.Identifier(ALTITUDE_LOG_TABLE))
            where_clauses = []
            params = []
            if start_dt:
                where_clauses.append(sql.SQL("timestamp >= %s"))
                params.append(start_dt)
            if end_dt:
                where_clauses.append(sql.SQL("timestamp <= %s"))
                params.append(end_dt)
            if where_clauses:
                base_query = base_query + sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_clauses)
            base_query = base_query + sql.SQL(" ORDER BY timestamp ASC")
            cur.execute(base_query, params)
            results = cur.fetchall()
            return results
    except Exception as e:
        return []
    finally:
        if conn:
            conn.close()

class AltitudeLoggerServicer(altitude_logger_pb2_grpc.AltitudeLoggerServicer):
    def GetAltitudeLog(self, request, context):
        # クライアントIP取得
        import urllib.parse
        ip_addr = None
        try:
            peer = context.peer()
            if 'ipv4:' in peer:
                ip_and_port = peer.split('ipv4:', 1)[1]
                ip_part = ip_and_port.rsplit(':', 1)[0]
                ip_addr = urllib.parse.unquote(ip_part)
            elif 'ipv6:' in peer:
                ip_and_port = peer.split('ipv6:', 1)[1]
                ip_part = ip_and_port.rsplit(':', 1)[0]
                ip_addr = urllib.parse.unquote(ip_part.strip('[]'))
        except Exception:
            ip_addr = None

        # アクセスキー検証（DBから有効なもののみ許可）
        if not is_valid_access_key(request.access_key):
            print(f"[DEBUG] Logging access failure: ip={ip_addr}, key={request.access_key}", flush=True)
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            context.set_details('Invalid access key')
            return altitude_logger_pb2.AltitudeLogResponse()
        # 日時パース
        start_dt = None
        end_dt = None
        dt_format = "%Y/%m/%d %H:%M:%S"
        try:
            if request.start_datetime:
                start_dt = datetime.strptime(request.start_datetime, dt_format)
            if request.end_datetime:
                end_dt = datetime.strptime(request.end_datetime, dt_format)
        except Exception:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details('Invalid datetime format')
            return altitude_logger_pb2.AltitudeLogResponse()
        logs = fetch_altitude_logs(start_dt, end_dt)
        response = altitude_logger_pb2.AltitudeLogResponse()
        for row in logs:
            response.logs.append(
                altitude_logger_pb2.AltitudeData(
                    datetime=row[0].strftime("%Y/%m/%d %H:%M:%S"),
                    altitude=row[1],
                    temperature=row[2],
                    pressure=row[3],
                    sea_level_pressure=row[4],
                    elevation=row[5]
                )
            )
        return response

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    altitude_logger_pb2_grpc.add_AltitudeLoggerServicer_to_server(AltitudeLoggerServicer(), server)

    if AUTH_MODE == 'none':
        server.add_insecure_port(f'[::]:{PORT}')
        print(f"gRPC server started (no TLS) on port {PORT}.")
    elif AUTH_MODE == 'tls':
        with open(os.path.join("certs", "server.crt"), "rb") as f:
            server_cert = f.read()
        with open(os.path.join("certs", "server.key"), "rb") as f:
            server_key = f.read()
        with open(os.path.join("certs", "ca.crt"), "rb") as f:
            ca_cert = f.read()
        server_credentials = grpc.ssl_server_credentials(
            [(server_key, server_cert)],
            root_certificates=ca_cert,
            require_client_auth=False
        )
        server.add_secure_port(f'[::]:{PORT}', server_credentials)
        print(f"gRPC TLS server started on port {PORT}.")
    elif AUTH_MODE == 'mtls':
        with open(os.path.join("certs", "server.crt"), "rb") as f:
            server_cert = f.read()
        with open(os.path.join("certs", "server.key"), "rb") as f:
            server_key = f.read()
        with open(os.path.join("certs", "ca.crt"), "rb") as f:
            ca_cert = f.read()
        server_credentials = grpc.ssl_server_credentials(
            [(server_key, server_cert)],
            root_certificates=ca_cert,
            require_client_auth=True
        )
        server.add_secure_port(f'[::]:{PORT}', server_credentials)
        print(f"gRPC mTLS server started on port {PORT}.")
    else:
        raise Exception(f"不明なAUTH_MODE: {AUTH_MODE}")

    server.start()
    try:
        while True:
            time.sleep(SLEEP_TIME)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    serve()
