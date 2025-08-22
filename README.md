# AltitudeLogger

ラズパイ + BMP280で高度ロガー

端末 Raspberry Pi 4 ModelB  
センサー BMP280  
<img width="378" height="371" alt="AltitudeLogger_1" src="https://github.com/user-attachments/assets/7d063d7c-5b44-4635-a5ef-69516285e388" />

Raspberry Pi OS 64bit  
(Raspberry Pi Imager使用)

ラズパイの設定などは  
https://github.com/MementoMori-Entangle/DecibelMonitoringService  
をベースとしています。  
I2Cを使用するので、raspi-configでI2Cを有効化

# server
開発環境  
　Python 3.13.3  
　PostgreSQL 17.5 on x86_64-windows, compiled by msvc-19.44.35209, 64-bit  
　gRPC grpcio 1.73.1

実行環境  
　Python 3.11.2  
　psql (PostgreSQL) 15.13 (Debian 15.13-0+deb12u1)  
　gRPC grpcio 1.73.1

1. venvを作成  
python3 -m venv bmp280 --system-site-packages

2. 仮想環境を有効化  
source bmp280/bin/activate

3. 仮想環境でpip install  
pip install bmp280 psycopg2 smbus2 pyyaml  
pip install git+https://github.com/pybluez/pybluez.git

5. 仮想環境を抜ける  
deactivate

アプリソース取得  
sudo apt update  
sudo apt install git

クローンしてソース取得  
git clone https://github.com/MementoMori-Entangle/AltitudeLogger.git

リポジトリ管理外ファイル  
server/certs/  
ca.crt  
client.crt  
client.key  
server.crt  
server.key  
android/app/  
my-release-key.jks  
android/  
keystore.properties  
local.properties

#ユーザーとDB作成  
CREATE USER "AltitudeLogger" WITH PASSWORD 's#gs1Gk3Dh8sa!g3s';  
CREATE DATABASE "AltitudeMonitor" OWNER "AltitudeLogger";

#権限追加  
GRANT CONNECT ON DATABASE "AltitudeMonitor" TO "AltitudeLogger";  
GRANT USAGE, CREATE ON SCHEMA public TO "AltitudeLogger";  
ALTER DEFAULT PRIVILEGES IN SCHEMA public  
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "AltitudeLogger";

ALTER DEFAULT PRIVILEGES IN SCHEMA public  
GRANT SELECT ON TABLES TO "AltitudeLogger";

-- アクセスキーの事前準備(DMSと違い管理画面なし)  
CREATE TABLE IF NOT EXISTS access_keys (  
　id SERIAL PRIMARY KEY,  
　access_key VARCHAR(128) UNIQUE NOT NULL,  
　description VARCHAR(256),  
　enabled BOOLEAN DEFAULT TRUE  
);

gRPC自動生成部分  
cd C:\workspace\AltitudeLogger\proto  
python -m grpc_tools.protoc -I ../proto --python_out=../server --grpc_python_out=../server ../proto/altitude_logger.proto

# altitude_logger_server.py起動前に環境変数設定
gRPC認証設定  
・認証なし  
set GRPC_SERVER_AUTH=none  
export GRPC_SERVER_AUTH=none  
・サーバー認証のみ  
set GRPC_SERVER_AUTH=tls  
export GRPC_SERVER_AUTH=tls   
・mTLS  
set GRPC_SERVER_AUTH=mtls  
export GRPC_SERVER_AUTH=mtls

# サービス登録(必要な場合)
対象  
・bmp280_logger.py(高度データ集計 常駐)  
・altitude_logger_server.py(高度データ配信gRPCサービス 常駐)

注意  
altitude_logger_serverはEnvironmentにGRPC_SERVER_AUTHを  
指定しない場合は認証なしとなります。  
ExecStartのpythonは仮想環境で稼働することを考慮してください。  
上記2サービスはPostgreSQLサービスが稼働していることが前提条件です。  
例) PostgreSQLサービス名を確認して指定してください。  
After=postgresql@15-main.service  
Requires=postgresql@15-main.service  
で制御してください。

・bluetooth_config_updater.py(海面気圧と海面基準の標高更新 常駐)  
注意  
ExecStartのpythonは仮想環境で稼働する時、root権限で実行してください。  
上記サービスはbluetoothサービスが稼働していることが前提条件です。  
例) bluetoothサービス名を確認して指定してください。  
After=bluetooth.service  
Requires=bluetooth.service  
で制御してください。

# client
開発環境  
AndroidStudio JDK17

実行環境  
Android13

# 高度計算に必要な海面気圧と海面基準の標高を自動取得
海面気圧: アメダス  
海面基準の標高: 国土地理院API

# ライセンス 2025年8月23日時点
・server  
python  
| パッケージ名       | ライセンス      |
|-------------------|----------------|
| PyBluez           | GPL-2.0        |
| PyYAML            | MIT            |
| psycopg2          | LGPL           |
| bme280            | MIT            |
| smbus2            | MIT            |
| grpcio            | Apache-2.0     |
| grpcio-tools      | Apache-2.0     |


・client  
kotlin(Java)  
| パッケージ名                            | ライセンス    |
|----------------------------------------|--------------|
| androidx.core:core-ktx                 | Apache-2.0   |
| androidx.appcompat                     | Apache-2.0   |
| com.google.android.material            | Apache-2.0   |
| org.jetbrains.kotlin:kotlin-stdlib     | Apache-2.0   |
| io.flutter:flutter_embedding_debug     | BSD 3-Clause |

Dart/Flutter  
| パッケージ名                 | バージョン   | ライセンス    |
|-----------------------------|-------------|--------------|
| cupertino_icons             | ^1.0.8      | MIT          |
| geolocator                  | ^14.0.2     | MIT          |
| http                        | ^1.5.0      | BSD 3-Clause |
| permission_handler          | ^12.0.1     | BSD 3-Clause |
