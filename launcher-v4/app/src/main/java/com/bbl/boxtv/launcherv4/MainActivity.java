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

public class MainActivity extends Activity {
    FrameLayout root;
    TextView clock, date;
    final int CYAN = Color.rgb(22,220,255);
    final int ORANGE = Color.rgb(255,120,18);

    @Override public void onCreate(Bundle b){
        super.onCreate(b);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().getDecorView().setSystemUiVisibility(5894);
        build();
    }

    TextView text(String s, float sp, int gravity){
        TextView t = new TextView(this);
        t.setText(s); t.setTextSize(sp); t.setTextColor(Color.WHITE); t.setGravity(gravity);
        t.setShadowLayer(8,0,2,Color.BLACK);
        return t;
    }

    GradientDrawable panel(int fill, int stroke, float radius, int sw){
        GradientDrawable g = new GradientDrawable();
        g.setColor(fill); g.setCornerRadius(radius); g.setStroke(sw,stroke);
        return g;
    }

    void build(){
        root = new FrameLayout(this);
        root.setBackground(new CinematicDrawable());
        setContentView(root);

        // TOP BRAND
        TextView brand = text("BBL.BOX TV", 34, Gravity.CENTER);
        brand.setTypeface(null,Typeface.BOLD);
        brand.setTextColor(Color.rgb(255,210,135));
        FrameLayout.LayoutParams bp = new FrameLayout.LayoutParams(dp(470),dp(58),Gravity.TOP|Gravity.CENTER_HORIZONTAL);
        bp.topMargin=dp(8); root.addView(brand,bp);

        TextView slogan = text("O FUTURO ESTÁ AQUI",14,Gravity.CENTER);
        FrameLayout.LayoutParams sp = new FrameLayout.LayoutParams(dp(430),dp(30),Gravity.TOP|Gravity.CENTER_HORIZONTAL);
        sp.topMargin=dp(53); root.addView(slogan,sp);

        // CLOCK / DATE
        clock=text("",31,Gravity.RIGHT|Gravity.CENTER_VERTICAL); clock.setTypeface(null,Typeface.BOLD);
        FrameLayout.LayoutParams cp=new FrameLayout.LayoutParams(dp(180),dp(50),Gravity.TOP|Gravity.RIGHT);cp.topMargin=dp(8);cp.rightMargin=dp(34);root.addView(clock,cp);
        date=text("",13,Gravity.RIGHT|Gravity.CENTER_VERTICAL);
        FrameLayout.LayoutParams dp1=new FrameLayout.LayoutParams(dp(300),dp(32),Gravity.TOP|Gravity.RIGHT);dp1.topMargin=dp(49);dp1.rightMargin=dp(34);root.addView(date,dp1);

        // TOP ACTIONS under time
        LinearLayout actions=new LinearLayout(this); actions.setOrientation(LinearLayout.HORIZONTAL); actions.setGravity(Gravity.RIGHT);
        actions.addView(actionButton("⚙  Configurações",()->openSettings()),new LinearLayout.LayoutParams(dp(154),dp(42)));
        actions.addView(actionButton("Wi‑Fi",()->openWifi()),new LinearLayout.LayoutParams(dp(105),dp(42)));
        actions.addView(actionButton("Suporte",()->openSupport()),new LinearLayout.LayoutParams(dp(112),dp(42)));
        FrameLayout.LayoutParams ap=new FrameLayout.LayoutParams(dp(385),dp(44),Gravity.TOP|Gravity.RIGHT); ap.topMargin=dp(82);ap.rightMargin=dp(24);root.addView(actions,ap);

        // MAIN HERO AREA
        FrameLayout banner = banner();
        FrameLayout.LayoutParams banp=new FrameLayout.LayoutParams(0,0); banp.width=(int)(getResources().getDisplayMetrics().widthPixels*0.59f); banp.height=dp(305); banp.leftMargin=dp(26);banp.topMargin=dp(128);root.addView(banner,banp);

        int sw=getResources().getDisplayMetrics().widthPixels;
        int rightStart=(int)(sw*0.61f);
        int cardW=(sw-rightStart-dp(34))/2;
        View uni=featureCard("UniTV FREE", "unitv");
        FrameLayout.LayoutParams up=new FrameLayout.LayoutParams(cardW,dp(305));up.leftMargin=rightStart;up.topMargin=dp(128);root.addView(uni,up);
        View tudo=featureCard("TUDO LIBERADO", "tudo");
        FrameLayout.LayoutParams tp=new FrameLayout.LayoutParams(cardW,dp(305));tp.leftMargin=rightStart+cardW+dp(8);tp.topMargin=dp(128);root.addView(tudo,tp);

        // BOTTOM APP DOCK
        HorizontalScrollView hsv=new HorizontalScrollView(this); hsv.setHorizontalScrollBarEnabled(false); hsv.setClipToPadding(false); hsv.setPadding(dp(22),dp(4),dp(22),dp(4));
        LinearLayout dock=new LinearLayout(this); dock.setOrientation(LinearLayout.HORIZONTAL); dock.setGravity(Gravity.CENTER_VERTICAL);
        List<ResolveInfo> apps=apps(); int max=Math.min(apps.size(),10);
        for(int i=0;i<max;i++){ View c=appCard(apps.get(i)); LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(dp(205),dp(165));p.rightMargin=dp(10);dock.addView(c,p);}
        View more=simpleCard("▦","Mais Aplicativos",()->showAllApps()); LinearLayout.LayoutParams mp=new LinearLayout.LayoutParams(dp(205),dp(165));dock.addView(more,mp);
        hsv.addView(dock);
        FrameLayout.LayoutParams hp=new FrameLayout.LayoutParams(-1,dp(175),Gravity.BOTTOM);hp.bottomMargin=dp(58);root.addView(hsv,hp);

        // FOOTER
        LinearLayout footer=new LinearLayout(this);footer.setOrientation(LinearLayout.HORIZONTAL);footer.setGravity(Gravity.CENTER_VERTICAL);footer.setPadding(dp(24),0,dp(24),0);
        footer.setBackgroundColor(Color.argb(180,0,0,0));
        TextView left=text("⚙  Configurações      |      ▦  Aplicativos",16,Gravity.LEFT|Gravity.CENTER_VERTICAL);left.setOnClickListener(v->openSettings());left.setFocusable(true);
        TextView support=text("☏  Suporte: 21 98851‑0594",16,Gravity.RIGHT|Gravity.CENTER_VERTICAL);support.setOnClickListener(v->openSupport());support.setFocusable(true);
        footer.addView(left,new LinearLayout.LayoutParams(0,-1,1));footer.addView(support,new LinearLayout.LayoutParams(dp(380),-1));
        FrameLayout.LayoutParams fp=new FrameLayout.LayoutParams(-1,dp(56),Gravity.BOTTOM);root.addView(footer,fp);

        tick();
        if(dock.getChildCount()>0)dock.getChildAt(0).requestFocus();
    }

