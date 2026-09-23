# FlowMatch frontend - static HTML/CSS/JS, no build step (docs/DECISIONS.md #2).
# Served by nginx in production instead of the dev-only serve.py.
FROM nginx:1.27-alpine

COPY nginx-main.conf /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY . /usr/share/nginx/html
RUN rm -f /usr/share/nginx/html/nginx.conf \
          /usr/share/nginx/html/nginx-main.conf \
          /usr/share/nginx/html/docker-entrypoint.sh

EXPOSE 8080

# Startup logic is inlined here rather than kept in a separate entrypoint
# script: the script is maintained by pasting through the Azure DevOps web
# editor, which can introduce a BOM/CRLF that breaks the shebang and makes
# the container fail with "exec format error".
#
# mkdir: nginx only creates the final component of its *_temp_path
# directories, so /tmp/nginx must exist first (see nginx-main.conf, which
# moves those paths off the read-only root filesystem).
# envsubst: renders config.js into /tmp, which nginx.conf aliases to
# /config.js, keeping the image environment-agnostic.
CMD ["/bin/sh", "-c", "mkdir -p /tmp/nginx && envsubst '${API_BASE_URL}' < /usr/share/nginx/html/config.js.template > /tmp/config.js && exec nginx -g 'daemon off;'"]
