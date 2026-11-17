#!/bin/bash
# Teste de fumaça no emulador Android (usado pelo GitHub Actions): instala o APK, abre o aplicativo e
# espera o resultado do cálculo aparecer na tela. Prova que o Python roda dentro do aparelho.
#   uso: teste_emulador.sh caminho/app-debug.apk pasta_de_saida
set -u
APK="$1"; SAIDA="${2:-.}"; mkdir -p "$SAIDA"
adb install -r "$APK" || exit 1
adb shell am start -W -n br.eng.muroarrimo/.MainActivity || exit 1
achou=0
for i in $(seq 1 40); do
  sleep 5
  adb shell uiautomator dump /sdcard/tela.xml >/dev/null 2>&1
  adb pull /sdcard/tela.xml "$SAIDA/tela.xml" >/dev/null 2>&1
  if grep -q "FS tombamento\|Geometria do muro" "$SAIDA/tela.xml" 2>/dev/null && grep -q 'text="\(NÃO \)\?ATENDE"' "$SAIDA/tela.xml"; then
    achou=1; echo "resultado na tela depois de $((i * 5)) s"; break
  fi
done
adb exec-out screencap -p > "$SAIDA/tela.png"
adb logcat -d -t 400 chromium:V Capacitor:V Capacitor/Console:V '*:S' > "$SAIDA/logcat.txt" 2>/dev/null
adb shell dumpsys webviewupdate 2>/dev/null | grep -i "current webview package" > "$SAIDA/webview.txt"
cat "$SAIDA/webview.txt"
if [ "$achou" != 1 ]; then
  echo "O aplicativo não mostrou o resultado em 200 s. Textos na tela:"
  grep -o 'text="[^"]\+"' "$SAIDA/tela.xml" | head -30
  tail -40 "$SAIDA/logcat.txt"
  exit 1
fi
grep -o 'text="[^"]\+"' "$SAIDA/tela.xml" | head -12
