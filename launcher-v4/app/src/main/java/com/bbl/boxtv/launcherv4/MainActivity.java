package com.bbl.boxtv.launcherv4;

import android.app.*;
import android.os.*;
import android.provider.Settings;
import android.content.*;
import android.content.pm.*;
import android.graphics.*;
import android.graphics.drawable.*;
import android.net.Uri;
import android.view.*;
import android.widget.*;
import java.text.*;
import java.util.*;
import java.net.*;
import java.io.*;
import org.json.*;
import com.google.zxing.*;
import com.google.zxing.common.*;
import com.google.zxing.qrcode.*;

public class MainActivity extends Activity {
    FrameLayout root,banner,lockOverlay;
    SharedPreferences prefs;
    TextView clock,date,statusText,userText;
    Handler handler=new Handler();
    BgView bgView;
    ImageView remoteBanner;
    final int BW=1280,BH=720;
    boolean blocked=false;
    String tudoPackage="com.rtxapps.reuse";
    final String PREFS="bbl_base2_launcher";

    int X(int v){return root==null||root.getWidth()==0?v:Math.round(v*root.getWidth()/(float)BW);}
    int Y(int v){return root==null||root.getHeight()==0?v:Math.round(v*root.getHeight()/(float)BH);}

    @Override public void onCreate(Bundle b){
        super.onCreate(b);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().getDecorView().setSystemUiVisibility(5894);
        prefs=getSharedPreferences(PREFS,0);
        tudoPackage=prefs.getString("tudo_package","com.rtxapps.reuse");
        if(prefs.getString("base2_token","").isEmpty()) showLogin(); else buildLauncher(true);
    }

    @Override protected void onResume(){
        super.onResume();
        if(root!=null&&!prefs.getString("base2_token","").isEmpty()){
            handler.postDelayed(()->checkAccess(),400);
            handler.postDelayed(()->loadRemoteTheme(),800);
        }
    }
    @Override protected void onDestroy(){handler.removeCallbacksAndMessages(null);super.onDestroy();}
    @Override public void onBackPressed(){if(blocked)return;}

    TextView txt(String s,float sp,int gravity){
        TextView t=new TextView(this);t.setText(s);t.setTextSize(sp);t.setTextColor(Color.WHITE);t.setGravity(gravity);t.setShadowLayer(6,0,2,Color.BLACK);return t;
    }
    GradientDrawable panel(int fill,int stroke,int sw,int rad){GradientDrawable g=new GradientDrawable();g.setColor(fill);g.setStroke(sw,stroke);g.setCornerRadius(rad);return g;}

    String localDeviceId(){
        String id=Settings.Secure.getString(getContentResolver(),Settings.Secure.ANDROID_ID);
        if(id==null||id.trim().isEmpty()) id=Build.SERIAL;
        if(id==null||id.trim().isEmpty()) id="TVBOX"+Math.abs((Build.MODEL+Build.DEVICE).hashCode());
        return "BBL-"+id.replaceAll("[^A-Za-z0-9]","").toUpperCase(Locale.US);
    }

