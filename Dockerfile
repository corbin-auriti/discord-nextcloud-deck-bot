# Dockerfile
FROM python:slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY deck_bot.py .

# Set environment variables (these will be overridden by docker-compose or docker run)
ENV NEXTCLOUD_URL=""
ENV NEXTCLOUD_USERNAME=""
ENV NEXTCLOUD_PASSWORD=""
ENV DISCORD_WEBHOOK_URL=""
ENV BOARD_ID=""
ENV DISCORD_THREAD_ID=""
ENV CHECK_INTERVAL="60"

# Run the bot
CMD ["python", "deck_bot.py"]

