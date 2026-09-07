package com.bbl.boxtv.revenda;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
    private static final String LOGIN_URL="https://bbl-tvbox-manager-v2.onrender.com/base2/api/login";
    private static final String CHECK_URL="https://bbl-tvbox-manager-v2.onrender.com/base2/api/check";
    private static final String MOTOR_PACKAGE="com.rtxapps.reuse";
    private static final String PREFS="tudo_liberado_auth";
    private static final String PREF_TOKEN="token";
    private static final String[] MOTOR_ACTIVITIES={"top.niunaijun.blackboxa.view.main.LauncherActivity","top.niunaijun.blackbox.app.LauncherActivity"};
    private EditText userField,passField; private Button enterButton; private ProgressBar progress; private TextView status; private SharedPreferences prefs;

    @Override protected void onCreate(Bundle b){super.onCreate(b);prefs=getSharedPreferences(PREFS,Context.MODE_PRIVATE);buildUi();String t=prefs.getString(PREF_TOKEN,"");if(t!=null&&!t.trim().isEmpty())checkSavedLogin(t.trim());}
    private int dp(int v){return Math.round(v*getResources().getDisplayMetrics().density);}
    private TextView text(String v,float s,int c){TextView t=new TextView(this);t.setText(v);t.setTextSize(s);t.setTextColor(c);t.setGravity(Gravity.CENTER);return t;}
    private void buildUi(){LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setGravity(Gravity.CENTER);root.setPadding(dp(40),dp(30),dp(40),dp(30));root.setBackgroundColor(Color.rgb(5,12,22));TextView logo=text("TUDO LIBERADO",32f,Color.WHITE);logo.setTypeface(logo.getTypeface(),1);root.addView(logo,new LinearLayout.LayoutParams(-1,-2));TextView sub=text("ACESSO CONTROLADO",17f,Color.rgb(93,188,255));sub.setPadding(0,dp(4),0,dp(26));root.addView(sub,new LinearLayout.LayoutParams(-1,-2));LinearLayout card=new LinearLayout(this);card.setOrientation(LinearLayout.VERTICAL);card.setPadding(dp(28),dp(24),dp(28),dp(24));card.setBackgroundColor(Color.rgb(14,35,58));root.addView(card,new LinearLayout.LayoutParams(dp(520),-2));TextView title=text("Entre com seu usuário e senha",18f,Color.WHITE);title.setGravity(Gravity.START);title.setPadding(0,0,0,dp(14));card.addView(title);userField=new EditText(this);userField.setHint("Usuário");userField.setSingleLine(true);userField.setTextColor(Color.WHITE);userField.setHintTextColor(Color.rgb(150,170,190));userField.setBackgroundColor(Color.rgb(7,24,42));userField.setPadding(dp(16),dp(12),dp(16),dp(12));LinearLayout.LayoutParams fp=new LinearLayout.LayoutParams(-1,dp(58));fp.setMargins(0,dp(6),0,dp(10));card.addView(userField,fp);passField=new EditText(this);passField.setHint("Senha");passField.setSingleLine(true);passField.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);passField.setTextColor(Color.WHITE);passField.setHintTextColor(Color.rgb(150,170,190));passField.setBackgroundColor(Color.rgb(7,24,42));passField.setPadding(dp(16),dp(12),dp(16),dp(12));LinearLayout.LayoutParams pp=new LinearLayout.LayoutParams(-1,dp(58));pp.setMargins(0,0,0,dp(14));card.addView(passField,pp);enterButton=new Button(this);enterButton.setText("ENTRAR");enterButton.setTextSize(17f);enterButton.setFocusable(true);enterButton.setOnClickListener(v->login());card.addView(enterButton,new LinearLayout.LayoutParams(-1,dp(58)));progress=new ProgressBar(this);progress.setVisibility(View.GONE);LinearLayout.LayoutParams pr=new LinearLayout.LayoutParams(dp(42),dp(42));pr.gravity=Gravity.CENTER_HORIZONTAL;pr.setMargins(0,dp(14),0,0);card.addView(progress,pr);status=text("",15f,Color.LTGRAY);status.setPadding(0,dp(10),0,0);card.addView(status,new LinearLayout.LayoutParams(-1,-2));TextView footer=text("Acesso controlado remotamente pelo painel de revenda.",14f,Color.rgb(150,170,190));footer.setPadding(0,dp(24),0,0);root.addView(footer,new LinearLayout.LayoutParams(-1,-2));setContentView(root);userField.requestFocus();}
    private String deviceId(){String id=Settings.Secure.getString(getContentResolver(),Settings.Secure.ANDROID_ID);if(id==null||id.trim().isEmpty())id=android.os.Build.SERIAL;if(id==null||id.trim().isEmpty())id="unknown-device";return id.trim();}
    private String post(String endpoint,JSONObject json,int[] code)throws Exception{HttpURLConnection c=(HttpURLConnection)new URL(endpoint).openConnection();c.setConnectTimeout(12000);c.setReadTimeout(12000);c.setRequestMethod("POST");c.setRequestProperty("Content-Type","application/json; charset=UTF-8");c.setRequestProperty("Accept","application/json");c.setDoOutput(true);try(OutputStream os=c.getOutputStream()){os.write(json.toString().getBytes(StandardCharsets.UTF_8));}code[0]=c.getResponseCode();InputStream in=code[0]>=200&&code[0]<400?c.getInputStream():c.getErrorStream();StringBuilder sb=new StringBuilder();if(in!=null){BufferedReader br=new BufferedReader(new InputStreamReader(in,StandardCharsets.UTF_8));String line;while((line=br.readLine())!=null)sb.append(line);}c.disconnect();return sb.toString();}
    private void checkSavedLogin(final String token){setBusy(true,"Entrando automaticamente...");new Thread(()->{try{JSONObject j=new JSONObject();j.put("token",token);j.put("device_id",deviceId());int[] code={-1};String body=post(CHECK_URL,j,code);runOnUiThread(()->{if(code[0]>=200&&code[0]<300){setBusy(false,"Acesso liberado.");openTudoLiberado();}else{prefs.edit().remove(PREF_TOKEN).commit();setBusy(false,"Sessão encerrada. Entre novamente.");}});}catch(Exception e){runOnUiThread(()->setBusy(false,"Sem conexão. Tente novamente."));}}).start();}
    private void login(){final String u=userField.getText().toString().trim(),p=passField.getText().toString();if(u.isEmpty()||p.isEmpty()){status.setText("Digite usuário e senha.");return;}setBusy(true,"Verificando acesso...");new Thread(()->{try{JSONObject j=new JSONObject();j.put("username",u);j.put("password",p);j.put("device_id",deviceId());int[] code={-1};String body=post(LOGIN_URL,j,code);runOnUiThread(()->{if(code[0]>=200&&code[0]<300){try{String token=new JSONObject(body).optString("token","").trim();if(!token.isEmpty())prefs.edit().putString(PREF_TOKEN,token).commit();}catch(Exception ignored){}setBusy(false,"Acesso liberado.");openTudoLiberado();}else{String msg="Usuário ou senha inválidos.";try{String err=new JSONObject(body).optString("error","");if("blocked".equals(err))msg="Acesso bloqueado no painel.";else if("expired".equals(err))msg="Acesso vencido. Fale com sua revenda.";else if("device_in_use".equals(err))msg="Este usuário já está vinculado a outro aparelho.";}catch(Exception ignored){}setBusy(false,msg);}});}catch(Exception e){runOnUiThread(()->setBusy(false,"Falha de conexão. Verifique a internet."));}}).start();}
    private void setBusy(boolean b,String m){enterButton.setEnabled(!b);userField.setEnabled(!b);passField.setEnabled(!b);progress.setVisibility(b?View.VISIBLE:View.GONE);status.setText(m);}
    private void openTudoLiberado(){Exception last=null;for(String a:MOTOR_ACTIVITIES){try{Intent i=new Intent(Intent.ACTION_MAIN);i.setComponent(new ComponentName(MOTOR_PACKAGE,a));i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);startActivity(i);status.setText("Abrindo TUDO LIBERADO...");finish();return;}catch(Exception e){last=e;}}String d=last==null?"atividade não encontrada":last.getClass().getSimpleName();status.setText("Motor instalado, mas não foi possível abrir ("+d+").");Toast.makeText(this,"Falha ao abrir o componente interno do TUDO LIBERADO.",Toast.LENGTH_LONG).show();}
}
