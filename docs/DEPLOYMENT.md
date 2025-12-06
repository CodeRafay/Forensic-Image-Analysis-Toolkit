# Deployment Guide - Veritas Forensic Image Analysis Toolkit

This guide covers multiple deployment options for the Veritas application.

---

## Table of Contents

1. [Local Development Setup](#local-development)
2. [Streamlit Cloud Deployment](#streamlit-cloud)
3. [Heroku Deployment](#heroku)
4. [Docker Deployment](#docker)
5. [AWS Deployment](#aws)
6. [Production Considerations](#production)

---

## Local Development

### Requirements

- Python 3.9+
- 2GB RAM minimum
- 5GB disk space

### Setup Steps

```bash
# Clone repository
git clone https://github.com/CodeRafay/Forensic-Image-Analysis-Toolkit.git
cd Forensic-Image-Analysis-Toolkit

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run application
streamlit run app.py
```

The app will be available at `http://localhost:8501`

---

## Streamlit Cloud

### Prerequisites

- GitHub account
- GitHub repository with your code

### Deployment Steps

1. **Push Code to GitHub**

   ```bash
   git add .
   git commit -m "Prepare for deployment"
   git push origin main
   ```

2. **Sign in to Streamlit Cloud**

   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Click "Sign in with GitHub"
   - Authorize Streamlit Cloud

3. **Deploy New App**

   - Click "New app"
   - Select your repository: `CodeRafay/Forensic-Image-Analysis-Toolkit`
   - Branch: `main`
   - Main file: `app.py`
   - Click "Deploy"

4. **Configure Secrets** (if needed)

   - Go to App settings → Secrets
   - Add any API keys or secrets in TOML format

5. **Custom Domain** (optional)
   - Go to App settings → General
   - Add custom domain under "Custom subdomain"

### Streamlit Cloud Limits

- Free tier: 1GB resources per app
- 3 public apps maximum
- Automatic updates from GitHub

---

## Heroku

### Prerequisites

- Heroku account
- Heroku CLI installed

### Setup Files

**Create `Procfile`:**

```
web: streamlit run app.py --server.port $PORT --server.enableCORS false
```

**Create `setup.sh`:**

```bash
mkdir -p ~/.streamlit/
echo "\
[server]\n\
headless = true\n\
port = $PORT\n\
enableCORS = false\n\
\n\
" > ~/.streamlit/config.toml
```

**Update `requirements.txt`** (add):

```
gunicorn==20.1.0
```

### Deployment Steps

```bash
# Login to Heroku
heroku login

# Create new app
heroku create veritas-forensics

# Deploy
git add .
git commit -m "Prepare for Heroku"
git push heroku main

# Open app
heroku open

# View logs
heroku logs --tail
```

### Heroku Configuration

```bash
# Set buildpack
heroku buildpacks:set heroku/python

# Scale dyno
heroku ps:scale web=1

# Set environment variables
heroku config:set STREAMLIT_THEME_BASE=dark
```

---

## Docker

### Dockerfile

Create `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: "3.8"

services:
  veritas:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./temp:/app/temp
    environment:
      - STREAMLIT_THEME_BASE=dark
    restart: unless-stopped
```

### Build and Run

```bash
# Build image
docker build -t veritas-forensics .

# Run container
docker run -p 8501:8501 veritas-forensics

# Or use docker-compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop container
docker-compose down
```

---

## AWS Deployment

### Option 1: EC2 Instance

1. **Launch EC2 Instance**

   - AMI: Ubuntu 22.04
   - Instance type: t2.medium (minimum)
   - Security group: Allow port 8501

2. **SSH into Instance**

   ```bash
   ssh -i your-key.pem ubuntu@ec2-xxx.compute.amazonaws.com
   ```

3. **Setup Application**

   ```bash
   # Update system
   sudo apt update && sudo apt upgrade -y

   # Install Python
   sudo apt install python3.9 python3-pip -y

   # Clone repository
   git clone https://github.com/CodeRafay/Forensic-Image-Analysis-Toolkit.git
   cd Forensic-Image-Analysis-Toolkit

   # Install dependencies
   pip3 install -r requirements.txt

   # Run with nohup
   nohup streamlit run app.py --server.port 8501 &
   ```

4. **Setup Nginx (optional)**

   ```bash
   sudo apt install nginx -y
   ```

   Create `/etc/nginx/sites-available/veritas`:

   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://localhost:8501;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_cache_bypass $http_upgrade;
       }
   }
   ```

   Enable site:

   ```bash
   sudo ln -s /etc/nginx/sites-available/veritas /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

### Option 2: Elastic Beanstalk

1. **Install EB CLI**

   ```bash
   pip install awsebcli
   ```

2. **Initialize EB**

   ```bash
   eb init -p python-3.9 veritas-forensics --region us-east-1
   ```

3. **Create Environment**

   ```bash
   eb create veritas-production
   ```

4. **Deploy Updates**
   ```bash
   eb deploy
   ```

---

## Production Considerations

### Performance Optimization

1. **Image Caching**

   - Cache processed results
   - Use Redis for session storage

2. **Resource Limits**

   - Set max upload size: `maxUploadSize=200` in config.toml
   - Limit concurrent users

3. **Monitoring**
   - Add application monitoring (New Relic, Datadog)
   - Set up error tracking (Sentry)

### Security

1. **HTTPS**

   - Use Let's Encrypt for SSL certificates
   - Configure SSL in Nginx/load balancer

2. **Authentication** (if needed)

   - Add authentication layer
   - Use environment variables for secrets

3. **Rate Limiting**
   - Implement API rate limiting
   - Use Cloudflare for DDoS protection

### Backup & Recovery

1. **Database Backup** (if applicable)

   - Schedule regular backups
   - Test recovery procedures

2. **File Storage**
   - Use S3 or cloud storage for uploads
   - Implement automatic cleanup of temp files

### Scalability

1. **Horizontal Scaling**

   - Use load balancer
   - Deploy multiple instances

2. **Vertical Scaling**
   - Upgrade instance size as needed
   - Monitor resource usage

### Maintenance

1. **Updates**

   ```bash
   # Pull latest code
   git pull origin main

   # Install new dependencies
   pip install -r requirements.txt --upgrade

   # Restart application
   # (method depends on deployment)
   ```

2. **Logs**

   - Rotate logs regularly
   - Archive old logs

3. **Monitoring**
   - Set up uptime monitoring
   - Configure alerts for downtime

---

## Troubleshooting

### Common Issues

**Port Already in Use**

```bash
# Find process using port 8501
netstat -ano | findstr :8501

# Kill process
taskkill /PID <pid> /F
```

**Module Not Found**

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

**Memory Issues**

- Increase instance RAM
- Optimize image processing
- Add pagination for batch operations

**Slow Performance**

- Enable caching
- Optimize algorithms
- Use CDN for static assets

---

## Support

For deployment issues:

- GitHub Issues: https://github.com/CodeRafay/Forensic-Image-Analysis-Toolkit/issues
- Email: [Add your email]

---

## Version History

- **v1.0.0** (2025-12) - Initial release with 11 analysis techniques
- **v0.9.0** (2025-11) - Beta release with core features

---

**Last Updated**: December 2025
