package com.bbl.boxtv.launcher

import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.security.MessageDigest

internal data class RemoteApp(val packageName:String,val label:String,val category:String="Aplicativos",val downloadUrl:String="",val versionName:String="",val versionCode:Long=0L,val sha256:String="")
internal data class RemoteBanner(val id:String,val name:String,val type:String,val url:String)
internal data class RemoteCommand(val id:String,val command:String,val payload:String)
internal data class DeviceConfig(val active:Boolean,val pending:Boolean=false,val expiresAt:String="",val apps:List<RemoteApp> = emptyList(),val brandingName:String="BBL.BOXTV",val logoUrl:String="",val wallpaperUrl:String="",val message:String="",val banners:List<RemoteBanner> = emptyList())

internal object ApiClient {
    private val apiBaseUrl=BuildConfig.API_BASE_URL.trimEnd('/')
    fun absoluteUrl(value:String):String { val v=value.trim(); return if(v.startsWith("http://")||v.startsWith("https://")) v else "$apiBaseUrl/${v.trimStart('/')}" }
    fun enroll(deviceId:String,activationCode:String):String {
        val c=URL("$apiBaseUrl/api/enroll").openConnection() as HttpURLConnection
        try { c.doOutput=true;c.connectTimeout=10000;c.readTimeout=10000;c.requestMethod="POST";c.setRequestProperty("Content-Type","application/json");c.setRequestProperty("Accept","application/json")
            val body=JSONObject().put("activationCode",activationCode.trim()).put("deviceId",deviceId).put("manufacturer",android.os.Build.MANUFACTURER?:"").put("model",android.os.Build.MODEL?:"").put("android_version",android.os.Build.VERSION.RELEASE?:"").put("launcher_version",BuildConfig.VERSION_NAME).toString()
            c.outputStream.use{it.write(body.toByteArray(Charsets.UTF_8))};val code=c.responseCode;val text=(if(code in 200..299)c.inputStream else c.errorStream)?.bufferedReader()?.use{it.readText()}.orEmpty();if(code !in 200..299)throw HttpStatusException(code,text)
            val j=JSONObject(text);return j.optString("device_token",j.optString("deviceToken",j.optString("token"))).also{if(it.isBlank())throw RuntimeException("Servidor não retornou token")}
        } finally { c.disconnect() }
    }
    fun getPolicy(deviceId:String,token:String):DeviceConfig {
        val id=URLEncoder.encode(deviceId,"UTF-8");val c=URL("$apiBaseUrl/api/devices/$id/policy").openConnection() as HttpURLConnection
        try { c.connectTimeout=10000;c.readTimeout=10000;c.requestMethod="GET";c.setRequestProperty("Accept","application/json");c.setRequestProperty("Authorization","Bearer $token");val code=c.responseCode;if(code !in 200..299)throw HttpStatusException(code)
            val j=JSONObject(c.inputStream.bufferedReader().use{it.readText()});val apps=mutableListOf<RemoteApp>();val a=j.optJSONArray("apps");if(a!=null)for(i in 0 until a.length()){val x=a.optJSONObject(i)?:continue;val pkg=x.optString("package_name").trim();if(pkg.isNotBlank())apps+=RemoteApp(pkg,x.optString("name",pkg).ifBlank{pkg},x.optString("category","Aplicativos"),x.optString("download_url","").trim(),x.optString("version_name","").trim(),x.optString("version_code","0").toLongOrNull()?:x.optLong("version_code",0L),x.optString("sha256","").trim().lowercase())}
            val brand=j.optJSONObject("brand")?:j.optJSONObject("branding")?:JSONObject();val banners=mutableListOf<RemoteBanner>();val ba=j.optJSONArray("banners");if(ba!=null)for(i in 0 until ba.length()){val b=ba.optJSONObject(i)?:continue;banners+=RemoteBanner(b.optString("id",i.toString()),b.optString("name","Banner"),b.optString("type","image"),b.optString("url",""))}
            val locked=j.optBoolean("locked",false)||j.optBoolean("expired",false);return DeviceConfig(!locked,expiresAt=j.optString("expires_at",""),apps=apps,brandingName=brand.optString("name",j.optString("branding_name","BBL.BOXTV")),logoUrl=brand.optString("logo_url",j.optString("logo_url","")),wallpaperUrl=brand.optString("wallpaper_url",j.optString("wallpaper_url","")),message=j.optString("message",brand.optString("message","")),banners=banners)
        } finally { c.disconnect() }
    }
    fun downloadBytes(urlValue:String):ByteArray { if(urlValue.isBlank())return ByteArray(0);val c=URL(absoluteUrl(urlValue)).openConnection() as HttpURLConnection;try{c.connectTimeout=10000;c.readTimeout=20000;c.instanceFollowRedirects=true;c.requestMethod="GET";if(c.responseCode !in 200..299)throw HttpStatusException(c.responseCode);return c.inputStream.use{it.readBytes()}}finally{c.disconnect()} }
    fun downloadApk(app:RemoteApp,destination:File){if(app.downloadUrl.isBlank())throw RuntimeException("Aplicativo sem URL de download");val c=URL(absoluteUrl(app.downloadUrl)).openConnection() as HttpURLConnection;try{c.connectTimeout=15000;c.readTimeout=60000;c.instanceFollowRedirects=true;c.requestMethod="GET";c.setRequestProperty("Accept","application/vnd.android.package-archive,application/octet-stream,*/*");val code=c.responseCode;if(code !in 200..299)throw HttpStatusException(code);destination.parentFile?.mkdirs();c.inputStream.use{input->destination.outputStream().use{out->input.copyTo(out)}};if(destination.length()<=0L)throw RuntimeException("APK vazio");if(app.sha256.isNotBlank()){val md=MessageDigest.getInstance("SHA-256");destination.inputStream().use{input->val buf=ByteArray(64*1024);while(true){val n=input.read(buf);if(n<=0)break;md.update(buf,0,n)}};val got=md.digest().joinToString(""){"%02x".format(it)};if(!got.equals(app.sha256,true)){destination.delete();throw RuntimeException("Falha na verificação do APK")}}}finally{c.disconnect()}}
    fun getCommands(deviceId:String,token:String):List<RemoteCommand>{val id=URLEncoder.encode(deviceId,"UTF-8");val c=URL("$apiBaseUrl/api/devices/$id/commands").openConnection() as HttpURLConnection;try{c.connectTimeout=10000;c.readTimeout=10000;c.requestMethod="GET";c.setRequestProperty("Authorization","Bearer $token");if(c.responseCode !in 200..299)throw HttpStatusException(c.responseCode);val arr=org.json.JSONArray(c.inputStream.bufferedReader().use{it.readText()});val out=mutableListOf<RemoteCommand>();for(i in 0 until arr.length()){val x=arr.optJSONObject(i)?:continue;out+=RemoteCommand(x.optString("id"),x.optString("command"),x.opt("payload")?.toString()?:"{}")}return out}finally{c.disconnect()}}
    fun reportCommand(deviceId:String,token:String,commandId:String,status:String,result:String){val id=URLEncoder.encode(deviceId,"UTF-8");val cmd=URLEncoder.encode(commandId,"UTF-8");val c=URL("$apiBaseUrl/api/devices/$id/commands/$cmd/result").openConnection() as HttpURLConnection;try{c.doOutput=true;c.requestMethod="POST";c.setRequestProperty("Content-Type","application/json");c.setRequestProperty("Authorization","Bearer $token");val body=JSONObject().put("status",status).put("result",result).toString();c.outputStream.use{it.write(body.toByteArray())};c.responseCode}finally{c.disconnect()}}
    internal class HttpStatusException(val code:Int,val body:String=""):RuntimeException("HTTP $code $body")
}
