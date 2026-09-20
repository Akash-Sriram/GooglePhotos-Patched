package app.morphe.extension.shared.updater;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageInfo;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;

import app.morphe.extension.shared.Logger;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

public class GitHubReleaseChecker {

    private static final String REPO_RELEASES_URL = "https://api.github.com/repos/Akash-Sriram/GooglePhotos-Patched/releases/latest";
    private static final String PREFS_NAME = "google_photos_updater_prefs";
    private static final String KEY_IGNORED_ASSET_TIME = "ignored_asset_time";
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
                    JSONArray assets = releaseJson.optJSONArray("assets");
                    if (assets != null) {
                        // 1. Prioritize matching the exact flavor of the currently installed app
                        for (int i = 0; i < assets.length(); i++) {
                            JSONObject asset = assets.getJSONObject(i);
                            String name = asset.optString("name", "");
                            if (name.endsWith(".apk") && name.toLowerCase().contains(targetFlavor)) {
                                downloadUrl = asset.optString("browser_download_url", null);
                                assetUpdatedAtStr = asset.optString("updated_at", asset.optString("created_at", ""));
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
                        long ignoredTime = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                                .getLong(KEY_IGNORED_ASSET_TIME, 0);
                        if (assetUpdatedAtMillis > (pInfo.lastUpdateTime + 60000L) && assetUpdatedAtMillis > ignoredTime) {
                            isNewerBuild = true;
                        }
                    }

                    if (isNewerVer || isNewerBuild) {
                        final String finalDownloadUrl = downloadUrl;
                        final String finalCurrentVersion = currentVersion;
                        final boolean finalIsRebuild = isNewerBuild && !isNewerVer;
                        final long finalAssetTime = assetUpdatedAtMillis;
                        new Handler(Looper.getMainLooper()).post(new Runnable() {
                            @Override
                            public void run() {
                                showUpdateDialog(context, latestVersion, finalDownloadUrl, finalCurrentVersion, finalIsRebuild, finalAssetTime);
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
                                         final String currentVersion, final boolean isRebuild, final long assetTime) {
        if (!(context instanceof Activity) || ((Activity) context).isFinishing()) {
            return;
        }

        String message;
        if (isRebuild) {
            message = "An updated build of Google Photos (v" + newVersion + ") with fixes/improvements is available.\n\n" +
                      "Would you like to download and install this latest build?";
        } else {
            message = "A new patched version of Google Photos is available.\n\n" +
                      "Installed version: " + currentVersion + "\n" +
                      "Latest version: " + newVersion + "\n\n" +
                      "Would you like to download and install it?";
        }

        new AlertDialog.Builder(context, getDialogTheme(context))
                .setTitle(isRebuild ? "Build Update Available" : "Update Available")
                .setMessage(message)
                .setPositiveButton("Update", (dialog, which) -> downloadAndInstallApk(context, newVersion, downloadUrl))
                .setNegativeButton("Later", (dialog, which) -> {
                    if (isRebuild && assetTime > 0) {
                        try {
                            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                                    .edit()
                                    .putLong(KEY_IGNORED_ASSET_TIME, assetTime)
                                    .apply();
                        } catch (Exception ignored) {}
                    }
                })
                .setCancelable(true)
                .show();
    }

    private static void downloadAndInstallApk(final Context context, final String version, String downloadUrl) {
        if (!(context instanceof Activity) || ((Activity) context).isFinishing()) {
            return;
        }

        try {
            DownloadManager.Request request = new DownloadManager.Request(Uri.parse(downloadUrl));
            request.setTitle("Google Photos Update (v" + version + ")");
            request.setDescription("Downloading updated patched Google Photos build...");
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE);
            request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "GooglePhotos-v" + version + "-patched.apk");

            final DownloadManager manager = (DownloadManager) context.getSystemService(Context.DOWNLOAD_SERVICE);
            if (manager == null) return;

            final long downloadId = manager.enqueue(request);

            // Programmatically build dialog
            final float density = context.getResources().getDisplayMetrics().density;
            android.widget.LinearLayout layout = new android.widget.LinearLayout(context);
            layout.setOrientation(android.widget.LinearLayout.VERTICAL);
            int padding = (int) (20 * density);
            layout.setPadding(padding, padding, padding, padding);

            final android.widget.TextView progressText = new android.widget.TextView(context);
            progressText.setText("Preparing download...");
            progressText.setTextSize(16);
            
            // Set text color to match the theme
            try {
                android.util.TypedValue typedValue = new android.util.TypedValue();
                context.getTheme().resolveAttribute(android.R.attr.textColorPrimary, typedValue, true);
                progressText.setTextColor(typedValue.data);
            } catch (Exception ignored) {}
            
            layout.addView(progressText);

            final android.widget.ProgressBar progressBar = new android.widget.ProgressBar(context, null, android.R.attr.progressBarStyleHorizontal);
            progressBar.setMax(100);
            progressBar.setIndeterminate(true);
            android.widget.LinearLayout.LayoutParams lp = new android.widget.LinearLayout.LayoutParams(
                    android.widget.LinearLayout.LayoutParams.MATCH_PARENT, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT);
            lp.setMargins(0, (int) (10 * density), 0, 0);
            progressBar.setLayoutParams(lp);
            layout.addView(progressBar);

            final AlertDialog downloadDialog = new AlertDialog.Builder(context, getDialogTheme(context))
                    .setTitle("Downloading Update")
                    .setView(layout)
                    .setCancelable(false)
                    .create();

            downloadDialog.show();

            // Background status polling
            final Handler mainHandler = new Handler(Looper.getMainLooper());
            new Thread(new Runnable() {
                @Override
                public void run() {
                    boolean downloading = true;
                    while (downloading) {
                        try {
                            Thread.sleep(250);
                        } catch (InterruptedException e) {
                            break;
                        }

                        DownloadManager.Query q = new DownloadManager.Query();
                        q.setFilterById(downloadId);
                        android.database.Cursor cursor = manager.query(q);
                        if (cursor != null && cursor.moveToFirst()) {
                            int bytesDownloadedCol = cursor.getColumnIndex(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR);
                            int bytesTotalCol = cursor.getColumnIndex(DownloadManager.COLUMN_TOTAL_SIZE_BYTES);
                            int statusCol = cursor.getColumnIndex(DownloadManager.COLUMN_STATUS);

                            if (bytesDownloadedCol != -1 && bytesTotalCol != -1 && statusCol != -1) {
                                final int bytesDownloaded = cursor.getInt(bytesDownloadedCol);
                                final int bytesTotal = cursor.getInt(bytesTotalCol);
                                final int status = cursor.getInt(statusCol);

                                mainHandler.post(new Runnable() {
                                    @Override
                                    public void run() {
                                        if (status == DownloadManager.STATUS_RUNNING) {
                                            progressBar.setIndeterminate(false);
                                            if (bytesTotal > 0) {
                                                int progress = (int) ((bytesDownloaded * 100L) / bytesTotal);
                                                progressBar.setProgress(progress);
                                                progressText.setText("Downloading: " + progress + "% (" 
                                                    + (bytesDownloaded / 1024 / 1024) + "MB / " 
                                                    + (bytesTotal / 1024 / 1024) + "MB)");
                                            } else {
                                                progressBar.setIndeterminate(true);
                                                progressText.setText("Downloading...");
                                            }
                                        }
                                    }
                                });

                                if (status == DownloadManager.STATUS_SUCCESSFUL) {
                                    downloading = false;
                                    mainHandler.post(new Runnable() {
                                        @Override
                                        public void run() {
                                            try {
                                                downloadDialog.dismiss();
                                            } catch (Exception ignored) {}
                                            Uri apkUri = manager.getUriForDownloadedFile(downloadId);
                                            if (apkUri != null) {
                                                installApk(context, apkUri);
                                            }
                                        }
                                    });
                                } else if (status == DownloadManager.STATUS_FAILED) {
                                    downloading = false;
                                    mainHandler.post(new Runnable() {
                                        @Override
                                        public void run() {
                                            try {
                                                downloadDialog.dismiss();
                                            } catch (Exception ignored) {}
                                            new AlertDialog.Builder(context)
                                                    .setTitle("Download Failed")
                                                    .setMessage("Failed to download the update APK. Please try again later.")
                                                    .setPositiveButton("OK", null)
                                                    .show();
                                        }
                                    });
                                }
                            }
                            cursor.close();
                        } else {
                            if (cursor != null) cursor.close();
                        }
                    }
                }
            }).start();

        } catch (Exception e) {
            Logger.printException(() -> "Error downloading update APK", e);
        }
    }

    private static void installApk(Context context, Uri apkUri) {
        try {
            Intent installIntent = new Intent(Intent.ACTION_VIEW);
            installIntent.setDataAndType(apkUri, "application/vnd.android.package-archive");
            installIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_GRANT_READ_URI_PERMISSION);
            context.startActivity(installIntent);
        } catch (Exception e) {
            Logger.printException(() -> "Error triggering package installer", e);
        }
    }

    private static void cleanupOldDownloads(Context context) {
        try {
            java.io.File downloadDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
            if (downloadDir != null && downloadDir.exists() && downloadDir.isDirectory()) {
                java.io.File[] files = downloadDir.listFiles();
                if (files != null) {
                    for (java.io.File file : files) {
                        if (file.isFile() && file.getName().startsWith("GooglePhotos-") && file.getName().endsWith(".apk")) {
                            file.delete();
                        }
                    }
                }
            }
        } catch (Exception e) {
            Logger.printException(() -> "Error cleaning up old download files", e);
        }
    }
}
