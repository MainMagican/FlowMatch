#!/bin/sh
# Renders config.js from config.js.template using envsubst, so the frontend
# image stays environment-agnostic (per the 3-YAML approach, environment
# values come from values.yaml -> envVariables, not the image).
#
# Written to /tmp instead of /usr/share/nginx/html: the Helm Blueprint's
# default pod securityContext sets readOnlyRootFilesystem, so the static
# content directory can't be written to at container start. /tmp is backed
# by a writable emptyDir even under that policy. nginx.conf aliases
# /config.js to /tmp/config.js so it's still served from the expected URL.
set -e

: "${API_BASE_URL:=}"
envsubst '${API_BASE_URL}' < /usr/share/nginx/html/config.js.template > /tmp/config.js

exec "$@"
