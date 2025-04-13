# CSV Explorer - Installation Guide

This document provides instructions for installing and running the CSV Explorer application on a Raspberry Pi.

## Prerequisites

- Raspberry Pi with Raspberry Pi OS (Debian-based)
- Internet connection
- Terminal access (SSH or direct)
- Basic knowledge of command line operations

## Installation Steps

### 1. Update your system

```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Install Python and required system dependencies

```bash
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib libpq-dev
```

### 3. Start and enable PostgreSQL database

```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 4. Setup the PostgreSQL database

```bash
# Switch to postgres user
sudo -u postgres psql

# Create a database user (change 'mypassword' to a secure password)
CREATE USER csvuser WITH PASSWORD 'mypassword';

# Create a database
CREATE DATABASE csvexplorer OWNER csvuser;

# Exit PostgreSQL prompt
\q
```

### 5. Extract the application files

Extract the `CSVExplorer.zip` file to a directory of your choice:

```bash
unzip CSVExplorer.zip -d ~/csvexplorer
cd ~/csvexplorer
```

### 6. Create a Python virtual environment and activate it

```bash
python3 -m venv venv
source venv/bin/activate
```

### 7. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 8. Configure environment variables

Create a `.env` file in the application directory with the following content (modify as needed):

```
DATABASE_URL=postgresql://csvuser:mypassword@localhost/csvexplorer
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USERNAME=your.email@gmail.com
EMAIL_PASSWORD=your-app-password
```

**Important notes for Gmail:**
- For `EMAIL_PASSWORD`, use an App Password if you have 2-factor authentication enabled on your Google account.
- To create an App Password:
  1. Go to your Google Account settings
  2. Select Security
  3. Under "Signing in to Google," select "App passwords" (you may need to enable 2-Step Verification first)
  4. Generate a new app password for "Mail" and "Other (Custom name)"
  5. Use the generated password in your .env file

### 9. Load environment variables

```bash
export $(grep -v '^#' .env | xargs)
```

### 10. Run the application

```bash
streamlit run app.py --server.port 5000
```

You can now access the application by opening a web browser and navigating to:
- If accessing from the Raspberry Pi itself: http://localhost:5000
- If accessing from another device on the same network: http://[raspberry-pi-ip-address]:5000

## Setting up as a service (optional)

To run the application as a service that starts automatically when the Raspberry Pi boots:

1. Create a service file:

```bash
sudo nano /etc/systemd/system/csvexplorer.service
```

2. Add the following content (adjust paths as needed):

```
[Unit]
Description=CSV Explorer Streamlit App
After=network.target postgresql.service

[Service]
User=pi
WorkingDirectory=/home/pi/csvexplorer
Environment="PATH=/home/pi/csvexplorer/venv/bin"
EnvironmentFile=/home/pi/csvexplorer/.env
ExecStart=/home/pi/csvexplorer/venv/bin/streamlit run app.py --server.port 5000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable csvexplorer
sudo systemctl start csvexplorer
```

4. Check the service status:

```bash
sudo systemctl status csvexplorer
```

## Default Login

After installation, you can log in with these default credentials:
- Username: admin
- Password: admin

**Important:** Change the default password immediately after the first login for security reasons.

## Troubleshooting

### Database connection issues
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Check database credentials in the .env file
- Ensure the database and user were created correctly

### Email sending issues
- For Gmail, ensure you're using an App Password if 2FA is enabled
- Verify email settings in the .env file
- Check the email_log.txt file for detailed error messages

### Application won't start
- Check for errors in the terminal output
- Verify all dependencies are installed correctly
- Ensure the path to the virtual environment is correct in service file (if using)
- Check system logs: `journalctl -u csvexplorer.service`