package com.bbl.boxtv.launcher

fun ApiClient.sendCommandResult(deviceId: String, token: String, commandId: String, status: String, result: String) {
    reportCommand(deviceId, token, commandId, status, result)
}
