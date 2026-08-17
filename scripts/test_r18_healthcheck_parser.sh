#!/bin/sh
# Exercise the parser function from the generated R18 healthcheck against the
# multiword values exported by /sys/kernel/debug/spi-nor/*/params.
set -eu

healthcheck=${1:?usage: test_r18_healthcheck_parser.sh PATH-TO-r18-healthcheck}
fixture=$(mktemp)
trap 'rm -f "$fixture"' EXIT

cat >"$fixture" <<'EOF'
name            s25fl128s1
id              01 20 18 4d 01 80
size            16.0 MiB
write size      1
page size       256
EOF

R18_HEALTHCHECK_TEST_ONLY=1
export R18_HEALTHCHECK_TEST_ONLY
. "$healthcheck"
unset R18_HEALTHCHECK_TEST_ONLY
params=$fixture

check_value() {
	label=$1
	expected=$2
	actual=$3
	if [ "$actual" != "$expected" ]; then
		echo "::error::healthcheck parser mismatch for $label: expected '$expected', got '$actual'" >&2
		exit 1
	fi
	echo "[PASS] healthcheck parses $label"
}

check_value 'name' 's25fl128s1' "$(param_value name '')"
check_value 'full JEDEC ID' '01 20 18 4d 01 80' "$(param_value id '')"
check_value 'full size value' '16.0 MiB' "$(param_value size '')"
check_value 'write size' '1' "$(param_value write size)"
check_value 'page size 256' '256' "$(param_value page size)"
