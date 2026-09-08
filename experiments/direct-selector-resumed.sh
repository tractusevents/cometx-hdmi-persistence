#!/bin/sh
# Bounded direct-selector trial with MCU running on D, C, then B.
# Adapted from the recorded 2026-09-08 experiment. Logical routing/USB stay B.
set -eu
[ "$#" = 3 ] && [ "$3" = --execute ] || { printf 'Usage: sh SCRIPT EXPECTED_HOSTNAME source-free|connected-b --execute\n'; exit 2; }
[ "$(hostname)" = "$1" ] || { printf 'Hostname guard failed; no changes.\n'; exit 1; }
case "$2" in source-free) lab=1 ;; connected-b) lab=0 ;; *) printf 'Unknown profile.\n'; exit 2 ;; esac
node=/sys/bus/i2c/devices/3-0058
[ "$(cat /proc/gl-hw-info/model)" = rm4pe ] || exit 1
[ "$(cat "$node/version")" = 1.1 ] || exit 1
read8() { timeout 3 i2ctransfer -f -y 3 w2@0x58 "$1" "$2" r1; }
write8() { timeout 3 i2ctransfer -f -y 3 w3@0x58 "$1" "$2" "$3"; }
phase() { printf '%s_UTC=%s\n' "$1" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"; }
[ "$(read8 0xff 0x3c)" = 0x27 ] && [ "$(read8 0xff 0x3d)" = 0x05 ] || exit 1
[ "$(read8 0xff 0x04)" != 0x5a ] || exit 1
state=$(cat "$node/hdmi_status")
original_channel=1
if [ "$lab" = 1 ]; then
    case "$state" in *': Connected'*) printf 'Guard: lab has a source; no writes.\n'; exit 1 ;; esac
    [ "$(cat "$node/channel")" = 'Current Channel : 2' ] || exit 1
    original_channel=2
else
    [ "$(cat "$node/channel")" = 'Current Channel : 1' ] || { printf 'Guard: B not selected; no writes.\n'; exit 1; }
    case "$state" in *'HDMI_A : Connected'*|*'HDMI_C : Connected'*|*'HDMI_D : Connected'*) printf 'Guard: another source attached; no writes.\n'; exit 1 ;; esac
    case "$state" in *'HDMI_B : Connected [SELECTED]'*) ;; *) printf 'Guard: B is not reporting normal HPD; no writes.\n'; exit 1 ;; esac
fi
phase TRIAL_START
cat "$node/channel"
cat "$node/hdmi_status"
guard=/tmp/cometx-mux-resume-$$
mkdir "$guard"
: > "$guard/saved"
printf '%s\n' "$original_channel" > "$guard/original-channel"
printf '%s\n' "$lab" > "$guard/lab"
cat > "$guard/recover.sh" <<'RECOVERY'
#!/bin/sh
set -eu
dir=$1
[ -f "$dir/armed" ] || exit 0
# Only one recovery owns the register bus. A failed attempt releases the lock
# so the independent watchdog can retry.
mkdir "$dir/recovering" 2>/dev/null || exit 1
trap 'rmdir "$dir/recovering" 2>/dev/null || true' 0
printf 'RESTORE_STARTED_UTC=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
timeout 3 i2ctransfer -f -y 3 w3@0x58 0xff 0x04 0x5a
sleep 1
gate=$(timeout 3 i2ctransfer -f -y 3 w2@0x58 0xff 0xff r1)
if [ "$gate" != 0x00 ]; then
    timeout 3 i2ctransfer -f -y 3 w3@0x58 0xff 0x04 0x00
    printf 'Recovery cannot verify internal access: %s\n' "$gate"
    exit 1
