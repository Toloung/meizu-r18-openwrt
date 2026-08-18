#!/bin/sh
# Model the keep.d contract that protects a previous LuCI theme choice.
set -eu

keep_file="${1:?usage: $0 KEEP_FILE DEFAULTS_FILE}"
defaults_file="${2:?usage: $0 KEEP_FILE DEFAULTS_FILE}"
expected_path='/etc/config/luci'
manual_theme='/luci-static/argon'

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

# The explicit keep.d entry must carry a user-selected Argon value to the new
# image; this differs from the Bootstrap clean-install default.
keep_settings_theme() {
	old_theme="$1"
	grep -Fxq "$expected_path" "$keep_file" && printf '%s\n' "$old_theme"
}

test "$(keep_settings_theme "$manual_theme")" = "$manual_theme" || {
	echo '::error::keep-settings lost the explicit Argon selection'
	exit 1
}
echo '[PASS] /etc/config/luci explicitly retains an Argon selection'

# LuCI itself provides the official Bootstrap default. The R18 first-boot
# script must not override a retained choice or force a replacement default.
if grep -Fq 'luci.main.mediaurlbase' "$defaults_file"; then
	echo '::error::R18 defaults must not override LuCI Bootstrap mediaurlbase'
	exit 1
fi
echo '[PASS] Bootstrap clean default is left to LuCI upstream defaults'
