package com.bbl.boxtv.launcher

internal fun ApiClient.sendCommandResult(deviceId: String, token: String, commandId: String, status: String, result: String) {
    reportCommand(deviceId, token, commandId, status, result)
}
