package com.entangle.slpes

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothSocket
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.ActivityCompat
import io.flutter.plugin.common.MethodChannel
import java.io.IOException
import java.io.OutputStream
import java.util.UUID
import kotlin.concurrent.thread

class BluetoothSppHandler(private val context: Context) {

    private var result: MethodChannel.Result? = null
    private val bluetoothManager: BluetoothManager = context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
    private val bluetoothAdapter: BluetoothAdapter? = bluetoothManager.adapter
    private var bluetoothSocket: BluetoothSocket? = null
    private var outputStream: OutputStream? = null

    companion object {
        // Standard SPP UUID
        private val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    }

    fun setResult(result: MethodChannel.Result) {
        this.result = result
    }

    fun getPairedDevices() {
        if (bluetoothAdapter == null) {
            result?.error("BLUETOOTH_UNAVAILABLE", "Bluetooth is not available on this device.", null)
            return
        }
        if (!bluetoothAdapter.isEnabled) {
            result?.error("BLUETOOTH_DISABLED", "Bluetooth is not enabled.", null)
            return
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (ActivityCompat.checkSelfPermission(context, Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
                result?.error("NO_PERMISSION", "Bluetooth connect permission not granted.", null)
                return
            }
        }

        val pairedDevices: Set<BluetoothDevice> = bluetoothAdapter.bondedDevices
        val devicesList = pairedDevices.map { device ->
            mapOf("name" to device.name, "address" to device.address)
        }
        result?.success(devicesList)
    }

    fun connect(address: String, channelResult: MethodChannel.Result) {
        if (bluetoothAdapter == null) {
            channelResult.error("BLUETOOTH_UNAVAILABLE", "Bluetooth is not available.", null)
            return
        }
        thread(start = true) {
            try {
                disconnect() // Close any existing connection
                val device: BluetoothDevice = bluetoothAdapter.getRemoteDevice(address)
                
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                     if (ActivityCompat.checkSelfPermission(context, Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
                        channelResult.error("NO_PERMISSION", "Bluetooth connect permission not granted.", null)
                        return@thread
                    }
                }

                bluetoothSocket = device.createRfcommSocketToServiceRecord(SPP_UUID)
                bluetoothSocket?.connect()
                outputStream = bluetoothSocket?.outputStream
                channelResult.success(true)
            } catch (e: IOException) {
                channelResult.error("CONNECTION_ERROR", "Failed to connect: ${e.message}", null)
                disconnect()
            } catch (e: SecurityException) {
                channelResult.error("PERMISSION_ERROR", "Permission denied: ${e.message}", null)
            }
        }
    }

    fun disconnect() {
        try {
            outputStream?.close()
            bluetoothSocket?.close()
        } catch (e: IOException) {
            // Ignore
        } finally {
            outputStream = null
            bluetoothSocket = null
        }
    }

    fun send(data: String, channelResult: MethodChannel.Result) {
        if (outputStream == null) {
            channelResult.error("NOT_CONNECTED", "Not connected to any device.", null)
            return
        }
        thread(start = true) {
            try {
                outputStream?.write(data.toByteArray())
                channelResult.success(null)
            } catch (e: IOException) {
                channelResult.error("SEND_ERROR", "Failed to send data: ${e.message}", null)
            }
        }
    }
}