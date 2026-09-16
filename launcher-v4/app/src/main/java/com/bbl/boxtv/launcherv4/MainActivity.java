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

public class MainActivity extends Activity {
    FrameLayout root,banner,lockOverlay;
    SharedPreferences prefs;
    TextView clock,date,statusText;
    Handler handler=new Handler();
    BgView bgView;
    ImageView remoteBanner;
    final int BW=1280,BH=720;
    boolean blocked=false;
    final LinkedHashMap<String,String> allowedApps=new LinkedHashMap<>();
    final LinkedHashMap<String,String> allowedUrls=new LinkedHashMap<>();
    String lastPolicyHash="";

    int X(int v){return Math.round(v*root.getWidth()/(float)BW);} int Y(int v){return Math.round(v*root.getHeight()/(float)BH);}

    @Override public void onCreate(Bundle b){
        super.onCreate(b);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().getDecorView().setSystemUiVisibility(5894);
        prefs=getSharedPreferences("bbl_v4",0);
        if(prefs.getString("device_token","").isEmpty()) showActivation(); else buildLauncher();
    }
    @Override protected void onResume(){super.onResume(); if(root!=null && !prefs.getString("device_token","").isEmpty()){handler.postDelayed(()->loadRemoteTheme(),800);handler.postDelayed(()->fetchPolicy(),400);}}
    @Override protected void onDestroy(){handler.removeCallbacksAndMessages(null);super.onDestroy();}
    @Override public void onBackPressed(){if(blocked)return; super.onBackPressed();}

    TextView txt(String s,float sp,int gravity){TextView t=new TextView(this);t.setText(s);t.setTextSize(sp);t.setTextColor(Color.WHITE);t.setGravity(gravity);t.setShadowLayer(6,0,2,Color.BLACK);return t;}
    GradientDrawable panel(int fill,int stroke,int sw,int rad){GradientDrawable g=new GradientDrawable();g.setColor(fill);g.setStroke(sw,stroke);g.setCornerRadius(rad);return g;}

    String localDeviceId(){
        String id=Settings.Secure.getString(getContentResolver(),Settings.Secure.ANDROID_ID);
        if(id==null||id.trim().isEmpty()) id=Build.SERIAL;
        if(id==null||id.trim().isEmpty()) id="TVBOX"+Math.abs((Build.MODEL+Build.DEVICE).hashCode());
        return "V4-"+id.replaceAll("[^A-Za-z0-9]","").toUpperCase(Locale.US);
    }

    void showActivation(){
        LinearLayout base=new LinearLayout(this);base.setOrientation(LinearLayout.VERTICAL);base.setGravity(Gravity.CENTER);base.setPadding(90,60,90,60);
        GradientDrawable bg=new GradientDrawable(GradientDrawable.Orientation.TL_BR,new int[]{Color.rgb(1,4,16),Color.rgb(16,14,54),Color.rgb(50,4,14),Color.BLACK});base.setBackground(bg);
        TextView logo=txt("BBL.BOX TV",44,Gravity.CENTER);logo.setTypeface(null,1);logo.setTextColor(Color.rgb(255,185,70));base.addView(logo,new LinearLayout.LayoutParams(-1,90));
        TextView title=txt("ATIVACAO DA LAUNCHER",25,Gravity.CENTER);title.setTypeface(null,1);base.addView(title,new LinearLayout.LayoutParams(-1,70));
        TextView help=txt("Digite o codigo de acesso fornecido pelo suporte para vincular esta TV Box ao painel.",17,Gravity.CENTER);base.addView(help,new LinearLayout.LayoutParams(-1,80));
        EditText code=new EditText(this);code.setHint("Codigo de acesso");code.setTextColor(Color.WHITE);code.setHintTextColor(Color.LTGRAY);code.setSingleLine(true);code.setTextSize(20);code.setGravity(Gravity.CENTER);code.setBackground(panel(Color.argb(200,8,16,45),Color.CYAN,2,14));LinearLayout.LayoutParams ep=new LinearLayout.LayoutParams(600,70);ep.setMargins(0,20,0,16);base.addView(code,ep);
        Button activate=new Button(this);activate.setText("ATIVAR");activate.setTextSize(18);LinearLayout.LayoutParams ap=new LinearLayout.LayoutParams(300,64);base.addView(activate,ap);
        statusText=txt("ID: "+localDeviceId(),14,Gravity.CENTER);LinearLayout.LayoutParams stp=new LinearLayout.LayoutParams(-1,60);stp.setMargins(0,18,0,0);base.addView(statusText,stp);
        activate.setOnClickListener(v->{String c=code.getText().toString().trim();if(c.isEmpty()){statusText.setText("Digite o codigo de acesso.");return;}activate.setEnabled(false);statusText.setText("Ativando...");enroll(c,activate);});
        setContentView(base);code.requestFocus();
    }

