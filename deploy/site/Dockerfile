# deploy/site/Dockerfile
# THE PUBLISHED SITE: its built output, served by Caddy.
#
# NOTHING IS BUILT HERE. /evidence and /results are computed from .artifacts/,
# which git ignores, so a build on Railway's builder would publish both pages
# empty. The site is built where the evidence lives and `dist` is copied in.
#
# Pinned by the linux/amd64 manifest, declared in toolchain.json and asserted by
# a test, so this file and that one cannot name different images.
FROM caddy:2.11.4-alpine@sha256:040e9f7480b80b6d4a7e5013a21159b950a63dcbdb956e38abe2387fb28d9ec0

COPY Caddyfile /etc/caddy/Caddyfile
COPY dist /srv

CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
