package com.bbl.boxtv.launcherv4;

import android.app.*;import android.os.*;import android.provider.Settings;import android.content.*;import android.content.pm.*;import android.graphics.*;import android.graphics.drawable.*;import android.net.Uri;import android.view.*;import android.widget.*;import java.util.*;

public class MainActivity extends Activity{
 FrameLayout root; SharedPreferences prefs; final int BW=1672,BH=941;
 @Override public void onCreate(Bundle b){super.onCreate(b);getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,WindowManager.LayoutParams.FLAG_FULLSCREEN);getWindow().getDecorView().setSystemUiVisibility(5894);prefs=getSharedPreferences("slots",0);build();}
 void build(){
  root=new FrameLayout(this);
  root.setBackgroundColor(Color.BLACK);
  root.setLayerType(View.LAYER_TYPE_SOFTWARE,null);
  root.setBackgroundResource(R.drawable.launcher_bg);
  Drawable d=root.getBackground();if(d!=null){d.setDither(true);}
  setContentView(root);
  root.post(()->layoutUI());
 }
 int X(int v){return Math.round(v*root.getWidth()/(float)BW);} int Y(int v){return Math.round(v*root.getHeight()/(float)BH);}
 GradientDrawable focusBg(boolean on){GradientDrawable g=new GradientDrawable();g.setColor(on?Color.argb(80,0,180,255):Color.TRANSPARENT);g.setCornerRadius(Y(18));g.setStroke(on?Y(4):Y(1),on?Color.CYAN:Color.TRANSPARENT);return g;}
 View zone(int x,int y,int w,int h,Runnable r){FrameLayout v=new FrameLayout(this);v.setFocusable(true);v.setBackground(focusBg(false));v.setOnFocusChangeListener((a,on)->{a.setBackground(focusBg(on));a.animate().scaleX(on?1.025f:1f).scaleY(on?1.025f:1f).setDuration(100).start();});v.setOnClickListener(a->r.run());FrameLayout.LayoutParams p=new FrameLayout.LayoutParams(X(w),Y(h));p.leftMargin=X(x);p.topMargin=Y(y);root.addView(v,p);return v;}
 void layoutUI(){
  zone(1126,114,187,55,()->openSettings());zone(1320,114,138,55,()->openWifi());zone(1467,114,153,55,()->openSupport());
  zone(1017,180,296,428,()->launchPreferred("unitv free","unitv"));zone(1323,180,296,428,()->launchPreferred("tudo liberado","tudo"));
  int[] xs={31,297,562,827,1093};for(int i=0;i<5;i++)addSlot(i,xs[i],630,257,207);zone(1359,630,258,207,()->showAllApps());
  View first=root.getChildAt(0);if(first!=null)first.requestFocus();
 }
 void addSlot(int idx,int x,int y,int w,int h){String pkg=prefs.getString("slot"+idx,"");FrameLayout box=new FrameLayout(this);box.setFocusable(true);box.setBackground(focusBg(false));FrameLayout.LayoutParams p=new FrameLayout.LayoutParams(X(w),Y(h));p.leftMargin=X(x);p.topMargin=Y(y);root.addView(box,p);box.setOnFocusChangeListener((v,on)->{v.setBackground(focusBg(on));v.animate().scaleX(on?1.03f:1f).scaleY(on?1.03f:1f).setDuration(100).start();});if(pkg.length()>0)fillSlot(box,pkg);box.setOnClickListener(v->{String cur=prefs.getString("slot"+idx,"");if(cur.length()==0)pickApp(idx);else launchPackage(cur);});box.setOnLongClickListener(v->{slotOptions(idx);return true;});}
 void fillSlot(FrameLayout box,String pkg){try{PackageManager pm=getPackageManager();ApplicationInfo ai=pm.getApplicationInfo(pkg,0);GradientDrawable gd=new GradientDrawable();gd.setColor(Color.argb(210,10,15,48));gd.setCornerRadius(Y(18));box.setBackground(gd);LinearLayout ll=new LinearLayout(this);ll.setOrientation(LinearLayout.VERTICAL);ll.setGravity(Gravity.CENTER);ImageView iv=new ImageView(this);iv.setImageDrawable(pm.getApplicationIcon(pkg));iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE);TextView tv=new TextView(this);tv.setText(pm.getApplicationLabel(ai));tv.setTextColor(Color.WHITE);tv.setTextSize(16);tv.setGravity(Gravity.CENTER);ll.addView(iv,new LinearLayout.LayoutParams(X(110),0,1));ll.addView(tv,new LinearLayout.LayoutParams(-1,Y(42)));box.addView(ll,new FrameLayout.LayoutParams(-1,-1));}catch(Exception e){}}
 List<ResolveInfo> apps(){Intent i=new Intent(Intent.ACTION_MAIN);i.addCategory(Intent.CATEGORY_LAUNCHER);List<ResolveInfo> a=getPackageManager().queryIntentActivities(i,0),o=new ArrayList<>();for(ResolveInfo r:a)if(!r.activityInfo.packageName.equals(getPackageName()))o.add(r);Collections.sort(o,(a1,b1)->a1.loadLabel(getPackageManager()).toString().compareToIgnoreCase(b1.loadLabel(getPackageManager()).toString()));return o;}
 void pickApp(final int idx){final List<ResolveInfo>a=apps();String[] n=new String[a.size()];for(int i=0;i<a.size();i++)n[i]=a.get(i).loadLabel(getPackageManager()).toString();new AlertDialog.Builder(this).setTitle("Escolher aplicativo").setItems(n,(d,w)->{prefs.edit().putString("slot"+idx,a.get(w).activityInfo.packageName).apply();recreate();}).setNegativeButton("Cancelar",null).show();}
 void slotOptions(final int idx){String pkg=prefs.getString("slot"+idx,"");if(pkg.length()==0){pickApp(idx);return;}new AlertDialog.Builder(this).setTitle("Atalho").setItems(new String[]{"Trocar aplicativo","Remover atalho"},(d,w)->{if(w==0)pickApp(idx);else{prefs.edit().remove("slot"+idx).apply();recreate();}}).show();}
 void showAllApps(){final List<ResolveInfo>a=apps();String[] n=new String[a.size()];for(int i=0;i<a.size();i++)n[i]=a.get(i).loadLabel(getPackageManager()).toString();new AlertDialog.Builder(this).setTitle("Meus Apps").setItems(n,(d,w)->launchPackage(a.get(w).activityInfo.packageName)).setNegativeButton("Fechar",null).show();}
 void launchPackage(String pkg){try{Intent i=getPackageManager().getLaunchIntentForPackage(pkg);if(i!=null)startActivity(i);}catch(Exception e){Toast.makeText(this,"Aplicativo não disponível",Toast.LENGTH_SHORT).show();}}
 void launchPreferred(String exact,String fallback){ResolveInfo best=null;for(ResolveInfo r:apps()){String s=(r.loadLabel(getPackageManager())+" "+r.activityInfo.packageName).toLowerCase();if(s.contains(exact)){best=r;break;}if(best==null&&s.contains(fallback))best=r;}if(best!=null)launchPackage(best.activityInfo.packageName);else Toast.makeText(this,"Aplicativo não instalado",Toast.LENGTH_SHORT).show();}
 void openSettings(){try{startActivity(new Intent(Settings.ACTION_SETTINGS));}catch(Exception e){}}
 void openWifi(){try{startActivity(new Intent(Settings.ACTION_WIFI_SETTINGS));}catch(Exception e){openSettings();}}
 void openSupport(){try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse("https://wa.me/5521988510594")));}catch(Exception e){Toast.makeText(this,"Suporte BBL.BOXTV",Toast.LENGTH_SHORT).show();}}
}