    void enroll(String code,Button button){
        new Thread(()->{
            try{
                URL u=new URL(BuildConfig.API_BASE_URL+"/api/enroll");HttpURLConnection c=(HttpURLConnection)u.openConnection();c.setConnectTimeout(12000);c.setReadTimeout(12000);c.setRequestMethod("POST");c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");
                JSONObject j=new JSONObject();j.put("activationCode",code);j.put("deviceId",localDeviceId());j.put("manufacturer",Build.MANUFACTURER);j.put("model",Build.MODEL);j.put("android_version",Build.VERSION.RELEASE);j.put("launcher_version",BuildConfig.VERSION_NAME);
                OutputStream os=c.getOutputStream();os.write(j.toString().getBytes("UTF-8"));os.close();int rc=c.getResponseCode();InputStream in=(rc>=200&&rc<300)?c.getInputStream():c.getErrorStream();String body=readAll(in);c.disconnect();if(rc<200||rc>=300)throw new IOException("Codigo invalido ou acesso negado");JSONObject r=new JSONObject(body);String token=r.optString("device_token",r.optString("deviceToken",r.optString("token","")));String did=r.optString("device_id",r.optString("deviceId",localDeviceId()));if(token.isEmpty())throw new IOException("Servidor nao retornou token");prefs.edit().putString("device_token",token).putString("device_id",did).putString("activation_code",code).apply();runOnUiThread(()->{Toast.makeText(this,"Ativacao concluida",Toast.LENGTH_LONG).show();buildLauncher();});
            }catch(Exception e){runOnUiThread(()->{button.setEnabled(true);statusText.setText("Falha na ativacao: "+e.getMessage());});}
        }).start();
    }

    String readAll(InputStream in)throws Exception{if(in==null)return "";BufferedReader r=new BufferedReader(new InputStreamReader(in));StringBuilder s=new StringBuilder();String l;while((l=r.readLine())!=null)s.append(l);r.close();return s.toString();}

    void buildLauncher(){
        handler.removeCallbacksAndMessages(null);root=new FrameLayout(this);root.setBackgroundColor(Color.BLACK);bgView=new BgView(this);root.addView(bgView,new FrameLayout.LayoutParams(-1,-1));setContentView(root);root.post(()->{layoutUI();loadCachedTheme();loadRemoteTheme();fetchPolicy();});
    }

