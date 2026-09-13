package com.bbl.container
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.io.File
import java.security.MessageDigest

data class CatalogApp(val id:String,val name:String,val packageName:String,val version:String,val sha256:String,val downloadUrl:String)
class ApiClient(private val base:String) {
    fun activate(code:String):String {
        val c=conn("/api/device/activate","POST",null); val b=JSONObject().put("activation_code",code).put("device_fingerprint",android.os.Build.MODEL).toString(); c.outputStream.use{it.write(b.toByteArray())}; val o=JSONObject(c.inputStream.bufferedReader().readText()); return o.getString("device_token")
    }
    fun catalog(token:String):List<CatalogApp>{
        val c=conn("/api/device/catalog","GET",token); val a=JSONArray(c.inputStream.bufferedReader().readText()); return (0 until a.length()).map{ val o=a.getJSONObject(it); CatalogApp(o.getString("id"),o.getString("name"),o.getString("package_name"),o.getString("version_name"),o.getString("sha256"),o.getString("download_url")) }
    }
    fun download(token:String,path:String,out:File){ val c=conn(path,"GET",token); c.inputStream.use{i->out.outputStream().use{o->i.copyTo(o)}} }
    private fun conn(path:String,method:String,token:String?):HttpURLConnection { val c=URL(base.trimEnd('/')+path).openConnection() as HttpURLConnection; c.requestMethod=method;c.connectTimeout=15000;c.readTimeout=30000;c.setRequestProperty("Content-Type","application/json"); if(token!=null)c.setRequestProperty("Authorization","Bearer $token"); if(method=="POST")c.doOutput=true; return c }
    companion object { fun sha256(f:File):String { val md=MessageDigest.getInstance("SHA-256"); f.inputStream().use{inp->val b=ByteArray(8192);while(true){val n=inp.read(b);if(n<0)break;md.update(b,0,n)}};return md.digest().joinToString(""){"%02x".format(it)} } }
}
