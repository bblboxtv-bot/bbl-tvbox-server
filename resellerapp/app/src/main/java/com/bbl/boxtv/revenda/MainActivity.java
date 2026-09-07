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
    private static final String LOGIN_URL = "https://bbl-tvbox-manager-v2.onrender.com/base2/api/login";
    private static final String CHECK_URL = "https://bbl-tvbox-manager-v2.onrender.com/base2/api/check";
    private static final String MOTOR_PACKAGE = "com.rtxapps.reuse";
    private static final String PREFS = "tudo_liberado_auth";
    private static final String PREF_TOKEN = "token";
    private static final String[] MOTOR_ACTIVITIES = new String[] {
        "top.niunaijun.blackboxa.view.main.LauncherActivity",
        "top.niunaijun.blackbox.app.LauncherActivity"
    };

    private EditText userField;
    private EditText passField;
    private Button enterButton;
    private ProgressBar progress;
    private TextView status;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        buildUi();
        String savedToken = prefs.getString(PREF_TOKEN, "");
        if (savedToken != null && !savedToken.trim().isEmpty()) {
            checkSavedLogin(savedToken.trim());
        }
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

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setPadding(dp(40), dp(30), dp(40), dp(30));
        root.setBackgroundColor(Color.rgb(5, 12, 22));

        TextView logo = text("TUDO LIBERADO", 32f, Color.WHITE);
        logo.setTypeface(logo.getTypeface(), 1);
        root.addView(logo, new LinearLayout.LayoutParams(-1, -2));

        TextView subtitle = text("ACESSO CONTROLADO", 17f, Color.rgb(93, 188, 255));
        subtitle.setPadding(0, dp(4), 0, dp(26));
        root.addView(subtitle, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(28), dp(24), dp(28), dp(24));
        card.setBackgroundColor(Color.rgb(14, 35, 58));
        root.addView(card, new LinearLayout.LayoutParams(dp(520), -2));

        TextView title = text("Entre com seu usuário e senha", 18f, Color.WHITE);
        title.setGravity(Gravity.START);
        title.setPadding(0, 0, 0, dp(14));
        card.addView(title);

        userField = new EditText(this);
        userField.setHint("Usuário");
        userField.setSingleLine(true);
        userField.setTextColor(Color.WHITE);
        userField.setHintTextColor(Color.rgb(150, 170, 190));
        userField.setBackgroundColor(Color.rgb(7, 24, 42));
        userField.setPadding(dp(16), dp(12), dp(16), dp(12));
        LinearLayout.LayoutParams fp = new LinearLayout.LayoutParams(-1, dp(58));
        fp.setMargins(0, dp(6), 0, dp(10));
        card.addView(userField, fp);

        passField = new EditText(this);
        passField.setHint("Senha");
        passField.setSingleLine(true);
        passField.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        passField.setTextColor(Color.WHITE);
        passField.setHintTextColor(Color.rgb(150, 170, 190));
        passField.setBackgroundColor(Color.rgb(7, 24, 42));
        passField.setPadding(dp(16), dp(12), dp(16), dp(12));
        LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(-1, dp(58));
        pp.setMargins(0, 0, 0, dp(14));
        card.addView(passField, pp);

        enterButton = new Button(this);
        enterButton.setText("ENTRAR");
        enterButton.setTextSize(17f);
        enterButton.setFocusable(true);
        enterButton.setOnClickListener(v -> login());
        card.addView(enterButton, new LinearLayout.LayoutParams(-1, dp(58)));

        progress = new ProgressBar(this);
        progress.setVisibility(View.GONE);
        LinearLayout.LayoutParams prog = new LinearLayout.LayoutParams(dp(42), dp(42));
        prog.gravity = Gravity.CENTER_HORIZONTAL;
        prog.setMargins(0, dp(14), 0, 0);
        card.addView(progress, prog);

        status = text("", 15f, Color.LTGRAY);
        status.setPadding(0, dp(10), 0, 0);
        card.addView(status, new LinearLayout.LayoutParams(-1, -2));

        TextView footer = text("Acesso controlado remotamente pelo painel de revenda.", 14f, Color.rgb(150, 170, 190));
        footer.setPadding(0, dp(24), 0, 0);
        root.addView(footer, new LinearLayout.LayoutParams(-1, -2));

        setContentView(root);
        userField.requestFocus();
    }

    private String deviceId() {
        String id = Settings.Secure.getString(getContentResolver(), Settings.Secure.ANDROID_ID);
        if (id == null || id.trim().isEmpty()) id = android.os.Build.SERIAL;
        if (id == null || id.trim().isEmpty()) id = "unknown-device";
        return id.trim();
    }

    private void checkSavedLogin(final String token) {
        setBusy(true, "Validando acesso salvo...");
        new Thread(() -> {
            int code = -1;
            String body = "";
            try {
                URL url = new URL(CHECK_URL);
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setConnectTimeout(12000);
                conn.setReadTimeout(12000);
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
                conn.setRequestProperty("Accept", "application/json");
                conn.setDoOutput(true);
                JSONObject json = new JSONObject();
                json.put("token", token);
                json.put("device_id", deviceId());
                byte[] out = json.toString().getBytes(StandardCharsets.UTF_8);
                try (OutputStream os = conn.getOutputStream()) { os.write(out); }
                code = conn.getResponseCode();
                InputStream in = code >= 200 && code < 400 ? conn.getInputStream() : conn.getErrorStream();
                if (in != null) {
                    BufferedReader br = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8));
                    StringBuilder sb = new StringBuilder();
                    String line;
                    while ((line = br.readLine()) != null) sb.append(line);
                    body = sb.toString();
                }
                conn.disconnect();
            } catch (Exception e) {
                runOnUiThread(() -> setBusy(false, "Sem conexão. Digite usuário e senha para tentar novamente."));
                return;
            }
            final int finalCode = code;
            final String finalBody = body;
            runOnUiThread(() -> {
                if (finalCode >= 200 && finalCode < 300) {
                    setBusy(false, "Acesso salvo liberado.");
                    openTudoLiberado();
                } else {
                    prefs.edit().remove(PREF_TOKEN).apply();
                    String msg = "Sessão expirada. Entre novamente.";
                    try {
                        String err = new JSONObject(finalBody).optString("error", "");
                        if ("expired".equals(err)) msg = "Acesso vencido. Fale com sua revenda.";
                    } catch (Exception ignored) {}
                    setBusy(false, msg);
                }
            });
        }).start();
    }

    private void login() {
        final String username = userField.getText().toString().trim();
        final String password = passField.getText().toString();
        if (username.isEmpty() || password.isEmpty()) {
            status.setText("Digite usuário e senha.");
            return;
        }
        setBusy(true, "Verificando acesso...");
        new Thread(() -> {
            int code = -1;
            String body = "";
            try {
                URL url = new URL(LOGIN_URL);
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setConnectTimeout(12000);
                conn.setReadTimeout(12000);
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
                conn.setRequestProperty("Accept", "application/json");
                conn.setDoOutput(true);
                JSONObject json = new JSONObject();
                json.put("username", username);
                json.put("password", password);
                json.put("device_id", deviceId());
                byte[] out = json.toString().getBytes(StandardCharsets.UTF_8);
                try (OutputStream os = conn.getOutputStream()) { os.write(out); }
                code = conn.getResponseCode();
                InputStream in = code >= 200 && code < 400 ? conn.getInputStream() : conn.getErrorStream();
                if (in != null) {
                    BufferedReader br = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8));
                    StringBuilder sb = new StringBuilder();
                    String line;
                    while ((line = br.readLine()) != null) sb.append(line);
                    body = sb.toString();
                }
                conn.disconnect();
            } catch (Exception e) {
                runOnUiThread(() -> setBusy(false, "Falha de conexão. Verifique a internet e tente novamente."));
                return;
            }
            final int finalCode = code;
            final String finalBody = body;
            runOnUiThread(() -> {
                if (finalCode >= 200 && finalCode < 300) {
                    try {
                        String token = new JSONObject(finalBody).optString("token", "").trim();
                        if (!token.isEmpty()) prefs.edit().putString(PREF_TOKEN, token).apply();
                    } catch (Exception ignored) {}
                    setBusy(false, "Acesso liberado.");
                    openTudoLiberado();
                } else {
                    String msg = "Usuário ou senha inválidos.";
                    try {
                        String err = new JSONObject(finalBody).optString("error", "");
                        if ("blocked".equals(err)) msg = "Acesso bloqueado no painel.";
                        else if ("expired".equals(err)) msg = "Acesso vencido. Fale com sua revenda.";
                        else if ("device_in_use".equals(err)) msg = "Este usuário já está vinculado a outro aparelho.";
                    } catch (Exception ignored) {}
                    setBusy(false, msg);
                }
            });
        }).start();
    }

    private void setBusy(boolean busy, String message) {
        enterButton.setEnabled(!busy);
        userField.setEnabled(!busy);
        passField.setEnabled(!busy);
        progress.setVisibility(busy ? View.VISIBLE : View.GONE);
        status.setText(message);
    }

    private void openTudoLiberado() {
        Exception last = null;
        for (String activity : MOTOR_ACTIVITIES) {
            try {
                Intent launch = new Intent(Intent.ACTION_MAIN);
                launch.setComponent(new ComponentName(MOTOR_PACKAGE, activity));
                launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
                startActivity(launch);
                status.setText("Abrindo TUDO LIBERADO...");
                return;
            } catch (Exception e) {
                last = e;
            }
        }
        String detail = last == null ? "atividade não encontrada" : last.getClass().getSimpleName();
        status.setText("Motor instalado, mas não foi possível abrir (" + detail + ").");
        Toast.makeText(this, "Falha ao abrir o componente interno do TUDO LIBERADO.", Toast.LENGTH_LONG).show();
    }
}
