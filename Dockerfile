FROM mcr.microsoft.com/playwright/python:v1.61.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/trace

# HMM and Wan Hai require a headed browser; Xvfb supplies a private display.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends xvfb xauth fonts-noto-cjk ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin trace

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY trace_api_probe ./trace_api_probe
COPY crawler_lab ./crawler_lab

RUN mkdir --parents /var/lib/trace \
    && chown --recursive trace:trace /app /var/lib/trace

USER trace

ENTRYPOINT ["xvfb-run", "--auto-servernum", "--server-args=-screen 0 1280x1024x24", "python", "-m", "trace_api_probe"]