    void showLogin(){
        handler.removeCallbacksAndMessages(null);
        LinearLayout base=new LinearLayout(this);base.setOrientation(LinearLayout.VERTICAL);base.setGravity(Gravity.CENTER);base.setPadding(90,45,90,45);
        GradientDrawable bg=new GradientDrawable(GradientDrawable.Orientation.TL_BR,new int[]{Color.rgb(1,4,16),Color.rgb(15,13,54),Color.rgb(55,5,15),Color.BLACK});base.setBackground(bg);
        TextView logo=txt("TUDO LIBERADO",48,Gravity.CENTER);logo.setTypeface(null,1);logo.setTextColor(Color.rgb(255,185,70));base.addView(logo,new LinearLayout.LayoutParams(-1,85));
        TextView sub=txt("BBL.BOXTV • LAUNCHER",20,Gravity.CENTER);sub.setTypeface(null,1);base.addView(sub,new LinearLayout.LayoutParams(-1,52));
        TextView help=txt("Acesse com usuario e senha cadastrados no painel BBL.BOXTV.",16,Gravity.CENTER);base.addView(help,new LinearLayout.LayoutParams(-1,55));

        EditText user=new EditText(this);user.setHint("Usuario");user.setSingleLine(true);user.setTextColor(Color.WHITE);user.setHintTextColor(Color.LTGRAY);user.setTextSize(20);user.setGravity(Gravity.CENTER);user.setBackground(panel(Color.argb(210,8,16,45),Color.CYAN,2,14));
        LinearLayout.LayoutParams up=new LinearLayout.LayoutParams(600,68);up.setMargins(0,8,0,12);base.addView(user,up);
        EditText pass=new EditText(this);pass.setHint("Senha");pass.setSingleLine(true);pass.setInputType(0x00000081);pass.setTextColor(Color.WHITE);pass.setHintTextColor(Color.LTGRAY);pass.setTextSize(20);pass.setGravity(Gravity.CENTER);pass.setBackground(panel(Color.argb(210,8,16,45),Color.CYAN,2,14));
        LinearLayout.LayoutParams pp=new LinearLayout.LayoutParams(600,68);pp.setMargins(0,0,0,16);base.addView(pass,pp);

        Button entrar=new Button(this);entrar.setText("ENTRAR");entrar.setTextSize(18);base.addView(entrar,new LinearLayout.LayoutParams(310,62));
        statusText=txt("ID: "+localDeviceId(),14,Gravity.CENTER);LinearLayout.LayoutParams sp=new LinearLayout.LayoutParams(-1,60);sp.setMargins(0,14,0,0);base.addView(statusText,sp);
        TextView sup=txt("Suporte: 21 98851-0594",14,Gravity.CENTER);base.addView(sup,new LinearLayout.LayoutParams(-1,44));

        View.OnClickListener go=v->{
            String u=user.getText().toString().trim(),p=pass.getText().toString();
            if(u.isEmpty()||p.isEmpty()){statusText.setText("Digite usuario e senha.");return;}
            entrar.setEnabled(false);statusText.setText("Validando acesso...");loginBase2(u,p,entrar);
        };
        entrar.setOnClickListener(go);pass.setOnEditorActionListener((v,a,e)->{go.onClick(pass);return true;});
        setContentView(base);user.requestFocus();
    }

    void loginBase2(String username,String password,Button button){
        new Thread(()->{
            try{
                HttpURLConnection c=(HttpURLConnection)new URL(BuildConfig.API_BASE_URL+"/base2/api/login").openConnection();
                c.setConnectTimeout(12000);c.setReadTimeout(12000);c.setRequestMethod("POST");c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");c.setRequestProperty("Accept","application/json");
                JSONObject j=new JSONObject();j.put("username",username);j.put("password",password);j.put("device_id",localDeviceId());
                OutputStream os=c.getOutputStream();os.write(j.toString().getBytes("UTF-8"));os.close();
                int rc=c.getResponseCode();String body=readAll((rc>=200&&rc<300)?c.getInputStream():c.getErrorStream());c.disconnect();
                JSONObject r=new JSONObject(body.length()>0?body:"{}");
                if(rc<200||rc>=300||!r.optBoolean("ok",false)){
                    String er=r.optString("error","acesso_negado");
                    if("invalid_credentials".equals(er)) throw new IOException("Usuario ou senha invalidos");
                    if("blocked".equals(er)) throw new IOException("Cliente bloqueado no painel");
                    if("expired".equals(er)) throw new IOException("Acesso vencido");
                    if("device_in_use".equals(er)) throw new IOException("Usuario vinculado a outro aparelho");
                    throw new IOException("Acesso negado");
                }
                String token=r.optString("token","");if(token.isEmpty())throw new IOException("Token nao recebido");
                String pkg=r.optString("package_name","com.rtxapps.reuse");
                prefs.edit().putString("base2_token",token).putString("username",username).putString("tudo_package",pkg).putString("expires_at",r.optString("expires_at","")).apply();
                tudoPackage=pkg;
                runOnUiThread(()->{Toast.makeText(this,"Acesso liberado",Toast.LENGTH_SHORT).show();buildLauncher(false);handler.postDelayed(()->launchTudo(),900);});
            }catch(Exception e){runOnUiThread(()->{button.setEnabled(true);statusText.setText(e.getMessage());});}
        }).start();
    }

    String readAll(InputStream in)throws Exception{if(in==null)return "";BufferedReader r=new BufferedReader(new InputStreamReader(in));StringBuilder s=new StringBuilder();String l;while((l=r.readLine())!=null)s.append(l);r.close();return s.toString();}

    void buildLauncher(boolean autoOpen){
        handler.removeCallbacksAndMessages(null);blocked=false;
        root=new FrameLayout(this);root.setBackgroundColor(Color.BLACK);bgView=new BgView(this);root.addView(bgView,new FrameLayout.LayoutParams(-1,-1));setContentView(root);
        root.post(()->{layoutUI();loadCachedTheme();loadRemoteTheme();checkAccess();if(autoOpen)handler.postDelayed(()->launchTudo(),1100);});
    }

