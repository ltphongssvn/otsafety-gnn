# docker/render.Dockerfile
# THE ONE ENVIRONMENT THAT RENDERS THE SHEET, on every machine.
#
# Pinned by the linux/amd64 manifest digest rather than the multi-platform index:
# an index resolves to arm64 on an Apple laptop and amd64 on a GitHub runner, so
# pinning it would leave two different browsers behind one identifier. Both
# machines now run the same bytes, which is the whole point.
#
# The image already carries Chromium and its system libraries at the version
# matching the pinned playwright, so nothing is installed here and there is no
# apt layer to drift. Everything else the render needs -- the fonts, the
# generator -- is in the repository and mounted at run time.
#
# The digest is declared in toolchain.json and asserted by a test, so this file
# and that one cannot name different images.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble@sha256:96b39581c89131729a7ecb8d532314af54c7f9bcc7a61fe15c7a9e77602acf59

# THE BASE IMAGE CARRIES THE BROWSERS, NOT THE LIBRARY. It ships Chromium and
# every system dependency at the version matching this tag, which is the part
# that cannot be installed reliably; the python packages are ours to add.
# Running the base image directly failed on `No module named playwright`.
#
# Versions match uv.lock, so the container and the laptop run the same code.
# Ubuntu 24.04 refuses pip outside a venv, hence --break-system-packages.
RUN pip install --no-cache-dir --break-system-packages \
      "playwright==1.63.0" \
      "pypdf>=5,<7"

WORKDIR /repo