    FrameLayout banner(){
        FrameLayout f=new FrameLayout(this); f.setBackground(panel(Color.argb(130,0,0,0),Color.argb(210,180,200,255),dp(18),2));
        TextView title=text("BBL.BOX TV",64,Gravity.CENTER);title.setTypeface(null,Typeface.BOLD);title.setTextColor(Color.rgb(255,170,45));
        title.setShadowLayer(18,0,4,Color.RED);
        FrameLayout.LayoutParams p=new FrameLayout.LayoutParams(-1,dp(125),Gravity.CENTER);p.topMargin=dp(-30);f.addView(title,p);
        TextView sub=text("O MELHOR DO ENTRETENIMENTO EM UM SÓ LUGAR",19,Gravity.CENTER);sub.setTypeface(null,Typeface.BOLD);
        FrameLayout.LayoutParams s=new FrameLayout.LayoutParams(-1,dp(50),Gravity.BOTTOM);s.bottomMargin=dp(58);f.addView(sub,s);
        LinearLayout cats=new LinearLayout(this); cats.setGravity(Gravity.CENTER);String[] cs={"◉\nFILMES","▣\nSÉRIES","◉\nESPORTES","★\nINFANTIL","♫\nMÚSICA","◎\nCANAIS"};
        for(String c:cs){TextView t=text(c,12,Gravity.CENTER);cats.addView(t,new LinearLayout.LayoutParams(0,dp(62),1));}
        FrameLayout.LayoutParams ca=new FrameLayout.LayoutParams(-1,dp(64),Gravity.BOTTOM);ca.leftMargin=dp(10);ca.rightMargin=dp(10);ca.bottomMargin=dp(5);f.addView(cats,ca);
        return f;
    }