    void layoutUI(){
        TextView logo=txt("TUDO LIBERADO",34,Gravity.CENTER);logo.setTypeface(null,1);logo.setTextColor(Color.rgb(255,185,70));FrameLayout.LayoutParams lp=new FrameLayout.LayoutParams(X(420),Y(54));lp.leftMargin=X(430);lp.topMargin=Y(12);root.addView(logo,lp);
        TextView sl=txt("BBL.BOXTV • O MELHOR DO ENTRETENIMENTO EM UM SO LUGAR",12,Gravity.CENTER);FrameLayout.LayoutParams slp=new FrameLayout.LayoutParams(X(500),Y(28));slp.leftMargin=X(390);slp.topMargin=Y(58);root.addView(sl,slp);
        clock=txt("",28,Gravity.RIGHT|Gravity.CENTER_VERTICAL);clock.setTypeface(null,1);FrameLayout.LayoutParams cp=new FrameLayout.LayoutParams(X(175),Y(42));cp.leftMargin=X(1080);cp.topMargin=Y(10);root.addView(clock,cp);
        date=txt("",12,Gravity.RIGHT|Gravity.CENTER_VERTICAL);FrameLayout.LayoutParams dp=new FrameLayout.LayoutParams(X(260),Y(28));dp.leftMargin=X(995);dp.topMargin=Y(48);root.addView(date,dp);startClock();
        addTop("Configuracoes",850,82,128,42,()->openSettings());addTop("Wi-Fi",986,82,92,42,()->openWifi());addTop("Suporte",1086,82,168,42,()->openSupport());

        banner=new FrameLayout(this);banner.setBackground(panel(Color.argb(178,5,8,18),Color.rgb(80,210,255),2,18));FrameLayout.LayoutParams bp=new FrameLayout.LayoutParams(X(775),Y(330));bp.leftMargin=X(24);bp.topMargin=Y(132);root.addView(banner,bp);
        TextView b1=txt("TUDO LIBERADO",52,Gravity.CENTER);b1.setTypeface(null,1);b1.setTextColor(Color.rgb(255,155,40));FrameLayout.LayoutParams b1p=new FrameLayout.LayoutParams(-1,Y(110));b1p.topMargin=Y(52);banner.addView(b1,b1p);
        TextView b2=txt("FILMES • SERIES • CANAIS • ESPORTES • INFANTIL",17,Gravity.CENTER);b2.setTypeface(null,1);FrameLayout.LayoutParams b2p=new FrameLayout.LayoutParams(-1,Y(48));b2p.topMargin=Y(165);banner.addView(b2,b2p);
        userText=txt("Cliente: "+prefs.getString("username",""),14,Gravity.CENTER);FrameLayout.LayoutParams usp=new FrameLayout.LayoutParams(-1,Y(38));usp.topMargin=Y(218);banner.addView(userText,usp);
        remoteBanner=new ImageView(this);remoteBanner.setScaleType(ImageView.ScaleType.CENTER_CROP);remoteBanner.setVisibility(View.GONE);banner.addView(remoteBanner,new FrameLayout.LayoutParams(-1,-1));

        addFeature("TUDO LIBERADO","tudo",815,132,215,330);addFeature("UniTV FREE","unitv_free",1040,132,216,330);
        addFixedApp("AnyDesk","anydesk",24,486,196,185);addFixedApp("RS File Manager","rs file",232,486,196,185);addFixedApp("YOUTUBE","youtube",440,486,196,185);addFixedApp("YouTube Premium","youtube premium",648,486,196,185);addFixedApp("STV FUTEBOL","stv futebol",856,486,196,185);addFixedApp("Tudo Liberado Oculto","oculto",1064,486,192,185);
        createLockOverlay();
    }

    void checkAccess(){
        final String token=prefs.getString("base2_token","");if(token.isEmpty())return;
        new Thread(()->{
            try{
                HttpURLConnection c=(HttpURLConnection)new URL(BuildConfig.API_BASE_URL+"/base2/api/check").openConnection();c.setConnectTimeout(9000);c.setReadTimeout(9000);c.setRequestMethod("POST");c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");
                JSONObject j=new JSONObject();j.put("token",token);j.put("device_id",localDeviceId());OutputStream os=c.getOutputStream();os.write(j.toString().getBytes("UTF-8"));os.close();int rc=c.getResponseCode();String body=readAll((rc>=200&&rc<300)?c.getInputStream():c.getErrorStream());c.disconnect();
                JSONObject r=new JSONObject(body.length()>0?body:"{}");boolean ok=rc>=200&&rc<300&&r.optBoolean("ok",false);
                if(ok){String p=r.optString("package_name",tudoPackage);if(!p.isEmpty()){tudoPackage=p;prefs.edit().putString("tudo_package",p).apply();}runOnUiThread(()->setBlocked(false));}
                else{runOnUiThread(()->{setBlocked(true);handler.postDelayed(()->{prefs.edit().remove("base2_token").apply();showLogin();},2500);});}
            }catch(Exception e){}finally{if(!prefs.getString("base2_token","").isEmpty())handler.postDelayed(()->checkAccess(),15000);}
        }).start();
    }

