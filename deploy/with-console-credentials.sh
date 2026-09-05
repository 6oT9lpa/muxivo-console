#!/bin/sh

# Load the Vault Agent credential only for the child process.
set -eu

if [ "$#" -lt 2 ]; then
    printf '%s\n' 'Usage: with-console-credentials.sh CREDENTIAL_FILE COMMAND [ARG...]' >&2
    exit 64
fi

credentials_file=$1
shift

if [ ! -r "$credentials_file" ]; then
    printf '%s\n' 'Console credential file is not readable.' >&2
    exit 78
fi

# The Vault template is shell-escaped with printf %q before it reaches here.
set -a
. "$credentials_file"
set +a

exec "$@"
