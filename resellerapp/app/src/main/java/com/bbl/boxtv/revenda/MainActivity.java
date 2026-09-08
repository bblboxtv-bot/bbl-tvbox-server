package com.bbl.boxtv.revenda;

import android.app.Activity;
import android.app.PendingIntent;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInstaller;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
    private static final String BASE_URL = "https://bbl-tvbox-manager-v2.onrender.com";
    private static final String LOGIN_URL = BASE_URL + "/base2/api/login";
    private static final String CHECK_URL = BASE_URL + "/base2/api/check";
    private static final String APPS_LIST_URL = BASE_URL + "/base2/api/apps/list";
    private static final String APPS_RESULT_URL = BASE_URL + "/base2/api/apps/result";
    private static final String MOTOR_PACKAGE = "com.rtxapps.reuse";
    private static final String PREFS = "tudo_liberado_auth";
    private static final String PREF_TOKEN = "token";
    private static final String PREF_QUEUE = "install_queue";
    private static final String[] MOTOR_ACTIVITIES = new String[] {
            "top.niunaijun.blackboxa.view.main.LauncherActivity",
            "top.niunaijun.blackbox.app.LauncherActivity"
    };

    private LinearLayout root;
    private EditText userField;
    private EditText passField;
    private Button enterButton;
    private ProgressBar progress;
    private TextView status;
    private android.content.SharedPreferences prefs;
    private boolean waitingInstallPermission = false;
    private boolean firstResume = true;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        buildLoginUi();
        if (handleInstallerCallback(getIntent())) return;
        String savedToken = prefs.getString(PREF_TOKEN, "");
        if (savedToken != null && !savedToken.trim().isEmpty()) checkSavedLogin(savedToken.trim());
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (firstResume) { firstResume = false; return; }
        if (waitingInstallPermission) {
            waitingInstallPermission = false;
            String token = prefs.getString(PREF_TOKEN, "");
            if (token != null && !token.isEmpty()) loadAppCatalog(token);
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleInstallerCallback(intent);
    }

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }

    private TextView text(String value, float size, int color) {
        TextView t = new TextView(this);
        t.setText(value);
        t.setTextSize(size);
        t.setTextColor(color);
        t.setGravity(Gravity.CENTER);
        return t;
    }

    private LinearLayout newRoot() {
        LinearLayout r = new LinearLayout(this);
        r.setOrientation(LinearLayout.VERTICAL);
        r.setPadding(dp(34), dp(24), dp(34), dp(24));
        r.setBackgroundColor(Color.rgb(5, 12, 22));
        return r;
    }

    private void addHeader(LinearLayout target, String subtitleText) {
        TextView logo = text("TUDO LIBERADO", 30f, Color.WHITE);
        logo.setTypeface(logo.getTypeface(), 1);
        target.addView(logo, new LinearLayout.LayoutParams(-1, -2));
        TextView subtitle = text(subtitleText, 16f, Color.rgb(93,188,255));
        subtitle.setPadding(0, dp(4), 0, dp(18));
        target.addView(subtitle, new LinearLayout.LayoutParams(-1,-2));
    }

    private void buildLoginUi() {
        root = newRoot();
        root.setGravity(Gravity.CENTER);
        addHeader(root, "ACESSO CONTROLADO");
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(28),dp(24),dp(28),dp(24));
        card.setBackgroundColor(Color.rgb(14,35,58));
        root.addView(card,new LinearLayout.LayoutParams(dp(520),-2));

        TextView title=text("Entre com seu usuário e senha",18f,Color.WHITE);
        title.setGravity(Gravity.START);
        title.setPadding(0,0,0,dp(14));
        card.addView(title);

        userField=new EditText(this);
        userField.setHint("Usuário");
        userField.setSingleLine(true);
        userField.setTextColor(Color.WHITE);
        userField.setHintTextColor(Color.rgb(150,170,190));
        userField.setBackgroundColor(Color.rgb(7,24,42));
        userField.setPadding(dp(16),dp(12),dp(16),dp(12));
        LinearLayout.LayoutParams fp=new LinearLayout.LayoutParams(-1,dp(58));
        fp.setMargins(0,dp(6),0,dp(10));
        card.addView(userField,fp);

        passField=new EditText(this);
        passField.setHint("Senha");
        passField.setSingleLine(true);
        passField.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
        passField.setTextColor(Color.WHITE);
        passField.setHintTextColor(Color.rgb(150,170,190));
        passField.setBackgroundColor(Color.rgb(7,24,42));
        passField.setPadding(dp(16),dp(12),dp(16),dp(12));
        LinearLayout.LayoutParams pp=new LinearLayout.LayoutParams(-1,dp(58));
        pp.setMargins(0,0,0,dp(14));
        card.addView(passField,pp);

        enterButton=new Button(this);
        enterButton.setText("ENTRAR");
        enterButton.setTextSize(17f);
        enterButton.setFocusable(true);
        enterButton.setOnClickListener(v->login());
        card.addView(enterButton,new LinearLayout.LayoutParams(-1,dp(58)));

        progress=new ProgressBar(this);
        progress.setVisibility(View.GONE);
        LinearLayout.LayoutParams prog=new LinearLayout.LayoutParams(dp(42),dp(42));
        prog.gravity=Gravity.CENTER_HORIZONTAL;
        prog.setMargins(0,dp(14),0,0);
        card.addView(progress,prog);

        status=text("",15f,Color.LTGRAY);
        status.setPadding(0,dp(10),0,0);
        card.addView(status,new LinearLayout.LayoutParams(-1,-2));
        setContentView(root);
        userField.requestFocus();
    }

    private String deviceId() {
        String id=Settings.Secure.getString(getContentResolver(),Settings.Secure.ANDROID_ID);
        if(id==null||id.trim().isEmpty()) id=Build.SERIAL;
        if(id==null||id.trim().isEmpty()) id="unknown-device";
        return id.trim();
    }

    private JSONObject postJson(String urlString, JSONObject json) throws Exception {
        URL url=new URL(urlString);
        HttpURLConnection conn=(HttpURLConnection)url.openConnection();
        conn.setConnectTimeout(15000);
        conn.setReadTimeout(30000);
        conn.setRequestMethod("POST");
        conn.setRequestProperty("Content-Type","application/json; charset=UTF-8");
        conn.setRequestProperty("Accept","application/json");
        conn.setDoOutput(true);
        byte[] out=json.toString().getBytes(StandardCharsets.UTF_8);
        try(OutputStream os=conn.getOutputStream()){os.write(out);}
        int code=conn.getResponseCode();
        InputStream in=code>=200&&code<400?conn.getInputStream():conn.getErrorStream();
        StringBuilder sb=new StringBuilder();
        if(in!=null){BufferedReader br=new BufferedReader(new InputStreamReader(in,StandardCharsets.UTF_8));String line;while((line=br.readLine())!=null)sb.append(line);}
        conn.disconnect();
        JSONObject result=sb.length()>0?new JSONObject(sb.toString()):new JSONObject();
        result.put("_http",code);
        return result;
    }

    private void checkSavedLogin(final String token) {
        setBusy(true,"Validando acesso salvo...");
        new Thread(()->{
            try {
                JSONObject j=new JSONObject();
                j.put("token",token);
                j.put("device_id",deviceId());
                JSONObject r=postJson(CHECK_URL,j);
                int code=r.optInt("_http",500);
                runOnUiThread(()->{
                    if(code>=200&&code<300){ loadAppCatalog(token); }
                    else { prefs.edit().remove(PREF_TOKEN).apply(); buildLoginUi(); status.setText("Sessão expirada. Entre novamente."); }
                });
            } catch(Exception e){runOnUiThread(()->setBusy(false,"Sem conexão. Digite usuário e senha para tentar novamente."));}
        }).start();
    }

    private void login() {
        final String username=userField.getText().toString().trim();
        final String password=passField.getText().toString();
        if(username.isEmpty()||password.isEmpty()){status.setText("Digite usuário e senha.");return;}
        setBusy(true,"Verificando acesso...");
        new Thread(()->{
            try {
                JSONObject j=new JSONObject();
                j.put("username",username);
                j.put("password",password);
                j.put("device_id",deviceId());
                JSONObject r=postJson(LOGIN_URL,j);
                int code=r.optInt("_http",500);
                runOnUiThread(()->{
                    if(code>=200&&code<300){
                        String token=r.optString("token","").trim();
                        if(!token.isEmpty()) prefs.edit().putString(PREF_TOKEN,token).apply();
                        loadAppCatalog(token);
                    } else {
                        String err=r.optString("error","");
                        String msg="Usuário ou senha inválidos.";
                        if("blocked".equals(err))msg="Acesso bloqueado no painel.";
                        else if("expired".equals(err))msg="Acesso vencido. Fale com sua revenda.";
                        else if("device_in_use".equals(err))msg="Este usuário já está vinculado a outro aparelho.";
                        setBusy(false,msg);
                    }
                });
            } catch(Exception e){runOnUiThread(()->setBusy(false,"Falha de conexão. Verifique a internet e tente novamente."));}
        }).start();
    }

    private void loadAppCatalog(final String token) {
        new Thread(()->{
            try {
                JSONObject j=new JSONObject();
                j.put("token",token);
                j.put("device_id",deviceId());
                JSONObject r=postJson(APPS_LIST_URL,j);
                int code=r.optInt("_http",500);
                if(code<200||code>=300){runOnUiThread(()->showAppsScreen(token,new JSONArray(),"Falha ao carregar aplicativos do painel."));return;}
                JSONArray apps=r.optJSONArray("apps");
                if(apps==null) apps=new JSONArray();
                final JSONArray result=apps;
                runOnUiThread(()->showAppsScreen(token,result,""));
            } catch(Exception e){runOnUiThread(()->showAppsScreen(token,new JSONArray(),"Sem conexão com o painel."));}
        }).start();
    }

    private boolean isInstalled(String packageName) {
        if(packageName==null||packageName.trim().isEmpty()) return false;
        try { getPackageManager().getPackageInfo(packageName,0); return true; }
        catch(Exception e){ return false; }
    }

    private void showAppsScreen(final String token, JSONArray apps, String message) {
        root=newRoot();
        addHeader(root,"APLICATIVOS LIBERADOS PELO PAINEL");

        LinearLayout actions=new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setGravity(Gravity.CENTER);
        Button openMain=new Button(this);
        openMain.setText("ABRIR TUDO LIBERADO");
        openMain.setOnClickListener(v->openTudoLiberado());
        actions.addView(openMain,new LinearLayout.LayoutParams(0,dp(56),1f));
        Button refresh=new Button(this);
        refresh.setText("ATUALIZAR");
        refresh.setOnClickListener(v->loadAppCatalog(token));
        LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(dp(180),dp(56));
        rp.setMargins(dp(10),0,0,0);
        actions.addView(refresh,rp);
        root.addView(actions,new LinearLayout.LayoutParams(-1,-2));

        TextView info=text(message.isEmpty()?"Escolha um aplicativo abaixo para instalar.":message,15f,message.isEmpty()?Color.LTGRAY:Color.rgb(255,150,150));
        info.setPadding(0,dp(10),0,dp(10));
        root.addView(info,new LinearLayout.LayoutParams(-1,-2));

        ScrollView scroll=new ScrollView(this);
        LinearLayout list=new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(list,new ScrollView.LayoutParams(-1,-2));

        if(apps.length()==0){
            TextView empty=text("Nenhum aplicativo foi enviado para este cliente pelo painel.",18f,Color.WHITE);
            empty.setPadding(dp(20),dp(50),dp(20),dp(20));
            list.addView(empty,new LinearLayout.LayoutParams(-1,-2));
        }

        for(int i=0;i<apps.length();i++){
            JSONObject a=apps.optJSONObject(i);
            if(a==null) continue;
            final String qid=a.optString("queue_id","");
            final String appId=a.optString("id","");
            final String name=a.optString("name","Aplicativo");
            final String pkg=a.optString("package_name","");
            final String dl=a.optString("download_url","");
            final String ver=a.optString("version_name","");
            boolean installed=isInstalled(pkg);

            LinearLayout card=new LinearLayout(this);
            card.setOrientation(LinearLayout.HORIZONTAL);
            card.setGravity(Gravity.CENTER_VERTICAL);
            card.setPadding(dp(18),dp(14),dp(18),dp(14));
            card.setBackgroundColor(Color.rgb(14,35,58));
            LinearLayout.LayoutParams cp=new LinearLayout.LayoutParams(-1,-2);
            cp.setMargins(0,dp(7),0,dp(7));

            LinearLayout labels=new LinearLayout(this);
            labels.setOrientation(LinearLayout.VERTICAL);
            TextView nm=text(name,19f,Color.WHITE);
            nm.setGravity(Gravity.START);
            nm.setTypeface(nm.getTypeface(),1);
            labels.addView(nm);
            TextView meta=text((ver.isEmpty()?"":("Versão "+ver+" • "))+(installed?"INSTALADO":"DISPONÍVEL"),14f,installed?Color.rgb(90,220,130):Color.LTGRAY);
            meta.setGravity(Gravity.START);
            labels.addView(meta);
            card.addView(labels,new LinearLayout.LayoutParams(0,-2,1f));

            Button action=new Button(this);
            action.setText(installed?"ABRIR":"INSTALAR");
            action.setFocusable(true);
            action.setOnClickListener(v->{
                if(isInstalled(pkg)){
                    Intent launch=getPackageManager().getLaunchIntentForPackage(pkg);
                    if(launch!=null) startActivity(launch); else Toast.makeText(this,"Aplicativo instalado, mas sem tela de abertura.",Toast.LENGTH_LONG).show();
                } else {
                    downloadAndInstall(token,qid,appId,name,pkg,dl);
                }
            });
            card.addView(action,new LinearLayout.LayoutParams(dp(170),dp(58)));
            list.addView(card,cp);
        }

        root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1f));
        Button logout=new Button(this);
        logout.setText("SAIR DA CONTA");
        logout.setOnClickListener(v->{prefs.edit().clear().apply();buildLoginUi();});
        root.addView(logout,new LinearLayout.LayoutParams(-1,dp(52)));
        setContentView(root);
    }

    private void downloadAndInstall(final String token, final String qid, final String appId, final String name, final String pkg, final String dl) {
        if(dl==null||dl.isEmpty()){Toast.makeText(this,"APK sem endereço de download.",Toast.LENGTH_LONG).show();return;}
        Toast.makeText(this,"Baixando "+name+"...",Toast.LENGTH_SHORT).show();
        new Thread(()->{
            try {
                File apk=downloadApk(dl,qid.isEmpty()?appId:qid);
                prefs.edit().putString(PREF_QUEUE,qid).apply();
                runOnUiThread(()->installApk(apk,pkg,name));
            } catch(Exception e){runOnUiThread(()->Toast.makeText(this,"Falha ao baixar: "+e.getMessage(),Toast.LENGTH_LONG).show());}
        }).start();
    }

    private File downloadApk(String downloadUrl,String qid) throws Exception {
        String u=downloadUrl.startsWith("http")?downloadUrl:BASE_URL+downloadUrl;
        HttpURLConnection conn=(HttpURLConnection)new URL(u).openConnection();
        conn.setConnectTimeout(15000);
        conn.setReadTimeout(60000);
        conn.connect();
        if(conn.getResponseCode()<200||conn.getResponseCode()>=300) throw new Exception("HTTP "+conn.getResponseCode());
        File dir=new File(getCacheDir(),"remote_apks");
        if(!dir.exists())dir.mkdirs();
        File out=new File(dir,"remote-"+qid+".apk");
        try(InputStream in=conn.getInputStream();FileOutputStream fos=new FileOutputStream(out)){
            byte[] buf=new byte[32768];int n;while((n=in.read(buf))>0)fos.write(buf,0,n);
        }
        conn.disconnect();
        return out;
    }

    private void installApk(File apk,String packageName,String name) {
        try {
            if(Build.VERSION.SDK_INT>=Build.VERSION_CODES.O && !getPackageManager().canRequestPackageInstalls()){
                waitingInstallPermission=true;
                Toast.makeText(this,"Autorize TUDO LIBERADO a instalar aplicativos.",Toast.LENGTH_LONG).show();
                startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:"+getPackageName())));
                return;
            }
            PackageInstaller installer=getPackageManager().getPackageInstaller();
            PackageInstaller.SessionParams params=new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
            if(packageName!=null&&!packageName.isEmpty())params.setAppPackageName(packageName);
            int sessionId=installer.createSession(params);
            PackageInstaller.Session session=installer.openSession(sessionId);
            try(InputStream in=new java.io.FileInputStream(apk);OutputStream out=session.openWrite("base.apk",0,apk.length())){
                byte[] b=new byte[32768];int n;while((n=in.read(b))>0)out.write(b,0,n);session.fsync(out);
            }
            Intent callback=new Intent(this,MainActivity.class);
            callback.setAction("com.bbl.boxtv.revenda.INSTALL_RESULT");
            int flags=PendingIntent.FLAG_UPDATE_CURRENT;
            if(Build.VERSION.SDK_INT>=31)flags|=PendingIntent.FLAG_MUTABLE;
            PendingIntent pi=PendingIntent.getActivity(this,sessionId,callback,flags);
            session.commit(pi.getIntentSender());
            session.close();
        } catch(Exception e){
            Toast.makeText(this,"Não foi possível iniciar o instalador: "+e.getMessage(),Toast.LENGTH_LONG).show();
            reportInstall("error",e.getMessage());
        }
    }

    private boolean handleInstallerCallback(Intent intent) {
        if(intent==null || !"com.bbl.boxtv.revenda.INSTALL_RESULT".equals(intent.getAction())) return false;
        int st=intent.getIntExtra(PackageInstaller.EXTRA_STATUS,PackageInstaller.STATUS_FAILURE);
        if(st==PackageInstaller.STATUS_PENDING_USER_ACTION){
            Intent confirm=intent.getParcelableExtra(Intent.EXTRA_INTENT);
            if(confirm!=null)startActivity(confirm);
            return true;
        }
        String msg=intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE);
        if(st==PackageInstaller.STATUS_SUCCESS){
            Toast.makeText(this,"Aplicativo instalado com sucesso.",Toast.LENGTH_LONG).show();
            reportInstall("done","instalado");
        } else {
            Toast.makeText(this,"Instalação não concluída.",Toast.LENGTH_LONG).show();
            reportInstall("error",msg==null?"falha":msg);
        }
        String token=prefs.getString(PREF_TOKEN,"");
        new Handler(getMainLooper()).postDelayed(()->loadAppCatalog(token),700);
        return true;
    }

    private void reportInstall(final String resultStatus,final String result) {
        final String token=prefs.getString(PREF_TOKEN,"");
        final String qid=prefs.getString(PREF_QUEUE,"");
        if(token==null||token.isEmpty()||qid==null||qid.isEmpty())return;
        prefs.edit().remove(PREF_QUEUE).apply();
        new Thread(()->{
            try{
                JSONObject j=new JSONObject();
                j.put("token",token);
                j.put("device_id",deviceId());
                j.put("queue_id",qid);
                j.put("status",resultStatus);
                j.put("result",result==null?"":result);
                postJson(APPS_RESULT_URL,j);
            }catch(Exception ignored){}
        }).start();
    }

    private void setBusy(boolean busy,String message){
        if(enterButton!=null)enterButton.setEnabled(!busy);
        if(userField!=null)userField.setEnabled(!busy);
        if(passField!=null)passField.setEnabled(!busy);
        if(progress!=null)progress.setVisibility(busy?View.VISIBLE:View.GONE);
        if(status!=null)status.setText(message);
    }

    private void openTudoLiberado() {
        Exception last=null;
        for(String activity:MOTOR_ACTIVITIES){
            try{
                Intent launch=new Intent(Intent.ACTION_MAIN);
                launch.setComponent(new ComponentName(MOTOR_PACKAGE,activity));
                launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
                startActivity(launch);
                return;
            }catch(Exception e){last=e;}
        }
        String detail=last==null?"atividade não encontrada":last.getClass().getSimpleName();
        Toast.makeText(this,"Motor instalado, mas não foi possível abrir ("+detail+").",Toast.LENGTH_LONG).show();
    }
}
