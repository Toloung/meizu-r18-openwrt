#!/bin/sh
# Model the keep.d contract that protects a previous LuCI theme choice.
set -eu

keep_file="${1:?usage: $0 KEEP_FILE DEFAULTS_FILE}"
defaults_file="${2:?usage: $0 KEEP_FILE DEFAULTS_FILE}"
expected_path='/etc/config/luci'
old_rom_default='/luci-static/bootstrap'
clean_default='/luci-static/liquid'

test -f "$keep_file" || {
	echo "::error::R18 LuCI keep list is missing: $keep_file"
	exit 1
}

keep_entries="$(sed '/^[[:space:]]*$/d' "$keep_file")"
test "$keep_entries" = "$expected_path" || {
	echo '::error::R18 LuCI keep list must contain only /etc/config/luci'
	exit 1
}
echo '[PASS] sysupgrade keep list contains /etc/config/luci'

# A file equal to the old ROM default is normally omitted by changed-conffile
# discovery. The explicit keep.d entry must still carry it to the new image.
keep_settings_theme() {
	old_theme="$1"
	grep -Fxq "$expected_path" "$keep_file" && printf '%s\n' "$old_theme"
}

test "$(keep_settings_theme "$old_rom_default")" = "$old_rom_default" || {
	echo '::error::keep-settings lost the old ROM-default Bootstrap selection'
	exit 1
}
echo '[PASS] /etc/config/luci explicitly retained by keep-settings'

# A clean sysupgrade has no retained config, so the existing conditional UCI
# default must be the sole source of the new Liquid selection.
grep -Fq 'if [ -z "$(uci -q get luci.main.mediaurlbase)" ]; then' "$defaults_file" || {
	echo '::error::Liquid clean default is no longer conditional'
	exit 1
}
grep -Fq "uci set luci.main.mediaurlbase='$clean_default'" "$defaults_file" || {
	echo '::error::Liquid clean default is missing'
	exit 1
}
echo '[PASS] clean default remains Liquid'