    void layoutUI(){
        TextView logo=txt("BBL.BOX TV",34,Gravity.CENTER);logo.setTypeface(null,1);logo.setTextColor(Color.rgb(255,185,70));FrameLayout.LayoutParams lp=new FrameLayout.LayoutParams(X(420),Y(54));lp.leftMargin=X(430);lp.topMargin=Y(14);root.addView(logo,lp);
        TextView sl=txt("O FUTURO ESTA AQUI",13,Gravity.CENTER);FrameLayout.LayoutParams sp=new FrameLayout.LayoutParams(X(360),Y(28));sp.leftMargin=X(460);sp.topMargin=Y(58);root.addView(sl,sp);
        clock=txt("",28,Gravity.RIGHT|Gravity.CENTER_VERTICAL);clock.setTypeface(null,1);FrameLayout.LayoutParams cp=new FrameLayout.LayoutParams(X(175),Y(42));cp.leftMargin=X(1080);cp.topMargin=Y(12);root.addView(clock,cp);
        date=txt("",12,Gravity.RIGHT|Gravity.CENTER_VERTICAL);FrameLayout.LayoutParams dp=new FrameLayout.LayoutParams(X(260),Y(28));dp.leftMargin=X(995);dp.topMargin=Y(49);root.addView(date,dp);startClock();
        addTop("Configuracoes",890,82,120,42,()->openSettings());addTop("Wi-Fi",1018,82,90,42,()->openWifi());addTop("Suporte",1116,82,120,42,()->openSupport());
        banner=new FrameLayout(this);banner.setBackground(panel(Color.argb(180,5,8,18),Color.rgb(80,210,255),2,18));FrameLayout.LayoutParams bp=new FrameLayout.LayoutParams(X(770),Y(330));bp.leftMargin=X(24);bp.topMargin=Y(132);root.addView(banner,bp);
        TextView b1=txt("BBL.BOX TV",55,Gravity.CENTER);b1.setTypeface(null,1);b1.setTextColor(Color.rgb(255,155,40));FrameLayout.LayoutParams b1p=new FrameLayout.LayoutParams(-1,Y(120));b1p.topMargin=Y(55);banner.addView(b1,b1p);
        TextView b2=txt("O MELHOR DO ENTRETENIMENTO EM UM SO LUGAR",17,Gravity.CENTER);b2.setTypeface(null,1);FrameLayout.LayoutParams b2p=new FrameLayout.LayoutParams(-1,Y(46));b2p.topMargin=Y(175);banner.addView(b2,b2p);
        LinearLayout cats=new LinearLayout(this);cats.setGravity(Gravity.CENTER);String[] cs={"FILMES","SERIES","ESPORTES","INFANTIL","MUSICA","CANAIS"};for(String c:cs){TextView t=txt(c,11,Gravity.CENTER);cats.addView(t,new LinearLayout.LayoutParams(0,-1,1));}FrameLayout.LayoutParams csp=new FrameLayout.LayoutParams(-1,Y(58),Gravity.BOTTOM);csp.leftMargin=X(12);csp.rightMargin=X(12);csp.bottomMargin=Y(12);banner.addView(cats,csp);
        remoteBanner=new ImageView(this);remoteBanner.setScaleType(ImageView.ScaleType.CENTER_CROP);remoteBanner.setLayerType(View.LAYER_TYPE_SOFTWARE,null);remoteBanner.setVisibility(View.GONE);banner.addView(remoteBanner,new FrameLayout.LayoutParams(-1,-1));
        addFeature("UniTV FREE","unitv",812,132,210,330);addFeature("TUDO LIBERADO","tudo",1034,132,222,330);
        int[] xs={24,232,440,648,856};for(int i=0;i<5;i++)addSlot(i,xs[i],486,196,185);addMyApps(1064,486,192,185);
        createLockOverlay();
    }

