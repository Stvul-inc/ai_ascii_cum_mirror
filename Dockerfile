FROM python:3.11-slim

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-tk \
    tcl \
    tk \
    libgl1 \
    libglib2.0-0 \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 6080 5900

CMD ["bash", "-c", "rm -f /tmp/.X99-lock /tmp/.X11-unix/X99 && Xvfb :99 -screen 0 1024x768x24 & sleep 2 && x11vnc -display :99 -forever -nopw -shared -rfbport 5900 & websockify --web /usr/share/novnc 6080 localhost:5900 & python 7.py"]
