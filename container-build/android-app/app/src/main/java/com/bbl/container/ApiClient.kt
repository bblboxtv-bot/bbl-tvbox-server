package com.bbl.container

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.io.File
import java.security.MessageDigest

data class DeviceSession(val token:String,val deviceId:String)
data class CatalogApp(val id:String,val name:String,val packageName:String,val version:String,val sha256:String,val downloadUrl:String)

class ApiClient(private val base:String) {
    fun login(username:String,password:String,deviceId:String):DeviceSession {
        val c=conn("/base2/api/login","POST",null)
        val body=JSONObject().put("username",username).put("password",password).put("device_id",deviceId).toString()
        c.outputStream.use{it.write(body.toByteArray())}
        val text=readResponse(c)
        val o=JSONObject(text)
        val token=o.optString("token")
        if(token.isBlank()) throw IllegalStateException(o.optString("detail",o.optString("error","Login recusado pelo servidor")))
        return DeviceSession(token,o.optString("device_id",deviceId))
    }

    fun catalog(token:String):List<CatalogApp>{
        val c=conn("/base2/api/apps/list","GET",token)
        val text=readResponse(c)
        val a=if(text.trim().startsWith("[")) JSONArray(text) else JSONObject(text).optJSONArray("apps")?:JSONArray()
        return (0 until a.length()).mapNotNull { i ->
            val o=a.optJSONObject(i)?:return@mapNotNull null
            val id=o.optString("id"); val pkg=o.optString("package_name"); val url=o.optString("download_url")
            if(id.isBlank()||pkg.isBlank()||url.isBlank()) null else CatalogApp(id,o.optString("name",pkg),pkg,o.optString("version_name"),o.optString("sha256"),url)
        }
    }

    fun download(token:String,path:String,out:File){
        val c=conn(path,"GET",token)
        if(c.responseCode !in 200..299) throw IllegalStateException("Falha no download: HTTP ${c.responseCode}")
        c.inputStream.use{i->out.outputStream().use{o->i.copyTo(o)}}
    }

    private fun readResponse(c:HttpURLConnection):String {
        val code=c.responseCode
        val input=if(code in 200..299)c.inputStream else c.errorStream
        val text=input?.bufferedReader()?.use{it.readText()}?:""
        if(code !in 200..299){
            val msg=runCatching{JSONObject(text).optString("detail",JSONObject(text).optString("error"))}.getOrDefault("")
            throw IllegalStateException(if(msg.isNotBlank()) msg else "HTTP $code")
        }
        return text
    }

    private fun conn(path:String,method:String,token:String?):HttpURLConnection {
        val url=if(path.startsWith("http://")||path.startsWith("https://"))path else base.trimEnd('/')+path
        val c=URL(url).openConnection() as HttpURLConnection
        c.requestMethod=method;c.connectTimeout=15000;c.readTimeout=30000;c.setRequestProperty("Content-Type","application/json")
        if(token!=null)c.setRequestProperty("Authorization","Bearer $token")
        if(method=="POST")c.doOutput=true
        return c
    }

    companion object {
        fun sha256(f:File):String { val md=MessageDigest.getInstance("SHA-256"); f.inputStream().use{inp->val b=ByteArray(8192);while(true){val n=inp.read(b);if(n<0)break;md.update(b,0,n)}};return md.digest().joinToString(""){"%02x".format(it)} }
    }
}
