# CSV Explorer

A Streamlit-powered application for uploading, processing, and visualizing CSV data with organization-based filtering, PDF export, and email functionality.

## Features

- **CSV Data Processing**: Upload and process CSV files with automatic schema adaptation
- **Data Persistence**: Store data in PostgreSQL database between sessions
- **User Authentication**: Secure access with username/password login
- **Organization Filtering**: Filter and view data by organization
- **PDF Export**: Generate formatted PDF reports with proper pagination
- **Email Functionality**: Send reports to specified contacts
- **Responsive UI**: Built with Streamlit for a clean, intuitive interface
- **Easy Deployment**: Ready for deployment on Raspberry Pi or cloud environments

## Quick Start

1. Follow the instructions in `INSTALLATION.md` to set up the application on your Raspberry Pi
2. Start the application with `streamlit run app.py`
3. Log in with the default credentials (admin/admin)
4. Upload a CSV file to begin working with your data
5. Use the sidebar options to filter, export, and email reports

## Usage Instructions

### Uploading Data

1. Log in to the application
2. Click the "Upload CSV" button in the sidebar
3. Select your CSV file
4. The data will be processed and stored in the database

### Filtering Data

1. After uploading data, use the "Organization" dropdown in the sidebar
2. Select an organization to filter the data
3. The main view will update to show only records for that organization

### Generating Reports

1. Select the desired organization filter (or "All")
2. Click the "Generate PDF" button
3. The report will be generated and downloaded automatically

### Sending Email Reports

1. Navigate to the "Email Reports" section
2. Enter recipient email address(es)
3. Add a subject and message
4. Click "Send Email" to send the report as a PDF attachment

### User Management

1. Log in with your credentials
2. If you have admin access, you can manage users
3. Use the "Change Password" option to update your password
4. You can also update your email address for self-testing emails

## Security Notes

- Change the default admin password immediately after first login
- Store the `.env` file securely and don't share it
- When using Gmail, use app passwords rather than your main account password
- For production use, consider enabling HTTPS using a reverse proxy

## Troubleshooting

See the "Troubleshooting" section in `INSTALLATION.md` for common issues and solutions.

## License

This application is provided for your personal use.