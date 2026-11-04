package io.github.timzilla.pixelpantry;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.ValueCallback;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;
import org.json.JSONTokener;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Pixel Pantry, the phone side ("Kitchen Share"). Share a recipe page to this app and it:
 *  1. loads that page here, in the phone's own browser engine (so sites that block servers still work),
 *  2. grabs the page once it has settled,
 *  3. opens the shelf (the Cloudflare login happens here, once a month) so it holds the login cookie,
 *  4. posts the page to the shelf from Java with that cookie, and shows the clean recipe.
 * Opened from the launcher it is simply the shelf in a window. Problems are reported to the shelf's log.
 */
public class ShareActivity extends Activity {
    static String KITCHEN;   // the Pixel Pantry server, baked in at build time from android/.server (see build.sh)
    static final Pattern URL_RE = Pattern.compile("https?://[^\\s<>\"']+");
    WebView web; TextView status; final Handler h = new Handler();
    String pageUrl, pageHtml; int phase = 0, polls = 0; boolean sending = false;

    String version = "?";

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        KITCHEN = getString(R.string.server).replaceAll("/+$", "");
        try { version = getPackageManager().getPackageInfo(getPackageName(), 0).versionName; } catch (Exception ignored) {}
        LinearLayout root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setBackgroundColor(Color.parseColor("#5a3414"));
        status = new TextView(this); status.setTextColor(Color.parseColor("#f6e5b8")); status.setBackgroundColor(Color.parseColor("#5a3414"));
        status.setPadding(28, 22, 28, 22); status.setTextSize(15); status.setTextIsSelectable(true);
        web = new WebView(this);
        root.addView(status, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(web, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        setContentView(root);
        WebSettings s = web.getSettings(); s.setJavaScriptEnabled(true); s.setDomStorageEnabled(true); s.setLoadWithOverviewMode(true); s.setUseWideViewPort(true);
        CookieManager cm = CookieManager.getInstance(); cm.setAcceptCookie(true); cm.setAcceptThirdPartyCookies(web, true);
        web.setWebViewClient(new WebViewClient() {
            @Override public void onPageFinished(WebView v, String url) {
                if (url == null) return;
                if (phase == 1 && !url.startsWith(KITCHEN)) { polls = 0; settle(); }
                else if (phase == 2 && url.contains("cloudflareaccess.com")) say("Sign in to the kitchen (once a month): your email, then the code.");
                else if (phase == 2 && url.startsWith(KITCHEN) && !sending) { sending = true; send(); }
            }
        });
        handle(getIntent());
    }

    @Override protected void onNewIntent(Intent i) { super.onNewIntent(i); setIntent(i); handle(i); }

    void handle(Intent i) {
        String text = "";
        if (Intent.ACTION_SEND.equals(i.getAction())) {
            String t = i.getStringExtra(Intent.EXTRA_TEXT), sub = i.getStringExtra(Intent.EXTRA_SUBJECT);
            text = (t == null ? "" : t) + " " + (sub == null ? "" : sub);
        }
        if (Intent.ACTION_VIEW.equals(i.getAction()) && i.getData() != null && "kitchen".equals(i.getData().getScheme())) {
            String u = i.getData().getQueryParameter("url"); text = u == null ? "" : u;  // kitchen://add?url=... from the shelf page
        }
        Matcher m = URL_RE.matcher(text);
        if (m.find()) {
            pageUrl = m.group(); pageHtml = null; phase = 1; sending = false;
            say("Kitchen Share " + version + ": fetching the page on the phone…");
            web.loadUrl(pageUrl);
        } else {
            phase = 0; say("Pixel Pantry (app " + version + ")");
            web.loadUrl(KITCHEN + "/");
        }
    }

    static final String PROBE = "(function(){try{var ld=document.querySelectorAll('script[type=\"application/ld+json\"]');return JSON.stringify({t:document.title||'',ld:ld.length,n:(document.body&&document.body.innerText||'').length});}catch(e){return JSON.stringify({err:String(e)});}})()";
    // The page as the shelf needs it: structure intact, minus scripts (except recipe data), styles, images' data, iframes, svg.
    static final String GRAB = "(function(){try{var d=document.documentElement.cloneNode(true);var kill=d.querySelectorAll('script:not([type=\"application/ld+json\"]),style,link,svg,iframe,noscript,video,audio,canvas,template');for(var i=0;i<kill.length;i++){kill[i].parentNode&&kill[i].parentNode.removeChild(kill[i]);}var im=d.querySelectorAll('img,source');for(var j=0;j<im.length;j++){var el=im[j];['srcset','data-srcset','data-lazy-srcset'].forEach(function(a){el.removeAttribute(a);});var sr=el.getAttribute('src')||'';if(sr.indexOf('data:')===0)el.removeAttribute('src');}var h='<!doctype html>'+d.outerHTML;return h.length>6000000?h.slice(0,6000000):h;}catch(e){return 'ERR '+String(e);}})()";

    /** Wait for the page (and any "checking your browser" interstitial) to settle, then grab it. */
    void settle() {
        web.evaluateJavascript(PROBE, new ValueCallback<String>() { @Override public void onReceiveValue(String v) {
            boolean ready; String info = String.valueOf(v);
            try { JSONObject o = new JSONObject((String) new JSONTokener(v).nextValue()); String t = o.optString("t", "").toLowerCase();
                info = "title=" + t + " ld=" + o.optInt("ld") + " text=" + o.optInt("n");
                ready = o.optInt("n") > 800 && !t.contains("just a moment") && !t.contains("attention required") && (o.optInt("ld") > 0 || polls >= 5);
            } catch (Exception e) { ready = polls >= 8; info = "probe: " + e + " / " + info; }
            if (ready || polls >= 20) grab(); else { polls++; say("Waiting for the page… " + polls + "  [" + info + "]"); h.postDelayed(new Runnable() { public void run() { settle(); } }, 1000); }
        } });
    }

    void grab() {
        web.evaluateJavascript(GRAB, new ValueCallback<String>() { @Override public void onReceiveValue(String v) {
            String why;
            try { Object o = new JSONTokener(v).nextValue(); pageHtml = (o instanceof String) ? (String) o : null; why = pageHtml == null ? "page returned " + String.valueOf(v).substring(0, Math.min(80, String.valueOf(v).length())) : ""; }
            catch (Exception e) { pageHtml = null; why = "parse: " + e; }
            if (pageHtml != null && pageHtml.startsWith("ERR ")) { why = pageHtml; pageHtml = null; }
            if (pageHtml == null || pageHtml.length() < 300) { say("Couldn't read that page. " + why + (pageHtml == null ? "" : " (" + pageHtml.length() + " chars)")); return; }
            phase = 2; say("Got " + (pageHtml.length() / 1024) + " KB. Opening the shelf…");
            web.loadUrl(KITCHEN + "/?from=app");  // lands on the login first if the month is up; then send() runs
        } });
    }

    /** POST the page to the shelf from Java, with the WebView's login cookie, then show where it landed. */
    void send() {
        say("Sending to the shelf… (" + (pageHtml.length() / 1024) + " KB)");
        final String cookies = CookieManager.getInstance().getCookie(KITCHEN);
        new Thread(new Runnable() { public void run() {
            try {
                HttpURLConnection c = (HttpURLConnection) new URL(KITCHEN + "/add-html").openConnection();
                c.setInstanceFollowRedirects(false); c.setRequestMethod("POST"); c.setDoOutput(true); c.setConnectTimeout(20000); c.setReadTimeout(90000);
                c.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
                if (cookies != null) c.setRequestProperty("Cookie", cookies);
                byte[] body = ("url=" + URLEncoder.encode(pageUrl, "UTF-8") + "&html=" + URLEncoder.encode(pageHtml, "UTF-8")).getBytes("UTF-8");
                c.setFixedLengthStreamingMode(body.length);
                OutputStream o = c.getOutputStream(); o.write(body); o.close();
                int code = c.getResponseCode(); String loc = c.getHeaderField("Location");
                if ((code == 303 || code == 302) && loc != null) {
                    final String target = loc.startsWith("http") ? loc : KITCHEN + loc;
                    h.post(new Runnable() { public void run() { phase = 3; say(target.contains("err=") ? "The shelf couldn't read that page." : "Saved to the shelf."); web.loadUrl(target); } });
                } else { say("The shelf answered " + code + "."); log("add-html answered " + code + " for " + pageUrl); }
            } catch (Exception e) { say("Couldn't send: " + e); log("send failed for " + pageUrl + ": " + e); }
        } }).start();
    }

    /** Report a problem to the shelf's log so it can be seen from the server side. */
    void log(final String msg) {
        final String cookies = CookieManager.getInstance().getCookie(KITCHEN);
        new Thread(new Runnable() { public void run() {
            try {
                HttpURLConnection c = (HttpURLConnection) new URL(KITCHEN + "/app-log").openConnection();
                c.setRequestMethod("POST"); c.setDoOutput(true); c.setConnectTimeout(10000); c.setReadTimeout(10000);
                c.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
                if (cookies != null) c.setRequestProperty("Cookie", cookies);
                byte[] body = ("msg=" + URLEncoder.encode(msg, "UTF-8")).getBytes("UTF-8");
                OutputStream o = c.getOutputStream(); o.write(body); o.close(); c.getResponseCode();
            } catch (Exception ignored) {}
        } }).start();
    }

    void say(final String s) { h.post(new Runnable() { public void run() { status.setText(s); } }); }

    @Override public void onBackPressed() { if (web.canGoBack()) web.goBack(); else super.onBackPressed(); }
}
