#!/bin/sh
# Renders config.js from config.js.template using envsubst, so the frontend
# image stays environment-agnostic (per the 3-YAML approach, environment
# values come from environments/<env>.yaml -> envVariables, not the image).
set -e

: "${API_BASE_URL:=}"
envsubst '${API_BASE_URL}' < /usr/share/nginx/html/config.js.template > /usr/share/nginx/html/config.js

exec "$@"
