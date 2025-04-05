# Use Alpine Linux as the base image
FROM alpine:latest

# Install necessary packages
RUN apk update && \
    apk add --no-cache \
        gitea \
        rclone \
        busybox \
        su-exec

# Create a user and group named 'git'
RUN addgroup git && \
    adduser -D -H git -G git

# Set the working directory to /app
WORKDIR /app

# Copy the Gitea configuration file (if you have one)
# COPY gitea.conf /etc/gitea/app.ini
COPY backup.sh /app

# Expose the necessary ports for Gitea
EXPOSE 3000 2222

# Run Gitea as the 'git' user
# CMD ["su-exec", "git", "gitea", "web", "--config", "/etc/gitea/app.ini"]
CMD ["su-exec", "git", "/bin/busybox", "ash", "/app/backup.sh"]

