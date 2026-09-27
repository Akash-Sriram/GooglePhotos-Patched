package app.morphe.extension.shared.updater;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.TypedValue;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import app.morphe.extension.shared.Logger;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.lang.reflect.Method;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;
import java.util.concurrent.atomic.AtomicBoolean;

public class GitHubReleaseChecker {

    private static final String REPO_RELEASES_URL = "https://api.github.com/repos/Akash-Sriram/GooglePhotos-Patched/releases/latest";
    private static boolean hasCheckedThisSession = false;

    public static void checkUpdateOnStartup(final Context context) {
        checkUpdateOnStartup(context, REPO_RELEASES_URL);
    }

    public static void checkUpdateOnStartup(final Context context, final String customUrl) {
        if (hasCheckedThisSession || context == null) {
            return;
        }
        hasCheckedThisSession = true;

        cleanupOldDownloads(context);

        final String targetUrl = (customUrl != null && !customUrl.isEmpty()) ? customUrl : REPO_RELEASES_URL;

        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    URL url = new URL(targetUrl);
                    HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                    conn.setRequestMethod("GET");
                    conn.setRequestProperty("User-Agent", "GooglePhotos-Patched-App");
                    conn.setConnectTimeout(10000);
                    conn.setReadTimeout(10000);

                    if (conn.getResponseCode() != 200) {
                        return;
                    }

                    BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                    StringBuilder sb = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) {
                        sb.append(line);
                    }
                    reader.close();

                    JSONObject releaseJson = new JSONObject(sb.toString());
                    String tagName = releaseJson.optString("tag_name", "");
                    final String latestVersion = tagName.replaceAll("[^0-9.]", "").replaceAll("^\\.|\\.$", "");

                    String currentPackageName = context.getPackageName();
                    boolean isModPackage = currentPackageName != null && currentPackageName.startsWith("app.morphe");
                    String targetFlavor = isModPackage ? "-mod" : "-original";

                    String downloadUrl = null;
                    String assetUpdatedAtStr = null;
                    String matchedAssetName = null;
                    JSONArray assets = releaseJson.optJSONArray("assets");
                    if (assets != null) {
                        // 1. Prioritize matching the exact flavor of the currently installed app
                        for (int i = 0; i < assets.length(); i++) {
                            JSONObject asset = assets.getJSONObject(i);
                            String name = asset.optString("name", "");
                            if (name.endsWith(".apk") && name.toLowerCase().contains(targetFlavor)) {
                                downloadUrl = asset.optString("browser_download_url", null);
                                assetUpdatedAtStr = asset.optString("updated_at", asset.optString("created_at", ""));
                                matchedAssetName = name;
                                break;
                            }
                        }

                        // 2. Backward-compatibility fallback (if release only has single legacy asset)
                        if (downloadUrl == null) {
                            for (int i = 0; i < assets.length(); i++) {
                                JSONObject asset = assets.getJSONObject(i);
                                String name = asset.optString("name", "");
                                if (name.endsWith(".apk")) {
                                    downloadUrl = asset.optString("browser_download_url", null);
                                    assetUpdatedAtStr = asset.optString("updated_at", asset.optString("created_at", ""));
                                    matchedAssetName = name;
                                    break;
                                }
                            }
                        }
                    }

                    if (downloadUrl == null) {
                        return;
                    }

                    PackageInfo pInfo = context.getPackageManager().getPackageInfo(context.getPackageName(), 0);
                    String currentVersion = pInfo.versionName.replaceAll("[^0-9.]", "").replaceAll("^\\.|\\.$", "");

                    long assetUpdatedAtMillis = parseIso8601(assetUpdatedAtStr);
                    if (assetUpdatedAtMillis <= 0) {
                        assetUpdatedAtMillis = parseIso8601(releaseJson.optString("published_at", ""));
                    }

                    boolean isNewerVer = isNewerVersion(latestVersion, currentVersion);
                    boolean isSameVer = !latestVersion.isEmpty() && latestVersion.equals(currentVersion);

                    // Check if remote asset was updated after current installed package was updated
                    // Add 60-second grace threshold to avoid edge-timing on install
                    boolean isNewerBuild = false;
                    if (isSameVer && assetUpdatedAtMillis > 0) {
                        if (assetUpdatedAtMillis > (pInfo.lastUpdateTime + 60000L)) {
                            isNewerBuild = true;
                        }
                    }

