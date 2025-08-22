package com.entangle.slpes

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.core.app.ActivityCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val CHANNEL = "com.entangle.altitudelogger/bluetooth"
    private lateinit var handler: BluetoothSppHandler
    private val BLUETOOTH_PERMISSION_REQUEST_CODE = 99

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        checkAndRequestBluetoothPermissions()
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        handler = BluetoothSppHandler(this)

        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            CHANNEL
        ).setMethodCallHandler { call, result ->
            handler.setResult(result)
            when (call.method) {
                "getPairedDevices" -> {
                    handler.getPairedDevices()
                }
                "connect" -> {
                    val address = call.argument<String>("address")
                    if (address != null) {
                        handler.connect(address, result)
                    } else {
                        result.error("INVALID_ARGUMENT", "Address cannot be null", null)
                    }
                }
                "disconnect" -> {
                    handler.disconnect()
                    result.success(null)
                }
                "send" -> {
                    val data = call.argument<String>("data")
                    if (data != null) {
                        handler.send(data, result)
                    } else {
                        result.error("INVALID_ARGUMENT", "Data cannot be null", null)
                    }
                }
                else -> {
                    result.notImplemented()
                }
            }
        }
    }

    private fun checkAndRequestBluetoothPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val permissionsToRequest = mutableListOf<String>()
            if (ActivityCompat.checkSelfPermission(
                    this,
                    Manifest.permission.BLUETOOTH_SCAN
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                permissionsToRequest.add(Manifest.permission.BLUETOOTH_SCAN)
            }
            if (ActivityCompat.checkSelfPermission(
                    this,
                    Manifest.permission.BLUETOOTH_CONNECT
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                permissionsToRequest.add(Manifest.permission.BLUETOOTH_CONNECT)
            }
            if (permissionsToRequest.isNotEmpty()) {
                ActivityCompat.requestPermissions(
                    this,
                    permissionsToRequest.toTypedArray(),
                    BLUETOOTH_PERMISSION_REQUEST_CODE
                )
            }
        }
    }
}