    void createLockOverlay(){
        lockOverlay=new FrameLayout(this);lockOverlay.setVisibility(View.GONE);lockOverlay.setFocusable(true);lockOverlay.setClickable(true);lockOverlay.setBackgroundColor(Color.rgb(4,7,17));
        LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);box.setGravity(Gravity.CENTER);lockOverlay.addView(box,new FrameLayout.LayoutParams(-1,-1));
        TextView logo=txt("BBL.BOX TV",44,Gravity.CENTER);logo.setTypeface(null,1);logo.setTextColor(Color.rgb(255,185,70));box.addView(logo,new LinearLayout.LayoutParams(-1,90));
        TextView t=txt("ACESSO BLOQUEADO",34,Gravity.CENTER);t.setTypeface(null,1);t.setTextColor(Color.rgb(255,75,75));box.addView(t,new LinearLayout.LayoutParams(-1,75));
        TextView msg=txt("Acesso bloqueado ou vencido.\nEntre em contato com o suporte.",20,Gravity.CENTER);box.addView(msg,new LinearLayout.LayoutParams(-1,105));
        TextView sup=txt("Suporte: 21 98851-0594",18,Gravity.CENTER);box.addView(sup,new LinearLayout.LayoutParams(-1,60));root.addView(lockOverlay,new FrameLayout.LayoutParams(-1,-1));
    }
    void setBlocked(boolean value){blocked=value;if(lockOverlay==null)return;lockOverlay.setVisibility(value?View.VISIBLE:View.GONE);if(value){lockOverlay.bringToFront();lockOverlay.requestFocus();}}

    void addTop(String s,int x,int y,int w,int h,Runnable r){TextView t=txt(s,12,Gravity.CENTER);t.setFocusable(true);t.setBackground(panel(Color.argb(185,4,10,26),Color.rgb(30,205,255),2,12));t.setOnFocusChangeListener((v,on)->{v.setScaleX(on?1.06f:1);v.setScaleY(on?1.06f:1);v.setBackground(panel(on?Color.argb(220,0,95,150):Color.argb(185,4,10,26),on?Color.CYAN:Color.rgb(30,205,255),on?4:2,12));});t.setOnClickListener(v->{if(!blocked)r.run();});FrameLayout.LayoutParams p=new FrameLayout.LayoutParams(X(w),Y(h));p.leftMargin=X(x);p.topMargin=Y(y);root.addView(t,p);}

    void addFeature(String label,String key,int x,int y,int w,int h){
        LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);box.setGravity(Gravity.CENTER);box.setFocusable(true);box.setPadding(X(10),Y(10),X(10),Y(10));box.setBackground(panel(Color.argb(210,9,15,48),Color.rgb(70,215,255),2,18));
        ResolveInfo r="tudo".equals(key)?resolvePackage(tudoPackage):("unitv_free".equals(key)?findFirstByLabels("UniTV Free","UniTV FREE","UniTVFree"):findApp(key));ImageView iv=new ImageView(this);iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE);if(r!=null)iv.setImageDrawable(r.loadIcon(getPackageManager()));else iv.setImageResource(R.drawable.ic_bbl);box.addView(iv,new LinearLayout.LayoutParams(X(135),0,1));TextView tv=txt(label,16,Gravity.CENTER);tv.setTypeface(null,1);box.addView(tv,new LinearLayout.LayoutParams(-1,Y(48)));
        box.setOnClickListener(v->{if(blocked)return;if("tudo".equals(key))launchTudo();else if("unitv_free".equals(key))launchUniTVFree();else launchPreferred(key);});box.setOnFocusChangeListener((v,on)->{v.setScaleX(on?1.04f:1);v.setScaleY(on?1.04f:1);v.setBackground(panel(on?Color.argb(230,8,70,140):Color.argb(210,9,15,48),on?Color.CYAN:Color.rgb(70,215,255),on?4:2,18));});FrameLayout.LayoutParams p=new FrameLayout.LayoutParams(X(w),Y(h));p.leftMargin=X(x);p.topMargin=Y(y);root.addView(box,p);
    }

    void addSlot(int idx,int x,int y,int w,int h){String pkg=prefs.getString("slot"+idx,"");FrameLayout box=new FrameLayout(this);box.setFocusable(true);box.setBackground(panel(Color.argb(205,10,14,45),Color.rgb(70,130,255),2,16));FrameLayout.LayoutParams p=new FrameLayout.LayoutParams(X(w),Y(h));p.leftMargin=X(x);p.topMargin=Y(y);root.addView(box,p);if(pkg.length()>0&&isInstalled(pkg))fillSlot(box,pkg);else{TextView plus=txt("+",58,Gravity.CENTER);plus.setTypeface(null,1);box.addView(plus,new FrameLayout.LayoutParams(-1,-1));}box.setOnClickListener(v->{if(blocked)return;String cur=prefs.getString("slot"+idx,"");if(cur.length()==0||!isInstalled(cur))pickApp(idx);else launchPackage(cur);});box.setOnLongClickListener(v->{if(!blocked)slotOptions(idx);return true;});box.setOnFocusChangeListener((v,on)->{v.setScaleX(on?1.05f:1);v.setScaleY(on?1.05f:1);v.setBackground(panel(on?Color.argb(235,8,65,125):Color.argb(205,10,14,45),on?Color.CYAN:Color.rgb(70,130,255),on?4:2,16));});}
    void fillSlot(FrameLayout box,String pkg){try{PackageManager pm=getPackageManager();ApplicationInfo ai=pm.getApplicationInfo(pkg,0);LinearLayout ll=new LinearLayout(this);ll.setOrientation(LinearLayout.VERTICAL);ll.setGravity(Gravity.CENTER);ImageView iv=new ImageView(this);iv.setImageDrawable(pm.getApplicationIcon(pkg));iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE);TextView tv=txt(pm.getApplicationLabel(ai).toString(),14,Gravity.CENTER);ll.addView(iv,new LinearLayout.LayoutParams(X(92),0,1));ll.addView(tv,new LinearLayout.LayoutParams(-1,Y(40)));box.addView(ll,new FrameLayout.LayoutParams(-1,-1));}catch(Exception e){}}

    void addFixedApp(String label,String key,int x,int y,int w,int h){
        LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);box.setGravity(Gravity.CENTER);box.setFocusable(true);box.setPadding(X(8),Y(8),X(8),Y(8));box.setBackground(panel(Color.argb(205,10,14,45),Color.rgb(70,130,255),2,16));
        ResolveInfo r=findFirstByLabels(label,key);
        ImageView iv=new ImageView(this);iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        if(r!=null)iv.setImageDrawable(r.loadIcon(getPackageManager()));else iv.setImageResource(R.drawable.ic_bbl);
        box.addView(iv,new LinearLayout.LayoutParams(X(105),0,1));
        TextView tv=txt(label,13,Gravity.CENTER);tv.setTypeface(null,1);box.addView(tv,new LinearLayout.LayoutParams(-1,Y(42)));
        box.setOnClickListener(v->{if(blocked)return;ResolveInfo app=findFirstByLabels(label,key);if(app!=null)launchRaw(app.activityInfo.packageName);else Toast.makeText(this,label+" nao instalado",Toast.LENGTH_SHORT).show();});
        box.setOnFocusChangeListener((v,on)->{v.setScaleX(on?1.05f:1);v.setScaleY(on?1.05f:1);v.setBackground(panel(on?Color.argb(235,8,65,125):Color.argb(205,10,14,45),on?Color.CYAN:Color.rgb(70,130,255),on?4:2,16));});
        FrameLayout.LayoutParams p=new FrameLayout.LayoutParams(X(w),Y(h));p.leftMargin=X(x);p.topMargin=Y(y);root.addView(box,p);
    }

    void addAllApps(int x,int y,int w,int h){LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);box.setGravity(Gravity.CENTER);box.setFocusable(true);box.setBackground(panel(Color.argb(205,10,14,45),Color.rgb(70,130,255),2,16));TextView icon=txt("[ ] [ ]\n[ ] [ ]",28,Gravity.CENTER);TextView label=txt("Meus Apps",16,Gravity.CENTER);box.addView(icon,new LinearLayout.LayoutParams(-1,0,1));box.addView(label,new LinearLayout.LayoutParams(-1,Y(48)));box.setOnClickListener(v->{if(!blocked)showAllApps();});box.setOnFocusChangeListener((v,on)->{v.setScaleX(on?1.05f:1);v.setScaleY(on?1.05f:1);v.setBackground(panel(on?Color.argb(235,8,65,125):Color.argb(205,10,14,45),on?Color.CYAN:Color.rgb(70,130,255),on?4:2,16));});FrameLayout.LayoutParams p=new FrameLayout.LayoutParams(X(w),Y(h));p.leftMargin=X(x);p.topMargin=Y(y);root.addView(box,p);}

    List<ResolveInfo> allInstalled(){Intent i=new Intent(Intent.ACTION_MAIN);i.addCategory(Intent.CATEGORY_LAUNCHER);List<ResolveInfo>a=getPackageManager().queryIntentActivities(i,0),o=new ArrayList<>();for(ResolveInfo r:a)if(!r.activityInfo.packageName.equals(getPackageName()))o.add(r);Collections.sort(o,(a1,b1)->a1.loadLabel(getPackageManager()).toString().compareToIgnoreCase(b1.loadLabel(getPackageManager()).toString()));return o;}
    ResolveInfo resolvePackage(String pkg){for(ResolveInfo r:allInstalled())if(r.activityInfo.packageName.equals(pkg))return r;return null;}
    ResolveInfo findApp(String key){for(ResolveInfo r:allInstalled()){String s=(r.loadLabel(getPackageManager())+" "+r.activityInfo.packageName).toLowerCase(Locale.US);if(s.contains(key.toLowerCase(Locale.US)))return r;}return null;}
    ResolveInfo findAppExact(String label){
        String wanted=label==null?"":label.trim().toLowerCase(Locale.US);
        for(ResolveInfo r:allInstalled()){
            String l=r.loadLabel(getPackageManager()).toString().trim().toLowerCase(Locale.US);
            if(l.equals(wanted))return r;
        }
        return null;
    }
    ResolveInfo findFirstByLabels(String... labels){
        for(String s:labels){ResolveInfo r=findAppExact(s);if(r!=null)return r;}
        for(String s:labels){ResolveInfo r=findApp(s);if(r!=null)return r;}
        return null;
    }
    boolean isInstalled(String pkg){try{getPackageManager().getPackageInfo(pkg,0);return true;}catch(Exception e){return false;}}
    void launchPreferred(String key){
        ResolveInfo r=findApp(key);
        if(r!=null) launchRaw(r.activityInfo.packageName);
        else Toast.makeText(this,"Aplicativo nao instalado",Toast.LENGTH_SHORT).show();
    }
    void launchUniTVFree(){
        ResolveInfo r=findFirstByLabels("UniTV Free","UniTV FREE","UniTVFree");
        if(r!=null) launchRaw(r.activityInfo.packageName);
        else Toast.makeText(this,"UniTV Free nao esta instalado",Toast.LENGTH_LONG).show();
    }

    void launchTudo(){
        if(blocked)return;
        if(isInstalled(tudoPackage)){launchRaw(tudoPackage);return;}
        ResolveInfo r=findApp("tudo");if(r==null)r=findApp("liberado");
        if(r!=null){
            tudoPackage=r.activityInfo.packageName;
            prefs.edit().putString("tudo_package",tudoPackage).apply();
            launchRaw(tudoPackage);
        }else Toast.makeText(this,"Tudo Liberado nao esta instalado",Toast.LENGTH_LONG).show();
    }
    void launchRaw(String pkg){
        try{
            Intent i=getPackageManager().getLaunchIntentForPackage(pkg);
            if(i!=null){i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);startActivity(i);}
        }catch(Exception e){}
    }

    void launchThroughTudo(String targetPkg){
        if(blocked||targetPkg==null||targetPkg.trim().isEmpty())return;
        if(targetPkg.equals(tudoPackage)){launchTudo();return;}
        if(!isInstalled(tudoPackage)){
            ResolveInfo tr=findApp("tudo");if(tr==null)tr=findApp("liberado");
            if(tr!=null){tudoPackage=tr.activityInfo.packageName;prefs.edit().putString("tudo_package",tudoPackage).apply();}
        }
        if(!isInstalled(tudoPackage)){
            Toast.makeText(this,"Tudo Liberado nao esta instalado",Toast.LENGTH_LONG).show();
            return;
        }
        try{
            Intent b=new Intent("com.bbl.TUDO_LIBERADO.OPEN_APP");
            b.setPackage(tudoPackage);
            b.putExtra("package_name",targetPkg);
            b.putExtra("target_package",targetPkg);
            b.putExtra("app_package",targetPkg);
            b.putExtra("pkg",targetPkg);
            sendBroadcast(b);
        }catch(Exception e){}
        try{
            Intent i=getPackageManager().getLaunchIntentForPackage(tudoPackage);
            if(i!=null){
                i.putExtra("package_name",targetPkg);
                i.putExtra("target_package",targetPkg);
                i.putExtra("app_package",targetPkg);
                i.putExtra("pkg",targetPkg);
                i.putExtra("bbl_target_package",targetPkg);
                i.putExtra("open_app",true);
                i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_SINGLE_TOP|Intent.FLAG_ACTIVITY_CLEAR_TOP);
                startActivity(i);
                return;
            }
        }catch(Exception e){}
        Toast.makeText(this,"Nao foi possivel encaminhar o aplicativo pelo Tudo Liberado",Toast.LENGTH_LONG).show();
    }

    void launchPackage(String pkg){launchRaw(pkg);}

    void pickApp(final int idx){final List<ResolveInfo>a=allInstalled();if(a.isEmpty())return;String[] n=new String[a.size()];for(int i=0;i<a.size();i++)n[i]=a.get(i).loadLabel(getPackageManager()).toString();new AlertDialog.Builder(this).setTitle("Escolher aplicativo").setItems(n,(d,w)->{prefs.edit().putString("slot"+idx,a.get(w).activityInfo.packageName).apply();buildLauncher(false);}).setNegativeButton("Cancelar",null).show();}
    void slotOptions(final int idx){String pkg=prefs.getString("slot"+idx,"");if(pkg.length()==0){pickApp(idx);return;}new AlertDialog.Builder(this).setTitle("Atalho").setItems(new String[]{"Trocar aplicativo","Remover atalho"},(d,w)->{if(w==0)pickApp(idx);else{prefs.edit().remove("slot"+idx).apply();buildLauncher(false);}}).show();}
    void showAllApps(){final List<ResolveInfo>a=allInstalled();if(a.isEmpty())return;String[] n=new String[a.size()];for(int i=0;i<a.size();i++)n[i]=a.get(i).loadLabel(getPackageManager()).toString();new AlertDialog.Builder(this).setTitle("Meus Apps").setItems(n,(d,w)->launchThroughTudo(a.get(w).activityInfo.packageName)).setNegativeButton("Fechar",null).show();}

    void logout(){new AlertDialog.Builder(this).setTitle("Sair").setMessage("Deseja remover o login desta TV Box?").setPositiveButton("SIM",(d,w)->{prefs.edit().clear().apply();showLogin();}).setNegativeButton("NAO",null).show();}
    void openSettings(){try{startActivity(new Intent(Settings.ACTION_SETTINGS));}catch(Exception e){}}
    void openWifi(){try{startActivity(new Intent(Settings.ACTION_WIFI_SETTINGS));}catch(Exception e){openSettings();}}
    void openSupport(){
        try{
            LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);box.setGravity(Gravity.CENTER);box.setPadding(28,22,28,22);
            TextView title=txt("SUPORTE BBL.BOXTV",22,Gravity.CENTER);title.setTypeface(null,1);box.addView(title,new LinearLayout.LayoutParams(-1,58));
            ImageView qr=new ImageView(this);qr.setScaleType(ImageView.ScaleType.CENTER_INSIDE);qr.setImageBitmap(makeQr("tel:+5521988510594",420));box.addView(qr,new LinearLayout.LayoutParams(430,430));
            TextView phone=txt("(21) 98851-0594",24,Gravity.CENTER);phone.setTypeface(null,1);box.addView(phone,new LinearLayout.LayoutParams(-1,70));
            new AlertDialog.Builder(this).setView(box).setPositiveButton("FECHAR",null).show();
        }catch(Exception e){Toast.makeText(this,"Suporte: (21) 98851-0594",Toast.LENGTH_LONG).show();}
    }
    Bitmap makeQr(String text,int size)throws Exception{
        BitMatrix m=new QRCodeWriter().encode(text,BarcodeFormat.QR_CODE,size,size);
        Bitmap b=Bitmap.createBitmap(size,size,Bitmap.Config.ARGB_8888);
        for(int y=0;y<size;y++)for(int x=0;x<size;x++)b.setPixel(x,y,m.get(x,y)?Color.BLACK:Color.WHITE);
        return b;
    }
    void startClock(){handler.post(new Runnable(){public void run(){if(clock==null)return;Date d=new Date();clock.setText(new SimpleDateFormat("HH:mm:ss",new Locale("pt","BR")).format(d));date.setText(new SimpleDateFormat("EEE, dd 'de' MMM 'de' yyyy",new Locale("pt","BR")).format(d));handler.postDelayed(this,1000);}});}

    String abs(String u){if(u==null||u.trim().length()==0)return "";u=u.trim();if(u.startsWith("http://")||u.startsWith("https://"))return u;return BuildConfig.API_BASE_URL.replaceAll("/$","")+"/"+u.replaceFirst("^/","");}
    byte[] getBytes(String url)throws Exception{HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();c.setConnectTimeout(10000);c.setReadTimeout(15000);c.setInstanceFollowRedirects(true);c.setRequestProperty("Accept","image/*,*/*");try{if(c.getResponseCode()<200||c.getResponseCode()>299)throw new IOException("HTTP "+c.getResponseCode());ByteArrayOutputStream o=new ByteArrayOutputStream();InputStream in=c.getInputStream();byte[] b=new byte[16384];int n;while((n=in.read(b))>0)o.write(b,0,n);in.close();return o.toByteArray();}finally{c.disconnect();}}
    Bitmap decode(byte[] data){try{BitmapFactory.Options o=new BitmapFactory.Options();o.inPreferredConfig=Bitmap.Config.RGB_565;o.inDither=true;return BitmapFactory.decodeByteArray(data,0,data.length,o);}catch(Exception e){return null;}}
    void saveCache(String name,byte[] data){try{File tmp=new File(getFilesDir(),name+".tmp");FileOutputStream f=new FileOutputStream(tmp);f.write(data);f.flush();f.close();Bitmap test=decode(data);if(test==null){tmp.delete();return;}File dst=new File(getFilesDir(),name);if(dst.exists())dst.delete();tmp.renameTo(dst);}catch(Exception e){}}
    void deleteCache(String name){try{new File(getFilesDir(),name).delete();new File(getFilesDir(),name+".tmp").delete();}catch(Exception e){}}
    Bitmap loadCache(String name){try{FileInputStream f=openFileInput(name);BitmapFactory.Options o=new BitmapFactory.Options();o.inPreferredConfig=Bitmap.Config.RGB_565;o.inDither=true;Bitmap b=BitmapFactory.decodeStream(f,null,o);f.close();return b;}catch(Exception e){return null;}}
    void loadCachedTheme(){Bitmap w=loadCache("panel_wallpaper.img");if(w!=null)bgView.setRemote(w);Bitmap b=loadCache("panel_banner.img");if(b!=null&&remoteBanner!=null){remoteBanner.setImageBitmap(b);remoteBanner.setVisibility(View.VISIBLE);}}
    void loadRemoteTheme(){if(root==null)return;new Thread(()->{try{HttpURLConnection c=(HttpURLConnection)new URL(BuildConfig.API_BASE_URL+"/api/launcher-v4/theme").openConnection();c.setConnectTimeout(8000);c.setReadTimeout(8000);c.setRequestProperty("Accept","application/json");String text;try{if(c.getResponseCode()!=200)return;text=readAll(c.getInputStream());}finally{c.disconnect();}JSONObject j=new JSONObject(text);String wu=abs(j.optString("wallpaper_url",""));String bu=abs(j.optString("banner_url",""));final Bitmap[] wb={null};final Bitmap[] bb={null};if(wu.length()>0){byte[] d=getBytes(wu);Bitmap x=decode(d);if(x!=null){saveCache("panel_wallpaper.img",d);wb[0]=x;}}else deleteCache("panel_wallpaper.img");if(bu.length()>0){byte[] d=getBytes(bu);Bitmap x=decode(d);if(x!=null){saveCache("panel_banner.img",d);bb[0]=x;}}else deleteCache("panel_banner.img");runOnUiThread(()->{if(root==null)return;if(wu.length()==0)bgView.setRemote(null);else if(wb[0]!=null)bgView.setRemote(wb[0]);if(remoteBanner!=null){if(bu.length()==0){remoteBanner.setImageDrawable(null);remoteBanner.setVisibility(View.GONE);}else if(bb[0]!=null){remoteBanner.setImageBitmap(bb[0]);remoteBanner.setVisibility(View.VISIBLE);}}});}catch(Exception e){}finally{if(root!=null)handler.postDelayed(()->loadRemoteTheme(),60000);}}).start();}

    class BgView extends View{
        Paint p=new Paint(3);Bitmap remote;
        public BgView(Context c){super(c);setLayerType(View.LAYER_TYPE_SOFTWARE,null);}
        void setRemote(Bitmap b){remote=b;invalidate();}
        protected void onDraw(Canvas c){super.onDraw(c);int w=getWidth(),h=getHeight();LinearGradient g=new LinearGradient(0,0,w,h,new int[]{Color.rgb(2,4,15),Color.rgb(8,15,55),Color.rgb(35,3,12),Color.BLACK},null,Shader.TileMode.CLAMP);p.setShader(g);c.drawRect(0,0,w,h,p);p.setShader(null);if(remote!=null){Rect src=new Rect(0,0,remote.getWidth(),remote.getHeight());RectF dst=new RectF(0,0,w,h);p.setAlpha(255);c.drawBitmap(remote,src,dst,p);p.setAlpha(255);}}
    }
}
