#!/bin/bash

# CSV Explorer Setup Script
# This script helps set up the CSV Explorer application on a Raspberry Pi

echo "=== CSV Explorer Setup ==="
echo "This script will help you set up the CSV Explorer application."

# Create .streamlit directory and config file
echo "Creating Streamlit configuration..."
mkdir -p .streamlit
cp streamlit_config.toml .streamlit/config.toml

# Set up virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install -r raspberry_requirements.txt

# Set up environment file
echo "Setting up environment file..."
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp env.template .env
    
    # Prompt for database configuration
    read -p "Enter PostgreSQL database username: " db_user
    read -p "Enter PostgreSQL database password: " db_pass
    read -p "Enter PostgreSQL database name: " db_name
    
    # Replace placeholders in .env file
    sed -i "s/csvuser/$db_user/g" .env
    sed -i "s/mypassword/$db_pass/g" .env
    sed -i "s/csvexplorer/$db_name/g" .env
    
    # Prompt for email configuration
    read -p "Enter email username: " email_user
    read -p "Enter email password/app password: " email_pass
    
    # Replace email placeholders
    sed -i "s/your.email@gmail.com/$email_user/g" .env
    sed -i "s/your-app-password/$email_pass/g" .env
    
    echo ".env file created and configured!"
else
    echo ".env file already exists. Skipping configuration."
fi

# Create example service file
echo "Creating example systemd service file..."
cat > csvexplorer.service << EOL
[Unit]
Description=CSV Explorer Streamlit App
After=network.target postgresql.service

[Service]
User=$(whoami)
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/venv/bin"
EnvironmentFile=$(pwd)/.env
ExecStart=$(pwd)/venv/bin/streamlit run app.py --server.port 5000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOL

echo "Example service file created as csvexplorer.service"
echo "To install as a system service, run:"
echo "sudo cp csvexplorer.service /etc/systemd/system/"
echo "sudo systemctl daemon-reload"
echo "sudo systemctl enable csvexplorer"
echo "sudo systemctl start csvexplorer"

echo ""
echo "Setup complete! You can now run the application with:"
echo "source venv/bin/activate"
echo "streamlit run app.py"
echo ""
echo "Default login credentials:"
echo "Username: admin"
echo "Password: admin"
echo ""
echo "IMPORTANT: Change the default password after first login!"