    void createLockOverlay(){
        lockOverlay=new FrameLayout(this);lockOverlay.setVisibility(View.GONE);lockOverlay.setFocusable(true);lockOverlay.setClickable(true);lockOverlay.setBackgroundColor(Color.rgb(4,7,17));
        LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);box.setGravity(Gravity.CENTER);FrameLayout.LayoutParams fp=new FrameLayout.LayoutParams(-1,-1);lockOverlay.addView(box,fp);
        TextView logo=txt("BBL.BOX TV",44,Gravity.CENTER);logo.setTypeface(null,1);logo.setTextColor(Color.rgb(255,185,70));box.addView(logo,new LinearLayout.LayoutParams(-1,90));
        TextView t=txt("ACESSO BLOQUEADO",34,Gravity.CENTER);t.setTypeface(null,1);t.setTextColor(Color.rgb(255,75,75));box.addView(t,new LinearLayout.LayoutParams(-1,75));
        TextView msg=txt("Esta TV Box esta temporariamente bloqueada.\nEntre em contato com o suporte para regularizar o acesso.",20,Gravity.CENTER);box.addView(msg,new LinearLayout.LayoutParams(-1,110));
        TextView sup=txt("Suporte: 21 98851-0594",18,Gravity.CENTER);box.addView(sup,new LinearLayout.LayoutParams(-1,60));
        root.addView(lockOverlay,new FrameLayout.LayoutParams(-1,-1));
    }

    void setBlocked(boolean value){blocked=value;if(lockOverlay==null)return;lockOverlay.setVisibility(value?View.VISIBLE:View.GONE);if(value){lockOverlay.bringToFront();lockOverlay.requestFocus();}}

    void fetchPolicy(){
        final String did=prefs.getString("device_id","");final String token=prefs.getString("device_token","");if(did.isEmpty()||token.isEmpty())return;
        new Thread(()->{
            try{
                String enc=URLEncoder.encode(did,"UTF-8");HttpURLConnection c=(HttpURLConnection)new URL(BuildConfig.API_BASE_URL+"/api/devices/"+enc+"/policy").openConnection();c.setConnectTimeout(9000);c.setReadTimeout(9000);c.setRequestProperty("Authorization","Bearer "+token);c.setRequestProperty("Accept","application/json");int rc=c.getResponseCode();if(rc==401||rc==403){prefs.edit().remove("device_token").apply();runOnUiThread(()->showActivation());c.disconnect();return;}if(rc<200||rc>=300){c.disconnect();return;}JSONObject j=new JSONObject(readAll(c.getInputStream()));c.disconnect();boolean lock=j.optBoolean("locked",false)||j.optBoolean("expired",false);JSONArray arr=j.optJSONArray("apps");LinkedHashMap<String,String> names=new LinkedHashMap<>();LinkedHashMap<String,String> urls=new LinkedHashMap<>();if(arr!=null){for(int i=0;i<arr.length();i++){JSONObject a=arr.optJSONObject(i);if(a==null)continue;String p=a.optString("package_name","").trim();if(p.isEmpty())continue;names.put(p,a.optString("name",p));urls.put(p,abs(a.optString("download_url","")));}}
                String hash=lock+"|"+names.keySet().toString();runOnUiThread(()->{allowedApps.clear();allowedApps.putAll(names);allowedUrls.clear();allowedUrls.putAll(urls);setBlocked(lock);if(!hash.equals(lastPolicyHash)){lastPolicyHash=hash;sanitizeSlots();if(!lock)refreshSlotsVisual();}});
            }catch(Exception e){}finally{handler.postDelayed(()->fetchPolicy(),15000);}
        }).start();
    }

    void sanitizeSlots(){for(int i=0;i<5;i++){String p=prefs.getString("slot"+i,"");if(!p.isEmpty()&&!allowedApps.containsKey(p))prefs.edit().remove("slot"+i).apply();}}
    void refreshSlotsVisual(){if(root!=null)root.postDelayed(()->{if(!blocked)buildLauncher();},150);}

    void addTop(String s,int x,int y,int w,int h,Runnable r){TextView t=txt(s,12,Gravity.CENTER);t.setFocusable(true);t.setBackground(panel(Color.argb(185,4,10,26),Color.rgb(30,205,255),2,12));t.setOnFocusChangeListener((v,on)->{v.setScaleX(on?1.06f:1);v.setScaleY(on?1.06f:1);v.setBackground(panel(on?Color.argb(220,0,95,150):Color.argb(185,4,10,26),on?Color.CYAN:Color.rgb(30,205,255),on?4:2,12));});t.setOnClickListener(v->{if(!blocked)r.run();});FrameLayout.LayoutParams p=new FrameLayout.LayoutParams(X(w),Y(h));p.leftMargin=X(x);p.topMargin=Y(y);root.addView(t,p);}

    void addFeature(String label,String key,int x,int y,int w,int h){LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);box.setGravity(Gravity.CENTER);box.setFocusable(true);box.setPadding(X(10),Y(10),X(10),Y(10));box.setBackground(panel(Color.argb(210,9,15,48),Color.rgb(70,215,255),2,18));ResolveInfo r=findApp(key);ImageView iv=new ImageView(this);iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE);if(r!=null)iv.setImageDrawable(r.loadIcon(getPackageManager()));else iv.setImageResource(R.drawable.ic_bbl);box.addView(iv,new LinearLayout.LayoutParams(X(135),0,1));TextView tv=txt(label,16,Gravity.CENTER);tv.setTypeface(null,1);box.addView(tv,new LinearLayout.LayoutParams(-1,Y(48)));box.setOnClickListener(v->{if(!blocked)launchPreferred(key);});box.setOnFocusChangeListener((v,on)->{v.setScaleX(on?1.04f:1);v.setScaleY(on?1.04f:1);v.setBackground(panel(on?Color.argb(230,8,70,140):Color.argb(210,9,15,48),on?Color.CYAN:Color.rgb(70,215,255),on?4:2,18));});FrameLayout.LayoutParams p=new FrameLayout.LayoutParams(X(w),Y(h));p.leftMargin=X(x);p.topMargin=Y(y);root.addView(box,p);}

    void addSlot(int idx,int x,int y,int w,int h){String pkg=prefs.getString("slot"+idx,"");FrameLayout box=new FrameLayout(this);box.setFocusable(true);box.setBackground(panel(Color.argb(205,10,14,45),Color.rgb(70,130,255),2,16));FrameLayout.LayoutParams p=new FrameLayout.LayoutParams(X(w),Y(h));p.leftMargin=X(x);p.topMargin=Y(y);root.addView(box,p);if(pkg.length()>0&&allowedApps.containsKey(pkg))fillSlot(box,pkg);else{TextView plus=txt("+",58,Gravity.CENTER);plus.setTypeface(null,1);box.addView(plus,new FrameLayout.LayoutParams(-1,-1));}box.setOnClickListener(v->{if(blocked)return;String cur=prefs.getString("slot"+idx,"");if(cur.length()==0||!allowedApps.containsKey(cur))pickApp(idx);else launchPackage(cur);});box.setOnLongClickListener(v->{if(!blocked)slotOptions(idx);return true;});box.setOnFocusChangeListener((v,on)->{v.setScaleX(on?1.05f:1);v.setScaleY(on?1.05f:1);v.setBackground(panel(on?Color.argb(235,8,65,125):Color.argb(205,10,14,45),on?Color.CYAN:Color.rgb(70,130,255),on?4:2,16));});}

    void addMyApps(int x,int y,int w,int h){LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);box.setGravity(Gravity.CENTER);box.setFocusable(true);box.setBackground(panel(Color.argb(205,10,14,45),Color.rgb(70,130,255),2,16));TextView icon=txt("[ ] [ ]\n[ ] [ ]",28,Gravity.CENTER);TextView label=txt("Meus Apps",16,Gravity.CENTER);box.addView(icon,new LinearLayout.LayoutParams(-1,0,1));box.addView(label,new LinearLayout.LayoutParams(-1,Y(48)));box.setOnClickListener(v->{if(!blocked)showManagedApps();});box.setOnFocusChangeListener((v,on)->{v.setScaleX(on?1.05f:1);v.setScaleY(on?1.05f:1);v.setBackground(panel(on?Color.argb(235,8,65,125):Color.argb(205,10,14,45),on?Color.CYAN:Color.rgb(70,130,255),on?4:2,16));});FrameLayout.LayoutParams p=new FrameLayout.LayoutParams(X(w),Y(h));p.leftMargin=X(x);p.topMargin=Y(y);root.addView(box,p);}

    void fillSlot(FrameLayout box,String pkg){try{PackageManager pm=getPackageManager();ApplicationInfo ai=pm.getApplicationInfo(pkg,0);LinearLayout ll=new LinearLayout(this);ll.setOrientation(LinearLayout.VERTICAL);ll.setGravity(Gravity.CENTER);ImageView iv=new ImageView(this);iv.setImageDrawable(pm.getApplicationIcon(pkg));iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE);TextView tv=txt(allowedApps.containsKey(pkg)?allowedApps.get(pkg):pm.getApplicationLabel(ai).toString(),14,Gravity.CENTER);ll.addView(iv,new LinearLayout.LayoutParams(X(92),0,1));ll.addView(tv,new LinearLayout.LayoutParams(-1,Y(40)));box.addView(ll,new FrameLayout.LayoutParams(-1,-1));}catch(Exception e){}}

    List<ResolveInfo> allInstalled(){Intent i=new Intent(Intent.ACTION_MAIN);i.addCategory(Intent.CATEGORY_LAUNCHER);List<ResolveInfo>a=getPackageManager().queryIntentActivities(i,0),o=new ArrayList<>();for(ResolveInfo r:a)if(!r.activityInfo.packageName.equals(getPackageName()))o.add(r);Collections.sort(o,(a1,b1)->a1.loadLabel(getPackageManager()).toString().compareToIgnoreCase(b1.loadLabel(getPackageManager()).toString()));return o;}
    List<ResolveInfo> managedInstalled(){List<ResolveInfo> out=new ArrayList<>();for(ResolveInfo r:allInstalled())if(allowedApps.containsKey(r.activityInfo.packageName))out.add(r);return out;}
    ResolveInfo findApp(String key){for(ResolveInfo r:allInstalled()){String s=(r.loadLabel(getPackageManager())+" "+r.activityInfo.packageName).toLowerCase();if(s.contains(key))return r;}return null;}
    void launchPreferred(String key){ResolveInfo r=findApp(key);if(r!=null)launchPackage(r.activityInfo.packageName);else Toast.makeText(this,"Aplicativo nao instalado",Toast.LENGTH_SHORT).show();}

    void pickApp(final int idx){final List<ResolveInfo>a=managedInstalled();if(a.isEmpty()){Toast.makeText(this,"Nenhum aplicativo liberado no painel para este cliente",Toast.LENGTH_LONG).show();return;}String[] n=new String[a.size()];for(int i=0;i<a.size();i++)n[i]=allowedApps.get(a.get(i).activityInfo.packageName);new AlertDialog.Builder(this).setTitle("Escolher aplicativo").setItems(n,(d,w)->{prefs.edit().putString("slot"+idx,a.get(w).activityInfo.packageName).apply();buildLauncher();}).setNegativeButton("Cancelar",null).show();}
    void slotOptions(final int idx){String pkg=prefs.getString("slot"+idx,"");if(pkg.length()==0){pickApp(idx);return;}new AlertDialog.Builder(this).setTitle("Atalho").setItems(new String[]{"Trocar aplicativo","Remover atalho"},(d,w)->{if(w==0)pickApp(idx);else{prefs.edit().remove("slot"+idx).apply();buildLauncher();}}).show();}

    void showManagedApps(){if(allowedApps.isEmpty()){new AlertDialog.Builder(this).setTitle("Meus Apps").setMessage("Nenhum aplicativo foi liberado no painel para este cliente.").setPositiveButton("Fechar",null).show();return;}final ArrayList<String> pkgs=new ArrayList<>(allowedApps.keySet());String[] n=new String[pkgs.size()];for(int i=0;i<pkgs.size();i++){String p=pkgs.get(i);n[i]=allowedApps.get(p)+(isInstalled(p)?"":"  [INSTALAR]");}new AlertDialog.Builder(this).setTitle("Meus Apps").setItems(n,(d,w)->{String p=pkgs.get(w);if(isInstalled(p))launchPackage(p);else openInstallUrl(p);}).setNegativeButton("Fechar",null).show();}
    boolean isInstalled(String pkg){try{getPackageManager().getPackageInfo(pkg,0);return true;}catch(Exception e){return false;}}
    void openInstallUrl(String pkg){String u=allowedUrls.get(pkg);if(u==null||u.isEmpty()){Toast.makeText(this,"APK sem link de instalacao no painel",Toast.LENGTH_LONG).show();return;}try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(u)));}catch(Exception e){Toast.makeText(this,"Nao foi possivel abrir o instalador",Toast.LENGTH_LONG).show();}}
    void launchPackage(String pkg){if(blocked)return;try{Intent i=getPackageManager().getLaunchIntentForPackage(pkg);if(i!=null)startActivity(i);}catch(Exception e){}}

    void openSettings(){try{startActivity(new Intent(Settings.ACTION_SETTINGS));}catch(Exception e){}}
    void openWifi(){try{startActivity(new Intent(Settings.ACTION_WIFI_SETTINGS));}catch(Exception e){openSettings();}}
    void openSupport(){try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse("https://wa.me/5521988510594")));}catch(Exception e){}}
    void startClock(){handler.post(new Runnable(){public void run(){if(clock==null)return;Date d=new Date();clock.setText(new SimpleDateFormat("HH:mm:ss",new Locale("pt","BR")).format(d));date.setText(new SimpleDateFormat("EEE, dd 'de' MMM 'de' yyyy",new Locale("pt","BR")).format(d));handler.postDelayed(this,1000);}});}

    String abs(String u){if(u==null||u.trim().length()==0)return "";u=u.trim();if(u.startsWith("http://")||u.startsWith("https://"))return u;return BuildConfig.API_BASE_URL.replaceAll("/$","")+"/"+u.replaceFirst("^/","");}
    byte[] getBytes(String url)throws Exception{HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();c.setConnectTimeout(10000);c.setReadTimeout(15000);c.setInstanceFollowRedirects(true);c.setRequestProperty("Accept","image/*,*/*");try{if(c.getResponseCode()<200||c.getResponseCode()>299)throw new IOException("HTTP "+c.getResponseCode());ByteArrayOutputStream o=new ByteArrayOutputStream();InputStream in=c.getInputStream();byte[] b=new byte[16384];int n;while((n=in.read(b))>0)o.write(b,0,n);in.close();return o.toByteArray();}finally{c.disconnect();}}
    Bitmap decode(byte[] data){try{BitmapFactory.Options o=new BitmapFactory.Options();o.inPreferredConfig=Bitmap.Config.RGB_565;o.inDither=true;return BitmapFactory.decodeByteArray(data,0,data.length,o);}catch(Exception e){return null;}}
    void saveCache(String name,byte[] data){try{FileOutputStream f=openFileOutput(name,MODE_PRIVATE);f.write(data);f.close();}catch(Exception e){}}
    Bitmap loadCache(String name){try{FileInputStream f=openFileInput(name);BitmapFactory.Options o=new BitmapFactory.Options();o.inPreferredConfig=Bitmap.Config.RGB_565;o.inDither=true;Bitmap b=BitmapFactory.decodeStream(f,null,o);f.close();return b;}catch(Exception e){return null;}}
    void loadCachedTheme(){Bitmap w=loadCache("panel_wallpaper.img");if(w!=null)bgView.setRemote(w);Bitmap b=loadCache("panel_banner.img");if(b!=null&&remoteBanner!=null){remoteBanner.setImageBitmap(b);remoteBanner.setVisibility(View.VISIBLE);}}
    void loadRemoteTheme(){if(root==null)return;new Thread(()->{try{HttpURLConnection c=(HttpURLConnection)new URL(BuildConfig.API_BASE_URL+"/api/launcher-v4/theme").openConnection();c.setConnectTimeout(8000);c.setReadTimeout(8000);c.setRequestProperty("Accept","application/json");String text;try{if(c.getResponseCode()!=200)return;text=readAll(c.getInputStream());}finally{c.disconnect();}JSONObject j=new JSONObject(text);String wu=abs(j.optString("wallpaper_url",""));String bu=abs(j.optString("banner_url",""));final Bitmap[] wb={null};final Bitmap[] bb={null};if(wu.length()>0){byte[] d=getBytes(wu);saveCache("panel_wallpaper.img",d);wb[0]=decode(d);}if(bu.length()>0){byte[] d=getBytes(bu);saveCache("panel_banner.img",d);bb[0]=decode(d);}runOnUiThread(()->{if(root==null)return;if(wb[0]!=null)bgView.setRemote(wb[0]);if(remoteBanner!=null){if(bb[0]!=null){remoteBanner.setImageBitmap(bb[0]);remoteBanner.setVisibility(View.VISIBLE);}else if(bu.length()==0)remoteBanner.setVisibility(View.GONE);}});}catch(Exception e){}finally{handler.postDelayed(()->loadRemoteTheme(),60000);}}).start();}

    class BgView extends View{
        Paint p=new Paint(3);Bitmap remote;
        public BgView(Context c){super(c);setLayerType(View.LAYER_TYPE_SOFTWARE,null);}
        void setRemote(Bitmap b){remote=b;invalidate();}
        protected void onDraw(Canvas c){super.onDraw(c);int w=getWidth(),h=getHeight();LinearGradient g=new LinearGradient(0,0,w,h,new int[]{Color.rgb(2,4,15),Color.rgb(8,15,55),Color.rgb(35,3,12),Color.BLACK},null,Shader.TileMode.CLAMP);p.setShader(g);c.drawRect(0,0,w,h,p);p.setShader(null);if(remote!=null){Rect src=new Rect(0,0,remote.getWidth(),remote.getHeight());RectF dst=new RectF(0,0,w,h);p.setAlpha(255);c.drawBitmap(remote,src,dst,p);p.setAlpha(255);}}
    }
}
