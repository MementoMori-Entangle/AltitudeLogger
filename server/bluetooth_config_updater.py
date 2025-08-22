import json
import os
import bluetooth
import time

def update_sensor_data(data):
    """
    受信したセンサーデータを sensor_data.json ファイルに保存・更新する。
    ファイルが存在しない場合は新規作成する。
    """
    file_path = os.path.join(os.path.dirname(__file__), 'sensor_data.json')
    try:
        # 既存のデータを読み込む
        existing_data = {}
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                # ファイルが空の場合の対策
                content = f.read()
                if content:
                    existing_data = json.loads(content)
        
        # 新しいデータで更新
        for key, value in data.items():
            if value is not None:
                existing_data[key] = value
        
        # ファイルに書き込む
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)
        
        print(f"Updated {file_path} with: {data}")

    except (IOError, json.JSONDecodeError) as e:
        print(f"Error updating {file_path}: {e}")


def run_server():
    """Bluetooth SPPサーバーを起動し、データを受信する"""
    server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    server_sock.bind(("", bluetooth.PORT_ANY))
    server_sock.listen(1)

    port = server_sock.getsockname()[1]
    uuid = "00001101-0000-1000-8000-00805F9B34FB" # Flutterアプリと合わせる

    bluetooth.advertise_service(server_sock, "AltitudeLoggerServer",
                                service_id=uuid,
                                service_classes=[uuid, bluetooth.SERIAL_PORT_CLASS],
                                profiles=[bluetooth.SERIAL_PORT_PROFILE])

    print(f"シリアルポートサービスをポート {port} で待機中...")

    while True:
        try:
            client_sock, client_info = server_sock.accept()
            print(f"接続を受け入れました: {client_info}")

            try:
                while True:
                    data = client_sock.recv(1024)
                    if not data:
                        break
                    
                    # 複数のJSONオブジェクトが一度に送られてくる可能性を考慮
                    decoded_data = data.decode('utf-8').strip()
                    json_strings = [s for s in decoded_data.split('\n') if s]

                    for json_str in json_strings:
                        try:
                            print(f"受信データ: {json_str}")
                            sensor_data = json.loads(json_str)
                            
                            # 新しい関数を呼び出す
                            update_sensor_data(sensor_data)

                        except json.JSONDecodeError:
                            print(f"エラー: JSONのデコードに失敗しました。受信データ: {json_str}")
                        except Exception as e:
                            print(f"データ処理中にエラーが発生しました: {e}")

            except bluetooth.btcommon.BluetoothError as e:
                print(f"クライアントとの通信エラー: {e}")
            finally:
                print("クライアントが切断しました。")
                client_sock.close()

        except KeyboardInterrupt:
            print("\nサーバーを停止します。")
            break
        except Exception as e:
            print(f"サーバーエラー: {e}")
            # エラーが発生してもサーバーを再起動
            time.sleep(1) # 短い待機時間
            continue

    server_sock.close()
    print("サーバーソケットを閉じました。")

if __name__ == '__main__':
    run_server()