                    if (isNewerVer || isNewerBuild) {
                        final String finalDownloadUrl = downloadUrl;
                        final String finalCurrentVersion = currentVersion;
                        final boolean finalIsRebuild = isNewerBuild && !isNewerVer;
                        final long finalAssetTime = assetUpdatedAtMillis;
                        final String finalAssetName = matchedAssetName;
                        new Handler(Looper.getMainLooper()).post(new Runnable() {
                            @Override
                            public void run() {
                                showUpdateDialog(context, latestVersion, finalDownloadUrl, finalCurrentVersion,
                                        finalIsRebuild, finalAssetTime, finalAssetName);
                            }
                        });
                    }
                } catch (Exception e) {
                    Logger.printException(() -> "Error checking for updates from GitHub", e);
                }
            }
        }).start();
    }

    private static long parseIso8601(String isoString) {
        if (isoString == null || isoString.isEmpty()) return 0;
        try {
            SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
            sdf.setTimeZone(TimeZone.getTimeZone("UTC"));
            Date date = sdf.parse(isoString);
            return date != null ? date.getTime() : 0;
        } catch (Exception ignored) {
            try {
                SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US);
                sdf.setTimeZone(TimeZone.getTimeZone("UTC"));
                Date date = sdf.parse(isoString);
                return date != null ? date.getTime() : 0;
            } catch (Exception e) {
                return 0;
            }
        }
    }

    private static boolean isNewerVersion(String latest, String current) {
        if (latest.isEmpty() || current.isEmpty()) return false;
        String[] latestParts = latest.split("\\.");
        String[] currentParts = current.split("\\.");

        int maxLen = Math.max(latestParts.length, currentParts.length);
        for (int i = 0; i < maxLen; i++) {
            long l = i < latestParts.length ? parseSafeLong(latestParts[i]) : 0L;
            long c = i < currentParts.length ? parseSafeLong(currentParts[i]) : 0L;
            if (l > c) return true;
            if (l < c) return false;
        }
        return false;
    }

    private static long parseSafeLong(String str) {
        try {
            return Long.parseLong(str.trim());
        } catch (NumberFormatException e) {
            return 0L;
        }
    }

    private static int getDialogTheme(Context context) {
        try {
            int nightModeFlags = context.getResources().getConfiguration().uiMode & android.content.res.Configuration.UI_MODE_NIGHT_MASK;
            if (nightModeFlags == android.content.res.Configuration.UI_MODE_NIGHT_YES) {
                return android.R.style.Theme_DeviceDefault_Dialog_Alert;
            } else {
                return android.R.style.Theme_DeviceDefault_Light_Dialog_Alert;
            }
        } catch (Exception e) {
            return 0;
        }
    }

    private static void showUpdateDialog(final Context context, final String newVersion, final String downloadUrl,
                                         final String currentVersion, final boolean isRebuild, final long assetTime,
                                         final String assetName) {
        if (!(context instanceof Activity) || ((Activity) context).isFinishing()) {
            return;
        }

        String displayName = (assetName != null && !assetName.isEmpty())
                ? assetName
                : ("GooglePhotos-v" + newVersion + ".apk");

        String message;
        if (isRebuild) {
            message = "An updated build of Google Photos (v" + newVersion + ") is available.\n\n" +
                      "Package: " + displayName + "\n\n" +
                      "Would you like to download and install this latest build?";
        } else {
            message = "A new patched version of Google Photos is available.\n\n" +
                      "Installed version: " + currentVersion + "\n" +
                      "Latest version: " + newVersion + "\n" +
                      "Package: " + displayName + "\n\n" +
                      "Would you like to download and install it?";
        }

        new AlertDialog.Builder(context, getDialogTheme(context))
                .setTitle(isRebuild ? "Build Update Available" : "Update Available")
                .setMessage(message)
                .setPositiveButton("Update", (dialog, which) -> {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        boolean canInstall = false;
                        try {
                            canInstall = context.getPackageManager().canRequestPackageInstalls();
                        } catch (SecurityException se) {
                            Logger.printException(() -> "Missing REQUEST_INSTALL_PACKAGES permission check", se);
                        }
                        if (!canInstall) {
                            new AlertDialog.Builder(context, getDialogTheme(context))
                                    .setTitle("Permission Required")
                                    .setMessage("Google Photos requires permission to install updates.\n\nPlease allow 'Install unknown apps' in the next screen, then tap Update again.")
                                    .setPositiveButton("Settings", (d, w) -> {
                                        try {
                                            Intent settingsIntent = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES);
                                            settingsIntent.setData(Uri.parse("package:" + context.getPackageName()));
                                            settingsIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                                            context.startActivity(settingsIntent);
                                        } catch (Exception ex) {
                                            Intent genericIntent = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES);
                                            genericIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                                            context.startActivity(genericIntent);
                                        }
                                    })
                                    .setNegativeButton("Cancel", null)
                                    .show();
                            return;
                        }
                    }
                    downloadAndInstallApk(context, newVersion, downloadUrl, assetName);
                })
                .setNegativeButton("Later", null)
                .setCancelable(true)
                .show();
    }

    private static void downloadAndInstallApk(final Context context, final String version, final String downloadUrl,
                                              final String assetName) {
        if (!(context instanceof Activity) || ((Activity) context).isFinishing()) {
            return;
        }

        final String apkFileName = (assetName != null && !assetName.isEmpty())
                ? assetName
                : ("GooglePhotos-v" + version + "-patched.apk");

        final float density = context.getResources().getDisplayMetrics().density;
        final int pad20 = (int) (20 * density);
        final int pad10 = (int) (10 * density);
        final int pad6 = (int) (6 * density);

        // Programmatically build informative UI layout
        LinearLayout layout = new LinearLayout(context);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(pad20, pad20, pad20, pad10);

        // 1. Filename header
        TextView fileNameView = new TextView(context);
        fileNameView.setText(apkFileName);
        fileNameView.setTextSize(14);
        fileNameView.setTypeface(null, android.graphics.Typeface.BOLD);
        fileNameView.setSingleLine(true);
        fileNameView.setEllipsize(android.text.TextUtils.TruncateAt.MIDDLE);
        try {
            TypedValue tv = new TypedValue();
            context.getTheme().resolveAttribute(android.R.attr.textColorPrimary, tv, true);
            fileNameView.setTextColor(tv.data);
        } catch (Exception ignored) {}
        layout.addView(fileNameView);

        // 2. Horizontal Progress Bar (1000 steps for 0.1% resolution)
        final ProgressBar progressBar = new ProgressBar(context, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setMax(1000);
        progressBar.setIndeterminate(true);
        LinearLayout.LayoutParams pbLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        pbLp.setMargins(0, pad10, 0, pad10);
        progressBar.setLayoutParams(pbLp);
        layout.addView(progressBar);

        // 3. Progress Info Text (percentage + downloaded / total MB)
        final TextView progressInfoView = new TextView(context);
        progressInfoView.setText("Connecting to server...");
        progressInfoView.setTextSize(13);
        try {
            TypedValue tv = new TypedValue();
            context.getTheme().resolveAttribute(android.R.attr.textColorPrimary, tv, true);
            progressInfoView.setTextColor(tv.data);
        } catch (Exception ignored) {}
        layout.addView(progressInfoView);

        // 4. Transfer Speed & ETA Info Text
        final TextView speedInfoView = new TextView(context);
        speedInfoView.setText("Speed: calculating... • ETA: --");
        speedInfoView.setTextSize(12);
        try {
            TypedValue tv = new TypedValue();
            context.getTheme().resolveAttribute(android.R.attr.textColorSecondary, tv, true);
            speedInfoView.setTextColor(tv.data);
        } catch (Exception ignored) {}
        LinearLayout.LayoutParams speedLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        speedLp.setMargins(0, pad6, 0, 0);
        speedInfoView.setLayoutParams(speedLp);
        layout.addView(speedInfoView);

        final AtomicBoolean isCancelled = new AtomicBoolean(false);
        final Handler mainHandler = new Handler(Looper.getMainLooper());

        final AlertDialog downloadDialog = new AlertDialog.Builder(context, getDialogTheme(context))
                .setTitle("Downloading Update")
                .setView(layout)
                .setCancelable(false)
                .setNegativeButton("Cancel", (dialog, which) -> {
                    isCancelled.set(true);
                })
                .create();

        downloadDialog.show();

        // High-throughput direct in-process downloader
        new Thread(new Runnable() {
            @Override
            public void run() {
                File targetDir = getUpdateDirectory(context);
                File tempFile = new File(targetDir, apkFileName + ".tmp");
                File finalFile = new File(targetDir, apkFileName);

                if (tempFile.exists()) tempFile.delete();
                if (finalFile.exists()) finalFile.delete();

                HttpURLConnection conn = null;
                InputStream in = null;
                FileOutputStream out = null;

                try {
                    // Manually follow HTTP redirects to resolve GitHub -> AWS S3 CDN direct location
                    String currentUrl = downloadUrl;
                    int redirectCount = 0;
                    while (redirectCount < 7) {
                        if (isCancelled.get()) return;
                        URL url = new URL(currentUrl);
                        conn = (HttpURLConnection) url.openConnection();
                        conn.setInstanceFollowRedirects(false);
                        conn.setRequestMethod("GET");
                        conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Android; Mobile) GooglePhotos-Patched-Updater");
                        conn.setRequestProperty("Accept-Encoding", "identity");
                        conn.setRequestProperty("Connection", "keep-alive");
                        conn.setConnectTimeout(15000);
                        conn.setReadTimeout(20000);

                        int responseCode = conn.getResponseCode();
                        if (responseCode == HttpURLConnection.HTTP_MOVED_PERM
                                || responseCode == HttpURLConnection.HTTP_MOVED_TEMP
                                || responseCode == HttpURLConnection.HTTP_SEE_OTHER
                                || responseCode == 307
                                || responseCode == 308) {
                            String location = conn.getHeaderField("Location");
                            conn.disconnect();
                            if (location != null && !location.isEmpty()) {
                                if (location.startsWith("/")) {
                                    URL base = new URL(currentUrl);
                                    currentUrl = new URL(base.getProtocol(), base.getHost(), base.getPort(), location).toString();
                                } else {
                                    currentUrl = location;
                                }
                                redirectCount++;
                                continue;
                            }
                        }
                        break;
                    }

                    if (isCancelled.get()) return;

                    int code = conn.getResponseCode();
                    if (code != HttpURLConnection.HTTP_OK) {
                        throw new IOException("Server returned HTTP " + code);
                    }

                    long totalBytes = -1;
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                        totalBytes = conn.getContentLengthLong();
                    } else {
                        String cl = conn.getHeaderField("Content-Length");
                        if (cl != null && !cl.isEmpty()) {
                            try {
                                totalBytes = Long.parseLong(cl.trim());
                            } catch (Exception ignored) {}
                        }
                        if (totalBytes <= 0) {
                            totalBytes = conn.getContentLength();
                        }
                    }
                    in = new BufferedInputStream(conn.getInputStream(), 131072);
                    out = new FileOutputStream(tempFile);

                    // 128 KB buffer to eliminate syscall overhead and saturate network bandwidth
                    byte[] buffer = new byte[131072];
                    int bytesRead;
                    long downloadedBytes = 0;
                    long lastUiTime = System.currentTimeMillis();
                    long lastDownloadedBytes = 0;
                    double smoothedSpeed = 0.0;

                    while ((bytesRead = in.read(buffer)) != -1) {
                        if (isCancelled.get()) {
                            break;
                        }
                        out.write(buffer, 0, bytesRead);
                        downloadedBytes += bytesRead;

                        long now = System.currentTimeMillis();
                        long elapsed = now - lastUiTime;
                        if (elapsed >= 200) { // Refresh UI every 200ms
                            long deltaBytes = downloadedBytes - lastDownloadedBytes;
                            double instantSpeed = (deltaBytes * 1000.0) / elapsed;
                            smoothedSpeed = (smoothedSpeed == 0.0) ? instantSpeed : (0.6 * instantSpeed + 0.4 * smoothedSpeed);

                            lastUiTime = now;
                            lastDownloadedBytes = downloadedBytes;

                            final long curDownloaded = downloadedBytes;
                            final long curTotal = totalBytes;
                            final double curSpeed = smoothedSpeed;

                            mainHandler.post(() -> {
                                if (isCancelled.get()) return;
                                updateProgressUi(progressBar, progressInfoView, speedInfoView, curDownloaded, curTotal, curSpeed);
                            });
                        }
                    }

                    out.flush();

                    if (isCancelled.get()) {
                        try { if (out != null) out.close(); } catch (Exception ignored) {}
                        try { if (in != null) in.close(); } catch (Exception ignored) {}
                        tempFile.delete();
                        mainHandler.post(() -> {
                            try { downloadDialog.dismiss(); } catch (Exception ignored) {}
                        });
                        return;
                    }

                    if (tempFile.renameTo(finalFile) || copyFile(tempFile, finalFile)) {
                        tempFile.delete();
                    } else {
                        finalFile = tempFile;
                    }

                    final File installedApk = finalFile;
                    mainHandler.post(() -> {
                        progressBar.setIndeterminate(true);
                        progressInfoView.setText("Download complete! Launching package installer...");
                        speedInfoView.setText("Ready to install.");

                        installApk(context, installedApk);

                        mainHandler.postDelayed(() -> {
                            try { downloadDialog.dismiss(); } catch (Exception ignored) {}
                        }, 2500);
                    });

                } catch (final Exception e) {
                    if (!isCancelled.get()) {
                        Logger.printException(() -> "Error downloading update APK", e);
                        mainHandler.post(() -> {
                            try { downloadDialog.dismiss(); } catch (Exception ignored) {}
                            new AlertDialog.Builder(context, getDialogTheme(context))
                                    .setTitle("Download Failed")
                                    .setMessage("Failed to download update:\n" + e.getMessage())
                                    .setPositiveButton("OK", null)
                                    .show();
                        });
                    }
                } finally {
                    try { if (out != null) out.close(); } catch (Exception ignored) {}
                    try { if (in != null) in.close(); } catch (Exception ignored) {}
                    if (conn != null) conn.disconnect();
                    if (isCancelled.get()) {
                        tempFile.delete();
                    }
                }
            }
        }).start();
    }

    private static void updateProgressUi(ProgressBar progressBar, TextView progressInfo, TextView speedInfo,
                                         long downloaded, long total, double speedBytesPerSec) {
        if (total > 0) {
            progressBar.setIndeterminate(false);
            int progressFraction = (int) ((downloaded * 1000L) / total);
            int progressPercent = (int) ((downloaded * 100L) / total);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                progressBar.setProgress(progressFraction, true);
            } else {
                progressBar.setProgress(progressFraction);
            }
            progressInfo.setText(String.format(Locale.US, "%d%% (%.1f MB / %.1f MB)",
                    progressPercent, downloaded / (1024.0 * 1024.0), total / (1024.0 * 1024.0)));

            long remainingBytes = Math.max(0, total - downloaded);
            String etaStr = formatEta(remainingBytes, speedBytesPerSec);
            speedInfo.setText(String.format(Locale.US, "Speed: %s  •  ETA: %s", formatSpeed(speedBytesPerSec), etaStr));
        } else {
            progressBar.setIndeterminate(true);
            progressInfo.setText(String.format(Locale.US, "Downloaded: %.1f MB", downloaded / (1024.0 * 1024.0)));
            speedInfo.setText(String.format(Locale.US, "Speed: %s", formatSpeed(speedBytesPerSec)));
        }
    }

    private static String formatSpeed(double bytesPerSec) {
        if (bytesPerSec <= 0) return "-- MB/s";
        if (bytesPerSec >= 1024.0 * 1024.0) {
            return String.format(Locale.US, "%.1f MB/s", bytesPerSec / (1024.0 * 1024.0));
        } else {
            return String.format(Locale.US, "%.0f KB/s", bytesPerSec / 1024.0);
        }
    }

    private static String formatEta(long remainingBytes, double speedBytesPerSec) {
        if (speedBytesPerSec <= 1024.0 || remainingBytes <= 0) return "--";
        long totalSecs = (long) (remainingBytes / speedBytesPerSec);
        if (totalSecs < 60) {
            return "~" + totalSecs + "s";
        } else {
            long mins = totalSecs / 60;
            long secs = totalSecs % 60;
            return mins + "m " + secs + "s";
        }
    }

    private static boolean copyFile(File src, File dst) {
        try (InputStream in = new FileInputStream(src);
             OutputStream out = new FileOutputStream(dst)) {
            byte[] buf = new byte[65536];
            int len;
            while ((len = in.read(buf)) > 0) {
                out.write(buf, 0, len);
            }
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private static void installApk(Context context, File apkFile) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                boolean canInstall = false;
                try {
                    canInstall = context.getPackageManager().canRequestPackageInstalls();
                } catch (SecurityException se) {
                    Logger.printException(() -> "Missing REQUEST_INSTALL_PACKAGES permission check", se);
                    canInstall = false;
                }
                if (!canInstall) {
                    new AlertDialog.Builder(context, getDialogTheme(context))
                            .setTitle("Permission Required")
                            .setMessage("Google Photos requires permission to install updates.\n\nPlease allow 'Install unknown apps' in the next screen, then tap Update again.")
                            .setPositiveButton("Settings", (dialog, which) -> {
                                try {
                                    Intent settingsIntent = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES);
                                    settingsIntent.setData(Uri.parse("package:" + context.getPackageName()));
                                    settingsIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                                    context.startActivity(settingsIntent);
                                } catch (Exception ex) {
                                    Intent genericIntent = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES);
                                    genericIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                                    context.startActivity(genericIntent);
                                }
                            })
                            .setNegativeButton("Cancel", null)
                            .show();
                    return;
                }
            }

            Uri apkUri = null;
            try {
                Class<?> fpClass = Class.forName("androidx.core.content.FileProvider");
                Method getUriMethod = null;
                try {
                    getUriMethod = fpClass.getMethod("getUriForFile", Context.class, String.class, File.class);
                } catch (NoSuchMethodException e) {
                    // Method was renamed by R8/ProGuard (e.g. 'a(Context, String, File) -> Uri')
                    for (Method m : fpClass.getDeclaredMethods()) {
                        if (java.lang.reflect.Modifier.isStatic(m.getModifiers())
                                && m.getReturnType() == Uri.class
                                && m.getParameterTypes().length == 3
                                && m.getParameterTypes()[0] == Context.class
                                && m.getParameterTypes()[1] == String.class
                                && m.getParameterTypes()[2] == File.class) {
                            getUriMethod = m;
                            getUriMethod.setAccessible(true);
                            break;
                        }
                    }
                }

                if (getUriMethod != null) {
                    apkUri = (Uri) getUriMethod.invoke(null, context, context.getPackageName() + ".fileprovider", apkFile);
                }
            } catch (Exception e) {
                Logger.printException(() -> "Error obtaining FileProvider URI via reflection", e);
            }

            // Fallback: Build content URI matching registered FileProvider cache path in res/SdZ.xml
            if (apkUri == null) {
                apkUri = Uri.parse("content://" + context.getPackageName() + ".fileprovider/stickers/" + Uri.encode(apkFile.getName()));
            }

            Intent installIntent = new Intent(Intent.ACTION_VIEW);
            installIntent.setDataAndType(apkUri, "application/vnd.android.package-archive");
            installIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_GRANT_READ_URI_PERMISSION);

            // Grant URI permission explicitly to package installer activities
            try {
                java.util.List<android.content.pm.ResolveInfo> resolveInfoList =
                        context.getPackageManager().queryIntentActivities(installIntent, PackageManager.MATCH_DEFAULT_ONLY);
                for (android.content.pm.ResolveInfo resolveInfo : resolveInfoList) {
                    String targetPackage = resolveInfo.activityInfo.packageName;
                    context.grantUriPermission(targetPackage, apkUri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
                }
            } catch (Exception ignored) {}

            context.startActivity(installIntent);
        } catch (Exception e) {
            Logger.printException(() -> "Error triggering package installer", e);
            try {
                new AlertDialog.Builder(context, getDialogTheme(context))
                        .setTitle("Installation Failed")
                        .setMessage("Could not start package installer: " + e.getMessage())
                        .setPositiveButton("OK", null)
                        .show();
            } catch (Exception ignored) {}
        }
    }

    private static File getUpdateDirectory(Context context) {
        // 'stickers' subfolder is registered in photos_fileprovider_file_paths (res/SdZ.xml)
        File stickersDir = new File(context.getCacheDir(), "stickers");
        if (!stickersDir.exists()) {
            stickersDir.mkdirs();
        }
        return stickersDir;
    }

    private static void cleanupOldDownloads(Context context) {
        try {
            File dir = new File(context.getCacheDir(), "stickers");
            if (dir.exists() && dir.isDirectory()) {
                File[] files = dir.listFiles();
                if (files != null) {
                    for (File file : files) {
                        if (file.isFile() && file.getName().endsWith(".apk")) {
                            file.delete();
                        }
                    }
                }
            }
        } catch (Exception ignored) {}

        try {
            File downloadDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
            if (downloadDir != null && downloadDir.exists() && downloadDir.isDirectory()) {
                File[] files = downloadDir.listFiles();
                if (files != null) {
                    for (File file : files) {
                        if (file.isFile() && file.getName().startsWith("GooglePhotos-") && file.getName().endsWith(".apk")) {
                            file.delete();
                        }
                    }
                }
            }
        } catch (Exception ignored) {}
    }
}
