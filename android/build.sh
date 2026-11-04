#!/bin/sh
# Builds out/kitchen.apk in a throwaway JDK container.
#   Server address: put it in ./.server (one line, e.g. https://pantry.example.com) or pass PANTRY_URL=...
#   Android SDK:    a directory with build-tools/34.0.0 and platforms/android-23, in $ANDROID_SDK
#                   (default: ../../kiosk-app/.sdk, where this house keeps one).
# The signing key lives in ./.signing (keep it: updates must be signed with the same key; generated on first build).
set -e
cd "$(dirname "$0")"
URL="${PANTRY_URL:-$(cat .server 2>/dev/null || true)}"
[ -n "$URL" ] || { echo "Set the server address: echo https://your.pantry > android/.server (or PANTRY_URL=...)" >&2; exit 1; }
SDKDIR="$(cd "${ANDROID_SDK:-../../kiosk-app/.sdk}" 2>/dev/null && pwd)" || { echo "No Android SDK at \${ANDROID_SDK:-../../kiosk-app/.sdk}" >&2; exit 1; }
mkdir -p out .signing src/res/values && chmod 700 .signing
printf '<?xml version="1.0" encoding="utf-8"?>\n<resources><string name="server">%s</string></resources>\n' "$URL" > src/res/values/server.xml
[ -s .signing/pass ] || (umask 077; head -c 24 /dev/urandom | base64 | tr -d '/+=' > .signing/pass)
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/w -v "$SDKDIR":/sdk:ro -w /w eclipse-temurin:17-jdk sh -ec '
  BT=/sdk/build-tools/34.0.0 JAR=/sdk/platforms/android-23/android.jar
  rm -rf build && mkdir -p build/classes build/dex build/gen
  [ -s .signing/kitchen.jks ] || keytool -genkeypair -keystore .signing/kitchen.jks -alias kitchen -keyalg RSA -keysize 2048 -validity 36500 \
      -dname "CN=Pixel Pantry" -storepass "$(cat .signing/pass)" -keypass "$(cat .signing/pass)" 2>/dev/null
  $BT/aapt2 compile --dir src/res -o build/res.zip
  $BT/aapt2 link -I $JAR --manifest src/AndroidManifest.xml -o build/unsigned.apk build/res.zip --java build/gen
  javac -source 8 -target 8 -bootclasspath $JAR -d build/classes -Xlint:-options $(find src/java build/gen -name "*.java")
  $BT/d8 --min-api 21 --lib $JAR --output build/dex $(find build/classes -name "*.class")
  cp build/unsigned.apk build/app.apk && (cd build/dex && jar uf ../app.apk classes.dex)
  $BT/zipalign -f 4 build/app.apk build/aligned.apk
  $BT/apksigner sign --ks .signing/kitchen.jks --ks-pass file:.signing/pass --out out/kitchen.apk build/aligned.apk
  $BT/apksigner verify out/kitchen.apk && echo BUILD OK
'
grep -oE 'versionName="[^"]+"' src/AndroidManifest.xml | cut -d'"' -f2 > out/version.txt