fi
ok=1
# The selector is first, returning physical routing to B before MCU resume.
while read -r hi lo value; do
    timeout 3 i2ctransfer -f -y 3 w3@0x58 "$hi" "$lo" "$value" || ok=0
    actual=$(timeout 3 i2ctransfer -f -y 3 w2@0x58 "$hi" "$lo" r1) || ok=0
    printf '%s%s_restored=%s expected=%s\n' "${hi#0x}" "${lo#0x}" "$actual" "$value"
    [ "$actual" = "$value" ] || ok=0
done < "$dir/saved"
timeout 3 i2ctransfer -f -y 3 w3@0x58 0xff 0x04 0x00
printf 'MCU_RESUMED_UTC=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
if [ "$(cat "$dir/lab")" = 1 ]; then
    cat "$dir/original-channel" > /sys/bus/i2c/devices/3-0058/channel
fi
sleep 2
[ "$ok" = 1 ] || exit 1
[ "$(timeout 3 i2ctransfer -f -y 3 w2@0x58 0xff 0xff r1)" = 0x01 ] || exit 1
[ "$(cat /sys/bus/i2c/devices/3-0058/channel)" = "Current Channel : $(cat "$dir/original-channel")" ] || exit 1
if [ "$(cat "$dir/lab")" = 0 ]; then
    state=$(cat /sys/bus/i2c/devices/3-0058/hdmi_status)
    case "$state" in
        *'HDMI_B : Connected [SELECTED]'*) ;;
        *)
            printf 'RECOVERY_NORMAL_C_TO_B_UTC=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
            printf '2\n' > /sys/bus/i2c/devices/3-0058/channel
            sleep 1
            printf '1\n' > /sys/bus/i2c/devices/3-0058/channel
            sleep 3
            state=$(cat /sys/bus/i2c/devices/3-0058/hdmi_status)
            case "$state" in *'HDMI_B : Connected [SELECTED]'*) ;; *) printf 'B health check failed after recovery.\n'; exit 1 ;; esac
            ;;
    esac
fi
rm -f "$dir/armed"
printf 'RESTORE_COMPLETE_UTC=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
RECOVERY
armed=0
cleanup() { set +e; if [ "$armed" = 1 ]; then sh "$guard/recover.sh" "$guard"; fi; }
trap cleanup 0
trap 'exit 130' INT
trap 'exit 143' HUP TERM
: > "$guard/armed"
nohup sh -c 'sleep 45; sh "$1/recover.sh" "$1"' recovery "$guard" > "$guard/recovery.log" 2>&1 < /dev/null &
armed=1
printf 'Recovery directory: %s\n' "$guard"
if [ "$lab" = 1 ]; then
    printf '1\n' > "$node/channel"
    sleep 2
fi
phase MCU_PAUSE_REQUEST
write8 0xff 0x04 0x5a
sleep 1
[ "$(read8 0xff 0xff)" = 0x00 ] || exit 1
while read -r hi lo; do
    value=$(read8 "$hi" "$lo")
    case "$value" in 0x[0123456789abcdef][0123456789abcdef]) ;; *) exit 1 ;; esac
    printf '%s %s %s\n' "$hi" "$lo" "$value" >> "$guard/saved"
    printf '%s%s_before=%s\n' "${hi#0x}" "${lo#0x}" "$value"
done <<'REGISTERS'
0x00 0x01
0x26 0x74
0x00 0xbb
0x00 0xb2
0x00 0xb5
0x00 0xb6
REGISTERS
original_mux=$(read8 0x00 0x01)
[ "$(((original_mux & 0x70) >> 4))" = 1 ] || { printf 'Guard: internal selector is not B.\n'; exit 1; }
mode=$(read8 0x00 0x00)
printf '0000_mode=%s\n' "$mode"
[ "$((mode & 0xc0))" = 64 ] || { printf 'Guard: unexpected selector mode.\n'; exit 1; }
if [ "$lab" = 1 ]; then
    # No source on the spare: establish B's five mask bits as a synthetic baseline.
    while read -r hi lo value; do
        [ "$hi $lo" != '0x00 0x01' ] || continue
        write8 "$hi" "$lo" "$(printf '0x%02x' "$((value | 2))")"
    done < "$guard/saved"
