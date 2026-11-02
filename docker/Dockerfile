# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
# The edge with the nodered and mqtt adapters (Python standard library + paho-mqtt). amd64 and arm64 (a Pi).
#
#   docker build -f docker/Dockerfile -t dhc-edge:latest .
#   docker run --rm --net=host dhc-edge:latest --profile inventory --adapter nodered --token T
FROM python:3.12-slim
RUN pip install --no-cache-dir paho-mqtt==2.1.0
WORKDIR /app
COPY dhc_edge/ dhc_edge/
COPY web/ web/
COPY profiles/ profiles/
COPY docs/architecture/ docs/architecture/
ENTRYPOINT ["python", "-m", "dhc_edge"]
CMD ["--profile", "blank"]
