FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    cron \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

COPY start.sh /start.sh
RUN chmod +x /start.sh

COPY run_cron.sh /run_cron.sh
RUN chmod +x /run_cron.sh

CMD ["/start.sh"]