fi
check_state() {
    state_ok=1
    actual=$(read8 0x00 0x01) || return 1
    printf '0001=%s expected=%s\n' "$actual" "$expected_mux"
    [ "$actual" = "$expected_mux" ] || state_ok=0
    actual_mode=$(read8 0x00 0x00) || return 1
    printf '0000=%s expected=%s\n' "$actual_mode" "$mode"
    [ "$actual_mode" = "$mode" ] || state_ok=0
    gate=$(read8 0xff 0xff) || return 1
    [ "$gate" = 0x00 ] || return 1
    [ "$(cat "$node/channel")" = 'Current Channel : 1' ] || state_ok=0
    while read -r hi lo value; do
        [ "$hi $lo" != '0x00 0x01' ] || continue
        actual=$(read8 "$hi" "$lo") || return 1
        expected=$value
        if [ "$lab" = 1 ]; then expected=$(printf '0x%02x' "$((value | 2))"); fi
        printf '%s%s=%s expected=%s\n' "${hi#0x}" "${lo#0x}" "$actual" "$expected"
        [ "$actual" = "$expected" ] && [ "$((actual & 2))" = 2 ] || state_ok=0
    done < "$guard/saved"
    status_b=$(read8 0x03 0x14) || return 1
    printf '0314=%s\n' "$status_b"
    if [ "$lab" != 1 ]; then [ "$((status_b & 0x22))" = 34 ] || state_ok=0; fi
    [ "$state_ok" = 1 ]
}
expected_mux=$original_mux
check_state
phase BASELINE_B_VERIFIED
for channel in 3 2 1; do
    case "$channel" in 3) label=D ;; 2) label=C ;; 1) label=B ;; esac
    expected_mux=$(printf '0x%02x' "$(((original_mux & 0x8f) | (channel << 4)))")
    phase "SELECT_${label}_REQUEST"
    write8 0x00 0x01 "$expected_mux"
    check_state
    phase "SELECT_${label}_VERIFIED"
    phase "MCU_RESUME_${label}_REQUEST"
    write8 0xff 0x04 0x00
    sleep 1
    [ "$(read8 0xff 0xff)" = 0x01 ] || exit 1
    heartbeat_start=$(read8 0xff 0x04)
    phase "MCU_RUNNING_${label}_VERIFIED"
    sleep 5
    heartbeat_end=$(read8 0xff 0x04)
    printf 'MCU_%s_heartbeat=%s -> %s\n' "$label" "$heartbeat_start" "$heartbeat_end"
    printf 'MCU_%s_ff07=' "$label"; read8 0xff 0x07
    cat "$node/hdmi_status"
    [ "$heartbeat_start" != "$heartbeat_end" ] || exit 1
    phase "HOLD_${label}_COMPLETE"
    phase "MCU_PAUSE_AFTER_${label}_REQUEST"
    write8 0xff 0x04 0x5a
    sleep 1
    [ "$(read8 0xff 0xff)" = 0x00 ] || exit 1
    if check_state; then
        phase "POST_RESUME_${label}_STATE_RETAINED"
    else
        phase "POST_RESUME_${label}_STATE_CHANGED_ABORT"
        printf 'State changed during resumed MCU operation; restoring B immediately.\n'
        exit 2
    fi
done
sh "$guard/recover.sh" "$guard"
armed=0
printf 'ffff_final='; read8 0xff 0xff
heartbeat1=$(read8 0xff 0x04)
sleep 1
heartbeat2=$(read8 0xff 0x04)
printf 'heartbeat_final=%s -> %s\n' "$heartbeat1" "$heartbeat2"
[ "$heartbeat1" != "$heartbeat2" ] || exit 1
cat "$node/channel"
cat "$node/hdmi_status"
phase TRIAL_COMPLETE
