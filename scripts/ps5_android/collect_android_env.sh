#!/data/data/com.termux/files/usr/bin/bash
# Read-only Android/Termux environment inventory. Does not install or change anything.
set -u

section() { printf '\n=== %s ===\n' "$1"; }
value() {
  local label="$1" result="$2"
  printf '%-24s %s\n' "$label" "${result:-unavailable}"
}

section "Android compatibility lab"
value "timestamp_utc" "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || true)"
value "termux_prefix" "${PREFIX:-}"
value "kernel_arch" "$(uname -m 2>/dev/null || true)"
value "kernel" "$(uname -sr 2>/dev/null || true)"
value "android_model" "$(getprop ro.product.model 2>/dev/null || true)"
value "android_manufacturer" "$(getprop ro.product.manufacturer 2>/dev/null || true)"
value "android_release" "$(getprop ro.build.version.release 2>/dev/null || true)"
value "android_sdk" "$(getprop ro.build.version.sdk 2>/dev/null || true)"
value "primary_abi" "$(getprop ro.product.cpu.abi 2>/dev/null || true)"
value "supported_abis" "$(getprop ro.product.cpu.abilist 2>/dev/null || true)"

section "Memory"
if [ -r /proc/meminfo ]; then
  grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo || true
else
  echo "proc memory information unavailable"
fi

section "Available diagnostic tools (no installation performed)"
for tool in git clang cmake ninja make python python3 pkg-config vulkaninfo termux-info; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '%-24s %s\n' "$tool" "$(command -v "$tool")"
  else
    printf '%-24s %s\n' "$tool" "not found"
  fi
done

section "Graphics-related Android properties"
getprop 2>/dev/null | grep -Ei '\[(ro\.hardware\.egl|ro\.board\.platform|ro\.hardware\.vulkan|ro\.opengl\.version|debug\.hwui\.renderer)\]' || true

section "Notes"
echo "Read-only inventory; no root access required or attempted."
echo "This report does not prove Vulkan feature support or game compatibility."
echo "Review this output for device metadata before publishing it."
