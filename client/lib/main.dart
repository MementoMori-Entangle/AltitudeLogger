import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;

void main() => runApp(const MyApp());

class MyApp extends StatelessWidget {
  const MyApp({super.key});
  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      title: 'Bluetooth 設定送信',
      home: BluetoothSendPage(),
    );
  }
}

class BluetoothDevice {
  final String name;
  final String address;

  BluetoothDevice({required this.name, required this.address});

  factory BluetoothDevice.fromMap(Map<dynamic, dynamic> map) {
    return BluetoothDevice(
      name: map['name'] ?? 'Unknown Device',
      address: map['address'] ?? '',
    );
  }
}

class BluetoothSendPage extends StatefulWidget {
  const BluetoothSendPage({super.key});
  @override
  State<BluetoothSendPage> createState() => BluetoothSendPageState();
}

class BluetoothSendPageState extends State<BluetoothSendPage> {
  static const platform = MethodChannel(
    'com.entangle.altitudelogger/bluetooth',
  );

  List<BluetoothDevice> _devices = [];
  BluetoothDevice? _selectedDevice;
  bool _isConnected = false;

  final _pressureController = TextEditingController();
  final _elevationController = TextEditingController();
  String _status = '';
  bool _isConnecting = false;
  bool _isSending = false;
  bool _isFetchingElevation = false;
  bool _isFetchingPressure = false;

  @override
  void initState() {
    super.initState();
  }

  @override
  void dispose() {
    _pressureController.dispose();
    _elevationController.dispose();
    _disconnect();
    super.dispose();
  }

  Future<void> _getPairedDevices() async {
    try {
      final List<dynamic>? devices = await platform.invokeMethod(
        'getPairedDevices',
      );
      if (devices != null) {
        setState(() {
          _devices =
              devices
                  .map(
                    (d) => BluetoothDevice.fromMap(d as Map<dynamic, dynamic>),
                  )
                  .toList();
        });
      }
    } on PlatformException catch (e) {
      setState(() {
        _status = "ペアリング済みデバイスの取得に失敗: ${e.message}";
      });
    }
  }

  Future<void> _connect() async {
    if (_selectedDevice == null) {
      setState(() => _status = 'デバイスが選択されていません');
      return;
    }
    setState(() {
      _isConnecting = true;
      _status = '接続中...';
    });
    try {
      final bool? connected = await platform.invokeMethod('connect', {
        'address': _selectedDevice!.address,
      });
      if (connected == true) {
        setState(() {
          _isConnected = true;
          _status = '接続完了';
        });
      } else {
        setState(() {
          _isConnected = false;
          _status = '接続に失敗しました';
        });
      }
    } on PlatformException catch (e) {
      setState(() {
        _isConnected = false;
        _status = "接続エラー: ${e.message}";
      });
    } finally {
      setState(() {
        _isConnecting = false;
      });
    }
  }

  Future<void> _disconnect() async {
    if (!_isConnected) return;
    try {
      await platform.invokeMethod('disconnect');
    } on PlatformException catch (e) {
      setState(() {
        _status = "切断エラー: ${e.message}";
      });
    } finally {
      setState(() {
        _isConnected = false;
        _status = '切断しました';
      });
    }
  }

  Future<void> _sendData() async {
    if (!_isConnected) {
      setState(() => _status = '接続されていません');
      return;
    }
    setState(() {
      _isSending = true;
      _status = '送信中...';
    });
    final data = {
      "sea_level_pressure": double.tryParse(_pressureController.text),
      "elevation": double.tryParse(_elevationController.text),
    };
    try {
      await platform.invokeMethod('send', {'data': '${json.encode(data)}\n'});
      setState(() {
        _status = '送信しました';
      });
    } on PlatformException catch (e) {
      setState(() {
        _status = "送信エラー: ${e.message}";
      });
    } finally {
      setState(() {
        _isSending = false;
      });
    }
  }