    View featureCard(String label,String key){
        LinearLayout c=new LinearLayout(this);c.setOrientation(LinearLayout.VERTICAL);c.setGravity(Gravity.CENTER);c.setPadding(dp(10),dp(12),dp(10),dp(12));
        c.setBackground(panel(Color.argb(175,20,25,80),Color.argb(210,180,205,255),dp(18),2));c.setFocusable(true);
        ImageView iv=new ImageView(this);ResolveInfo r=findApp(key);if(r!=null)iv.setImageDrawable(r.loadIcon(getPackageManager()));else iv.setImageResource(R.drawable.ic_bbl);iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        c.addView(iv,new LinearLayout.LayoutParams(dp(165),0,1));TextView t=text(label,17,Gravity.CENTER);t.setTypeface(null,Typeface.BOLD);c.addView(t,new LinearLayout.LayoutParams(-1,dp(45)));
        c.setOnClickListener(v->launchKey(key)); focus(c); return c;
    }

    View appCard(final ResolveInfo r){
        LinearLayout c=new LinearLayout(this);c.setOrientation(LinearLayout.VERTICAL);c.setGravity(Gravity.CENTER);c.setPadding(dp(8),dp(8),dp(8),dp(8));c.setFocusable(true);
        c.setBackground(panel(Color.argb(180,14,17,52),Color.argb(130,175,190,255),dp(12),2));
        ImageView iv=new ImageView(this);iv.setImageDrawable(r.loadIcon(getPackageManager()));iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE);c.addView(iv,new LinearLayout.LayoutParams(dp(100),dp(102)));
        String label=r.loadLabel(getPackageManager()).toString();TextView t=text(label,14,Gravity.CENTER);t.setSingleLine(true);c.addView(t,new LinearLayout.LayoutParams(-1,dp(42)));
        c.setOnClickListener(v->{Intent i=getPackageManager().getLaunchIntentForPackage(r.activityInfo.packageName);if(i!=null)startActivity(i);});focus(c);return c;
    }

    View simpleCard(String symbol,String label, final Runnable run){
        LinearLayout c=new LinearLayout(this);c.setOrientation(LinearLayout.VERTICAL);c.setGravity(Gravity.CENTER);c.setFocusable(true);c.setBackground(panel(Color.argb(180,14,17,52),Color.argb(130,175,190,255),dp(12),2));
        TextView a=text(symbol,48,Gravity.CENTER);c.addView(a,new LinearLayout.LayoutParams(-1,0,1));TextView t=text(label,14,Gravity.CENTER);c.addView(t,new LinearLayout.LayoutParams(-1,dp(40)));c.setOnClickListener(v->run.run());focus(c);return c;
    }

    View actionButton(String label, final Runnable run){
        TextView t=text(label,13,Gravity.CENTER);t.setFocusable(true);t.setPadding(dp(5),0,dp(5),0);t.setBackground(panel(Color.argb(165,0,0,0),Color.argb(150,255,255,255),dp(8),1));t.setOnClickListener(v->run.run());focus(t);return t;
    }

    void focus(View v){v.setOnFocusChangeListener((x,on)->{x.animate().scaleX(on?1.055f:1f).scaleY(on?1.055f:1f).setDuration(120).start();if(x instanceof TextView)((TextView)x).setTextColor(on?Color.YELLOW:Color.WHITE);if(on)x.setBackground(panel(Color.argb(210,16,86,150),CYAN,dp(12),4));else if(!(x instanceof TextView))x.setBackground(panel(Color.argb(180,14,17,52),Color.argb(130,175,190,255),dp(12),2));});}

    List<ResolveInfo> apps(){Intent i=new Intent(Intent.ACTION_MAIN);i.addCategory(Intent.CATEGORY_LAUNCHER);List<ResolveInfo> all=getPackageManager().queryIntentActivities(i,0),out=new ArrayList<>();for(ResolveInfo r:all)if(!r.activityInfo.packageName.equals(getPackageName()))out.add(r);Collections.sort(out,(a,b)->score(b)-score(a));return out;}
    int score(ResolveInfo r){String s=(r.loadLabel(getPackageManager())+" "+r.activityInfo.packageName).toLowerCase();if(s.contains("unitv"))return 100;if(s.contains("tudo"))return 95;if(s.contains("fast"))return 90;if(s.contains("anydesk"))return 85;if(s.contains("youtube"))return 80;if(s.contains("file")||s.contains("rs"))return 70;return 5;}
    ResolveInfo findApp(String key){for(ResolveInfo r:apps()){String s=(r.loadLabel(getPackageManager())+" "+r.activityInfo.packageName).toLowerCase();if(s.contains(key.toLowerCase()))return r;}return null;}
    void launchKey(String key){ResolveInfo r=findApp(key);if(r!=null){Intent i=getPackageManager().getLaunchIntentForPackage(r.activityInfo.packageName);if(i!=null)startActivity(i);}}
    void showAllApps(){Intent i=new Intent(Settings.ACTION_APPLICATION_SETTINGS);startActivity(i);}
    void openSettings(){try{startActivity(new Intent(Settings.ACTION_SETTINGS));}catch(Exception e){}}
    void openWifi(){try{startActivity(new Intent(Settings.ACTION_WIFI_SETTINGS));}catch(Exception e){openSettings();}}
    void openSupport(){try{Intent i=new Intent(Intent.ACTION_VIEW,Uri.parse("https://wa.me/5521988510594"));startActivity(i);}catch(Exception e){}}
    void tick(){Handler h=new Handler();h.post(new Runnable(){public void run(){Date d=new Date();clock.setText(new SimpleDateFormat("HH:mm",new Locale("pt","BR")).format(d));date.setText(new SimpleDateFormat("EEE, dd 'de' MMM 'de' yyyy",new Locale("pt","BR")).format(d));h.postDelayed(this,30000);}});}
    int dp(int v){return (int)(v*getResources().getDisplayMetrics().density+0.5f);}

    class CinematicDrawable extends Drawable{
        Paint p=new Paint(1); public void draw(Canvas c){Rect b=getBounds();
            LinearGradient base=new LinearGradient(0,0,b.width(),b.height(),new int[]{Color.rgb(2,3,12),Color.rgb(8,15,50),Color.rgb(30,2,8)},new float[]{0,0.55f,1},Shader.TileMode.CLAMP);p.setShader(base);c.drawRect(b,p);p.setShader(null);
            p.setStrokeWidth(dp(4));for(int i=0;i<12;i++){p.setColor(Color.argb(50+i*4,20,100+i*8,255));c.drawLine(0,i*dp(55),b.width(),(i*dp(55))+dp(120),p);}for(int i=0;i<8;i++){p.setColor(Color.argb(80,255,40+i*15,10));c.drawLine(b.width(),i*dp(90),0,(i*dp(90))+dp(210),p);} 
            RadialGradient rg=new RadialGradient(b.width()/2,dp(260),dp(430),new int[]{Color.argb(130,255,70,0),Color.TRANSPARENT},null,Shader.TileMode.CLAMP);p.setShader(rg);c.drawRect(b,p);p.setShader(null);
            p.setColor(Color.argb(160,255,90,20));p.setStrokeWidth(dp(2));c.drawLine(0,b.height()-dp(57),b.width(),b.height()-dp(57),p);
        }
        public void setAlpha(int a){} public void setColorFilter(android.graphics.ColorFilter f){} public int getOpacity(){return PixelFormat.OPAQUE;}
    }
}
