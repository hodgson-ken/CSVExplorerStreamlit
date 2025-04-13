# CSV Explorer - Installation Guide

This document provides instructions for installing and running the CSV Explorer application on a Raspberry Pi.

## Prerequisites

- Raspberry Pi with Raspberry Pi OS (Debian-based)
- Internet connection
- Terminal access (SSH or direct)
- Basic knowledge of command line operations

## Database Options

This application can be set up with two different database configurations:

### Option 1: Connect to Existing Cloud Database (Recommended)
- Uses the existing Neon PostgreSQL database
- Maintains all existing user accounts and data
- No local database setup required
- Requires internet connection to operate

### Option 2: Set Up Local PostgreSQL Database
- Creates a new local database on your Raspberry Pi
- Starts with a fresh database (no existing data)
- Works offline once set up
- Requires more setup steps

Choose the option that best suits your needs and follow the corresponding instructions below.

## Installation Steps

### 1. Update your system

```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Install Python and required system dependencies

```bash
sudo apt install -y python3 python3-pip python3-venv
```

If setting up a local database, also install PostgreSQL:

```bash
sudo apt install -y postgresql postgresql-contrib libpq-dev
```

### 3. Extract the application files

Extract the `CSVExplorer.zip` file to a directory of your choice:

```bash
unzip CSVExplorer.zip -d ~/csvexplorer
cd ~/csvexplorer
```

### 4. Create a Python virtual environment and activate it

```bash
python3 -m venv venv
source venv/bin/activate
```

### 5. Install Python dependencies

```bash
pip install -r raspberry_requirements.txt
```

### 6. Set up the .streamlit directory

```bash
mkdir -p ~/.streamlit
cp streamlit_config.toml ~/.streamlit/config.toml
```

## Option 1: Connect to Existing Cloud Database

### 1. Create .env file with cloud database credentials

Create a `.env` file in the application directory with the following content:

```
DATABASE_URL=postgresql://neondb_owner:npg_Ao5WVuFjp3ca@ep-fragrant-bar-a4exjndk.us-east-1.aws.neon.tech/neondb?sslmode=require
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USERNAME=kenhodgson
EMAIL_PASSWORD=yobz dwnv juzv ozwf
PGHOST=ep-fragrant-bar-a4exjndk.us-east-1.aws.neon.tech
PGPORT=5432
PGDATABASE=neondb
PGUSER=neondb_owner
PGPASSWORD=npg_Ao5WVuFjp3ca
```

This configuration uses:
- The existing cloud database with all user accounts and uploaded data
- Your configured Gmail account for sending emails

### 2. Protect your credentials

```bash
chmod 600 .env
```

## Option 2: Set Up Local PostgreSQL Database

### 1. Start and enable PostgreSQL database service

```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 2. Create a local PostgreSQL database

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

### 3. Configure environment variables for local database

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

### 4. Protect your credentials

```bash
chmod 600 .env
```

## Running the Application

### 1. Load environment variables

```bash
export $(grep -v '^#' .env | xargs)
```

### 2. Run the application

```bash
streamlit run app.py --server.port 5000
```

You can now access the application by opening a web browser and navigating to:
- If accessing from the Raspberry Pi itself: http://localhost:5000
- If accessing from another device on the same network: http://[raspberry-pi-ip-address]:5000

### Default Login

When using a local database (Option 2), the application will create a default admin user on first run:
- Username: admin
- Password: admin

When using the cloud database (Option 1), you'll use your existing credentials:
- Username: admin
- The password you've already set

**Important:** If using Option 2, change the default password immediately after first login for security reasons.

## Setting up as a service (optional)

To run the application as a service that starts automatically when the Raspberry Pi boots:

1. Copy the provided service file and edit it:

```bash
cp csvexplorer.service /tmp/csvexplorer.service
sudo nano /tmp/csvexplorer.service
```

2. Edit the file to replace USERNAME with your actual username (e.g., pi) and adjust paths as needed.

3. Move the edited file to the system directory:

```bash
sudo cp /tmp/csvexplorer.service /etc/systemd/system/csvexplorer.service
```

4. Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable csvexplorer
sudo systemctl start csvexplorer
```

5. Check the service status:

```bash
sudo systemctl status csvexplorer
```

## Database Management

### Existing Users (Cloud Database Option)

The cloud database currently contains:
- One admin user (username: admin) with email kenhodgson@gmail.com
- All CSV data previously uploaded to the application

### Local Database Tables

When using a local database, the application creates two tables:
- `users`: Stores authentication information (id, username, password, is_admin, email)
- `users_data`: Stores the CSV data that you upload to the application

The tables are automatically created on first run of the application.

## Troubleshooting

### Database connection issues
- Cloud database option: Verify internet connectivity and check .env credentials
- Local database option: 
  - Verify PostgreSQL is running: `sudo systemctl status postgresql`
  - Check database credentials in the .env file
  - Ensure the database and user were created correctly
  - Try connecting manually: `psql -U csvuser -d csvexplorer`

### Email sending issues
- For Gmail, ensure you're using an App Password if 2FA is enabled
- Verify email settings in the .env file
- Check the email_log.txt file for detailed error messages
- Test connectivity to mail server: `telnet smtp.gmail.com 587`

### Application won't start
- Check for errors in the terminal output
- Verify all dependencies are installed correctly 
- Run with verbose logging: `streamlit run app.py --server.port 5000 --logger.level=debug`
- Ensure the path to the virtual environment is correct in service file (if using)
- Check system logs: `journalctl -u csvexplorer.service`