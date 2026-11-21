# An endpoint anyone can run, so that "you can verify it online" does not mean
# "you can verify it on someone else's server".
#
#   docker build -f deploy/Dockerfile -t uibc-verify .
#   docker run -p 8770:8770 uibc-verify
#
# The image is slim because the verifier is standard-library only: no PyNaCl,
# no cryptography, no numpy. If that ever stops being true, this file is where
# it hurts first.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app

# No install step: the endpoint runs from the checkout, and pip would only
# add a wheel round-trip to something that imports nothing external.
RUN useradd --create-home --uid 10001 verify \
 && chown -R verify /app
USER verify

EXPOSE 8770
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8770/health', timeout=4).status==200 else sys.exit(1)"

# Bind 0.0.0.0 inside the container -- that is the container's own loopback,
# not the operator's network. The limit is on by default here, unlike the CLI,
# because anything reachable from outside needs one.
CMD ["python3", "tools/serve_verify.py", "--host", "0.0.0.0", "--port", "8770", "--rate", "60", "--burst", "10"]