  Future<Position> _determinePosition() async {
    LocationPermission permission;

    permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        return Future.error('Location permissions are denied');
      }
    }

    if (permission == LocationPermission.deniedForever) {
      return Future.error(
        'Location permissions are permanently denied, we cannot request permissions.',
      );
    }

    return await Geolocator.getCurrentPosition();
  }

  Future<void> _getElevationFromGps() async {
    setState(() {
      _isFetchingElevation = true;
      _status = 'GPSから標高を取得中...';
    });
    try {
      final position = await _determinePosition();
      final url = Uri.parse(
        'https://cyberjapandata2.gsi.go.jp/general/dem/scripts/getelevation.php?lon=${position.longitude}&lat=${position.latitude}&outtype=JSON',
      );
      final response = await http.get(url);
      if (response.statusCode == 200) {
        final jsonResponse = json.decode(response.body);
        final elevation = jsonResponse['elevation'];
        _elevationController.text = elevation.toString();
        setState(() {
          _status = '標高を取得しました: $elevation m';
        });
      } else {
        setState(() {
          _status = '標高の取得に失敗しました。';
        });
      }
    } catch (e) {
      setState(() {
        _status = '標高の取得に失敗しました: $e';
      });
    } finally {
      setState(() {
        _isFetchingElevation = false;
      });
    }
  }

  Future<void> _getSeaLevelPressure() async {
    setState(() {
      _isFetchingPressure = true;
      _status = '最寄りのAMeDASから海面気圧を取得中...';
    });

    try {
      // 1. Get current location
      final position = await _determinePosition();

      // 2. Fetch AMeDAS station list
      final stationListUrl = Uri.parse(
        'https://www.jma.go.jp/bosai/amedas/const/amedastable.json',
      );
      final stationListResponse = await http.get(stationListUrl);
      if (stationListResponse.statusCode != 200) {
        throw Exception('AMeDAS観測所リストの取得に失敗しました。');
      }
      final stationList = json.decode(stationListResponse.body);

      // 3. Find the nearest station
      String nearestStationCode = '';
      double minDistance = double.infinity;

      (stationList as Map<String, dynamic>).forEach((key, value) {
        if (value['lat'] is List && value['lon'] is List) {
          final lat = value['lat'][0] + value['lat'][1] / 60;
          final lon = value['lon'][0] + value['lon'][1] / 60;
          final distance = Geolocator.distanceBetween(
            position.latitude,
            position.longitude,
            lat,
            lon,
          );
          if (distance < minDistance) {
            minDistance = distance;
            nearestStationCode = key;
          }
        }
      });

      if (nearestStationCode.isEmpty) {
        throw Exception('最寄りの観測所が見つかりませんでした。');
      }
      final stationInfo = stationList[nearestStationCode];
      final stationName = stationInfo['kjName'];

      setState(() {
        _status = '最寄りの観測所: $stationName';
      });

      // 4. Fetch latest weather data
      final latestTimeUrl = Uri.parse(
        'https://www.jma.go.jp/bosai/amedas/data/latest_time.txt',
      );
      final latestTimeResponse = await http.get(latestTimeUrl);
      if (latestTimeResponse.statusCode != 200) {
        throw Exception('最新時刻の取得に失敗しました。');
      }

      // ISO 8601形式の時刻をYYYYMMDDHHMMSS形式に変換
      final latestTime = latestTimeResponse.body
          .trim()
          .replaceAll(RegExp(r'[-:T+Z]'), '')
          .substring(0, 14);

      final dataUrl = Uri.parse(
        'https://www.jma.go.jp/bosai/amedas/data/map/$latestTime.json',
      );
      final headers = {
        'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36',
      };
      final dataResponse = await http.get(dataUrl, headers: headers);
      if (dataResponse.statusCode != 200) {
        throw Exception('気象データの取得に失敗しました。');
      }

      // 5. Parse JSON and find sea level pressure
      final weatherData = json.decode(dataResponse.body);
      final stationData = weatherData[nearestStationCode];

      if (stationData == null) {
        throw Exception('最寄りの観測所の気象データが見つかりませんでした。');
      }

      final normalPressureData = stationData['normalPressure'];
      final seaLevelPressure =
          (normalPressureData is List && normalPressureData.isNotEmpty)
              ? normalPressureData[0]?.toString()
              : null;

      if (seaLevelPressure != null) {
        _pressureController.text = seaLevelPressure;
        setState(() {
          _status = '海面気圧を取得しました: $seaLevelPressure hPa';
        });
      } else {
        throw Exception('海面気圧データが見つかりませんでした。');
      }
    } catch (e) {
      setState(() {
        _status = '海面気圧の取得に失敗しました: $e';
      });
    } finally {
      setState(() {
        _isFetchingPressure = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Bluetooth 設定送信')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              ElevatedButton(
                onPressed: _getPairedDevices,
                child: const Text('デバイス検索'),
              ),
              DropdownButton<BluetoothDevice>(
                isExpanded: true,
                hint: const Text('デバイス選択'),
                value: _selectedDevice,
                onChanged: (BluetoothDevice? newValue) {
                  setState(() {
                    _selectedDevice = newValue;
                  });
                },
                items:
                    _devices.map((device) {
                      return DropdownMenuItem<BluetoothDevice>(
                        value: device,
                        child: Text(device.name),
                      );
                    }).toList(),
              ),
              Text('選択中のデバイス: ${_selectedDevice?.name ?? '未選択'}'),
              const SizedBox(height: 10),
              TextField(
                controller: _pressureController,
                decoration: const InputDecoration(
                  labelText: '海面気圧 (hPa)',
                  border: OutlineInputBorder(),
                ),
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
              ),
              const SizedBox(height: 5),
              ElevatedButton(
                onPressed: _isFetchingPressure ? null : _getSeaLevelPressure,
                child:
                    _isFetchingPressure
                        ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                        : const Text('最寄りのAMeDASから海面気圧を取得'),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _elevationController,
                decoration: const InputDecoration(
                  labelText: '標高 (m)',
                  border: OutlineInputBorder(),
                ),
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
              ),
              const SizedBox(height: 5),
              ElevatedButton(
                onPressed: _isFetchingElevation ? null : _getElevationFromGps,
                child:
                    _isFetchingElevation
                        ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                        : const Text('GPSから標高を取得'),
              ),
              const SizedBox(height: 20),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  ElevatedButton(
                    onPressed:
                        (_selectedDevice == null ||
                                _isConnecting ||
                                _isConnected)
                            ? null
                            : _connect,
                    child:
                        _isConnecting
                            ? const CircularProgressIndicator()
                            : const Text('接続'),
                  ),
                  ElevatedButton(
                    onPressed: !_isConnected ? null : _disconnect,
                    child: const Text('切断'),
                  ),
                  ElevatedButton(
                    onPressed: (!_isConnected || _isSending) ? null : _sendData,
                    child:
                        _isSending
                            ? const CircularProgressIndicator()
                            : const Text('送信'),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              Text(_status),
            ],
          ),
        ),
      ),
    );
  }
}
