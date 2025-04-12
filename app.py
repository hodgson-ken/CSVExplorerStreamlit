import os
import re
import io
import hashlib
import warnings
import smtplib
import socket
import tempfile
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Suppress SQLAlchemy warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Third-party imports
import streamlit as st
import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# Set page title and layout
st.set_page_config(
    page_title="CSV Data Explorer",
    layout="wide"
)

# Database connection setup
DATABASE_URL = os.environ.get('DATABASE_URL')
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# Initialize session state variables if they don't exist
if 'data' not in st.session_state:
    st.session_state.data = None
if 'schema_created' not in st.session_state:
    st.session_state.schema_created = False
if 'columns' not in st.session_state:
    st.session_state.columns = []
if 'upload_timestamp' not in st.session_state:
    st.session_state.upload_timestamp = None
if 'db_data_loaded' not in st.session_state:
    st.session_state.db_data_loaded = False
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
    
# Authentication functions
def create_admin_user():
    """Create admin user in database if it doesn't exist"""
    try:
        with engine.connect() as connection:
            # Check if users table exists
            check_query = text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users')")
            result = connection.execute(check_query).fetchone()
            
            if not result[0]:
                # Create users table
                create_table_query = text("""
                CREATE TABLE users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    email TEXT
                )
                """)
                connection.execute(create_table_query)
                connection.commit()
                
                # Add admin user (default password: admin)
                admin_pass = hashlib.sha256("admin".encode()).hexdigest()
                insert_query = text("""
                INSERT INTO users (username, password, is_admin, email) 
                VALUES ('admin', :password, TRUE, 'admin@example.com')
                ON CONFLICT (username) DO NOTHING
                """)
                connection.execute(insert_query, {"password": admin_pass})
                connection.commit()
    except Exception as e:
        st.error(f"Error setting up authentication: {str(e)}")

def verify_user(username, password):
    """Verify user credentials"""
    try:
        with engine.connect() as connection:
            # Hash the password
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            
            # Query the user
            query = text("""
            SELECT id, username, is_admin, email FROM users 
            WHERE username = :username AND password = :password
            """)
            result = connection.execute(query, {"username": username, "password": hashed_password}).fetchone()
            
            if result:
                # Check if email field exists (in case it was just added)
                if len(result) >= 4:
                    return True, result[0], result[1], result[2], result[3]
                else:
                    return True, result[0], result[1], result[2], None
            return False, None, None, None, None
    except Exception as e:
        # If there's a column error, try without email
        if "column \"email\" does not exist" in str(e):
            try:
                with engine.connect() as connection:
                    query = text("""
                    SELECT id, username, is_admin FROM users 
                    WHERE username = :username AND password = :password
                    """)
                    result = connection.execute(query, {"username": username, "password": hashed_password}).fetchone()
                    
                    if result:
                        return True, result[0], result[1], result[2], None
                    return False, None, None, None, None
            except Exception as inner_e:
                st.error(f"Authentication error: {str(inner_e)}")
                return False, None, None, None, None
        else:
            st.error(f"Authentication error: {str(e)}")
            return False, None, None, None, None
    
def change_password(username, current_password, new_password):
    """Change a user's password"""
    try:
        # First, verify the current password
        with engine.connect() as connection:
            # Hash the current password
            hashed_current = hashlib.sha256(current_password.encode()).hexdigest()
            
            # Verify current password
            verify_query = text("""
            SELECT id FROM users 
            WHERE username = :username AND password = :password
            """)
            result = connection.execute(verify_query, {"username": username, "password": hashed_current}).fetchone()
            
            if not result:
                return False, "Current password is incorrect"
            
            # Hash the new password
            hashed_new = hashlib.sha256(new_password.encode()).hexdigest()
            
            # Update the password
            update_query = text("""
            UPDATE users 
            SET password = :password 
            WHERE username = :username
            """)
            connection.execute(update_query, {"username": username, "password": hashed_new})
            connection.commit()
            
            return True, "Password updated successfully"
    except Exception as e:
        return False, f"Error changing password: {str(e)}"
        
def update_user_email(username, email):
    """Update a user's email address"""
    try:
        with engine.connect() as connection:
            # Update the email
            update_query = text("""
            UPDATE users 
            SET email = :email 
            WHERE username = :username
            """)
            connection.execute(update_query, {"username": username, "email": email})
            connection.commit()
            
            return True, "Email updated successfully"
    except Exception as e:
        return False, f"Error updating email: {str(e)}"

def login():
    """Handle user login"""
    if st.session_state.authenticated:
        return True
    
    st.title("CSV Data Explorer - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            success, user_id, user_name, is_admin, user_email = verify_user(username, password)
            if success:
                st.session_state.authenticated = True
                st.session_state.username = user_name
                st.session_state.is_admin = is_admin
                st.session_state.user_id = user_id
                st.session_state.user_email = user_email
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid username or password")
    
    st.markdown("Default credentials: admin/admin")
    
    return False

# Ensure admin user exists
create_admin_user()

# Helper function to determine organization based on rules from SQL query logic
def determine_org(row):
    # Default to blank org if description is empty
    if pd.isna(row.get('Description', '')) or row.get('Description', '') == '':
        return '(blank org)'
    
    # Extract organization prefix (characters before first space)
    description = row.get('Description', '')
    match = re.search(r'^(\S+)', description)
    org_prefix = match.group(1) if match else '(blank org)'
    
    # Apply special cases based on SQL logic
    if row.get('User role', '') == 'Manager' or ('stake' in description.lower()):
        return 'Stake'
    elif row.get('Invited by email', '') in ['jdwheeler@churchofjesuschrist.org', 'ron.saunders@churchofjesuschrist.org'] or row.get('User role', '') == 'Adminstrator':
        return 'FM'
    else:
        return org_prefix

# Function to generate PDF
def generate_pdf(data, org_name="All"):
    buffer = io.BytesIO()
    
    # Create the PDF document
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Helper function to add header to each page
    def add_headers(elements, styles, org_title=None):
        # Add a title
        if org_title:
            title_text = f"User Data Report - {org_title}"
        else:
            title_text = f"User Data Report - {org_name} Organization" if org_name != "All" else "User Data Report - All Organizations"
        
        title = Paragraph(title_text, styles["Heading1"])
        elements.append(title)
        
        # Add timestamp
        timestamp = Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"])
        elements.append(timestamp)
        elements.append(Paragraph("<br/>", styles["Normal"]))  # Add some space
        
        return elements
    
    # Add the headers to the first page
    styles = getSampleStyleSheet()
    elements = add_headers(elements, styles)
    
    # Make a copy and sort by Description
    pdf_data = data.copy()
    pdf_data = pdf_data.sort_values(by=['Description'])
    
    # Rename any variation of 'Accepted site invitation' to 'Has Used'
    for col in pdf_data.columns:
        if 'accepted' in col.lower() and 'invitation' in col.lower():
            pdf_data = pdf_data.rename(columns={col: 'Has Used'})
            break
    
    # Prepare data for the table
    cols_to_display = ['Org', 'First name', 'Last name', 'Email', 'Description', 'Has Used']
    existing_cols = [col for col in cols_to_display if col in pdf_data.columns]
    
    if org_name == "All":
        # Get unique organizations
        orgs = pdf_data['Org'].unique()
        
        # Loop through each organization and create a separate page
        for i, org in enumerate(orgs):
            # Filter data for this organization
            org_data = pdf_data[pdf_data['Org'] == org]
            
            if i > 0:  # Add page break after first organization
                elements.append(PageBreak())
                elements = add_headers(elements, styles, org)
            else:
                # Add organization header for the first organization
                elements.append(Paragraph(f"Organization: {org}", styles["Heading2"]))
            
            # Create table data with header
            table_data = [existing_cols]  # Header row
            
            # Add rows
            for _, row in org_data.iterrows():
                table_row = [str(row[col]) if not pd.isna(row[col]) else "" for col in existing_cols]
                table_data.append(table_row)
            
            # Create the table
            if len(table_data) > 1:  # Only create table if there are rows
                table = Table(table_data)
                
                # Add style
                style = TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),  # Font size for header row
                    ('FONTSIZE', (0, 1), (-1, -1), 7),  # Font size for data rows
                    ('TOPPADDING', (0, 0), (-1, -1), 1),  # Reduced top padding
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 1),  # Reduced bottom padding
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 4),  # Header row needs a bit more padding
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ])
                
                # Add zebra striping for readability
                for i in range(1, len(table_data)):
                    if i % 2 == 0:
                        style.add('BACKGROUND', (0, i), (-1, i), colors.white)
                
                table.setStyle(style)
                elements.append(table)
            
            # Add record count for this organization
            org_record_count = len(org_data)
            elements.append(Paragraph(f"<br/>Records: {org_record_count}", styles["Normal"]))
    else:
        # Single organization case - just create one table
        # Create table data with header
        table_data = [existing_cols]  # Header row
        
        # Add rows
        for _, row in pdf_data.iterrows():
            table_row = [str(row[col]) if not pd.isna(row[col]) else "" for col in existing_cols]
            table_data.append(table_row)
        
        # Create the table
        if len(table_data) > 1:  # Only create table if there are rows
            table = Table(table_data)
            
            # Add style
            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('TOPPADDING', (0, 0), (-1, -1), 1),  # Reduced top padding
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),  # Reduced bottom padding
                ('BOTTOMPADDING', (0, 0), (-1, 0), 4),  # Header row needs a bit more padding
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ])
            
            # Add zebra striping for readability
            for i in range(1, len(table_data)):
                if i % 2 == 0:
                    style.add('BACKGROUND', (0, i), (-1, i), colors.white)
            
            table.setStyle(style)
            elements.append(table)
    
    # Add total record count
    record_count = len(data)
    elements.append(Paragraph(f"<br/>Total Records: {record_count}", styles["Normal"]))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

# Function to send email with PDF attachment
def send_email(recipient_email, subject, body, pdf_buffer, filename):
    """Send email with PDF attachment"""
    # Set up logging to file
    log_file = "email_log.txt"
    with open(log_file, "a") as f:
        f.write(f"\n\n--- Email attempt: {datetime.now()} ---\n")
        f.write(f"To: {recipient_email}\n")
        f.write(f"Subject: {subject}\n")
    
    try:
        # Get email credentials from environment variables
        email_host = os.environ.get('EMAIL_HOST')
        email_port = os.environ.get('EMAIL_PORT')
        email_username = os.environ.get('EMAIL_USERNAME')
        email_password = os.environ.get('EMAIL_PASSWORD')
        
        # Log to file
        with open(log_file, "a") as f:
            f.write(f"Host: {email_host}\n")
            f.write(f"Port: {email_port}\n")
            f.write(f"Username: {email_username}\n")
            f.write(f"Password set: {'Yes' if email_password else 'No'}\n")
        
        # Check if credentials are available
        if not all([email_host, email_port, email_username, email_password]):
            missing = []
            if not email_host: missing.append("EMAIL_HOST")
            if not email_port: missing.append("EMAIL_PORT")
            if not email_username: missing.append("EMAIL_USERNAME")
            if not email_password: missing.append("EMAIL_PASSWORD")
            error_msg = f"Missing email credentials: {', '.join(missing)}"
            with open(log_file, "a") as f:
                f.write(f"ERROR: {error_msg}\n")
            return False, error_msg
        
        # Log connection details (without password)
        print(f"Attempting to connect to email server: {email_host}:{email_port} with username: {email_username}")
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = email_username
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Attach message body
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach PDF
        pdf_buffer.seek(0)
        pdf_attachment = MIMEApplication(pdf_buffer.read())
        pdf_attachment.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        msg.attach(pdf_attachment)
        
        # Send email with more detailed error handling
        try:
            # Create server connection
            with open(log_file, "a") as f:
                f.write(f"Creating SMTP connection to {email_host}:{email_port}...\n")
            server = smtplib.SMTP(email_host, int(email_port), timeout=10)
            server.set_debuglevel(1)  # Enable debug output
            
            # Store debug output
            debug_output = []
            def custom_debugger(smtp, message):
                debug_output.append(message)
                with open(log_file, "a") as f:
                    f.write(f"DEBUG: {message}\n")
            server.debuglevel = 1
            server._print_debug = custom_debugger
            
            # Start TLS
            try:
                with open(log_file, "a") as f:
                    f.write("Starting TLS...\n")
                server.starttls()
            except Exception as tls_error:
                error_msg = f"TLS error: {str(tls_error)}"
                with open(log_file, "a") as f:
                    f.write(f"ERROR: {error_msg}\n")
                return False, error_msg
            
            # Login to server
            try:
                with open(log_file, "a") as f:
                    f.write(f"Logging in as {email_username}...\n")
                server.login(email_username, email_password)
            except smtplib.SMTPAuthenticationError as auth_error:
                error_msg = f"Authentication failed: {str(auth_error)}"
                with open(log_file, "a") as f:
                    f.write(f"ERROR: {error_msg}\n")
                return False, error_msg
            
            # Send message
            try:
                with open(log_file, "a") as f:
                    f.write("Sending message...\n")
                server.send_message(msg)
            except Exception as send_error:
                error_msg = f"Error sending message: {str(send_error)}"
                with open(log_file, "a") as f:
                    f.write(f"ERROR: {error_msg}\n")
                return False, error_msg
            
            # Close connection
            try:
                with open(log_file, "a") as f:
                    f.write("Closing connection...\n")
                server.quit()
            except Exception as quit_error:
                with open(log_file, "a") as f:
                    f.write(f"Warning (non-fatal): Error closing connection: {str(quit_error)}\n")  
                
            with open(log_file, "a") as f:
                f.write("SUCCESS: Email sent successfully.\n")
            return True, "Email sent successfully"
        except smtplib.SMTPConnectError as conn_error:
            error_msg = f"Connection error: {str(conn_error)}"
            with open(log_file, "a") as f:
                f.write(f"ERROR: {error_msg}\n")
            return False, error_msg
        except TimeoutError:
            error_msg = f"Connection timed out while connecting to {email_host}:{email_port}"
            with open(log_file, "a") as f:
                f.write(f"ERROR: {error_msg}\n")
            return False, error_msg
        except socket.gaierror as dns_error:
            error_msg = f"DNS resolution error for {email_host}: {str(dns_error)}"
            with open(log_file, "a") as f:
                f.write(f"ERROR: {error_msg}\n")
            return False, error_msg
        except ConnectionRefusedError:
            error_msg = f"Connection refused by {email_host}:{email_port} - server may be blocking your connection"
            with open(log_file, "a") as f:
                f.write(f"ERROR: {error_msg}\n")
            return False, error_msg
        except Exception as smtp_error:
            error_msg = f"SMTP error: {str(smtp_error)}"
            with open(log_file, "a") as f:
                f.write(f"ERROR: {error_msg}\n")
                f.write(f"Error type: {type(smtp_error).__name__}\n")
                import traceback
                f.write(traceback.format_exc())
            return False, error_msg
            
    except Exception as e:
        error_msg = f"Error preparing email: {str(e)}"
        with open(log_file, "a") as f:
            f.write(f"ERROR: {error_msg}\n")
            import traceback
            f.write(traceback.format_exc())
        return False, error_msg

# Function to generate a PDF report of organization distribution
def generate_org_distribution_pdf(data):
    buffer = io.BytesIO()
    
    # Create the PDF document
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Add a title
    styles = getSampleStyleSheet()
    title_text = "Organization Distribution Report"
    title = Paragraph(title_text, styles["Heading1"])
    elements.append(title)
    
    # Add timestamp
    timestamp = Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"])
    elements.append(timestamp)
    elements.append(Paragraph("<br/>", styles["Normal"]))  # Add some space
    
    # Get organization distribution
    org_counts = data['Org'].value_counts().reset_index()
    org_counts.columns = ['Organization', 'Count']
    org_counts = org_counts.sort_values(by='Count', ascending=False)  # Sort by count
    
    # Calculate total for percentage
    total_users = len(data)
    
    # Add Organization Distribution table
    elements.append(Paragraph("Organization Distribution", styles["Heading2"]))
    elements.append(Paragraph("<br/>", styles["Normal"]))
    
    # Create table data with header
    summary_table_data = [['Organization', 'Count', 'Percentage']]  # Header row
    
    # Add rows
    for _, row in org_counts.iterrows():
        org = row['Organization']
        count = row['Count']
        percentage = (count / total_users) * 100 if total_users > 0 else 0
        
        summary_table_data.append([
            str(org), 
            str(count), 
            f"{percentage:.2f}%"
        ])
    
    # Create the summary table
    if len(summary_table_data) > 1:
        summary_table = Table(summary_table_data)
        
        # Add style
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),  # Reduced top padding
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),  # Reduced bottom padding
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),  # Header row needs a bit more padding
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        
        # Add zebra striping for readability
        for i in range(1, len(summary_table_data)):
            if i % 2 == 0:
                style.add('BACKGROUND', (0, i), (-1, i), colors.white)
        
        summary_table.setStyle(style)
        elements.append(summary_table)
    
    # Add usage statistics if available
    usage_column = None
    for col in data.columns:
        if 'accepted' in col.lower() and 'invitation' in col.lower():
            usage_column = col
            break
    
    if usage_column:
        elements.append(Paragraph("<br/><br/>", styles["Normal"]))
        elements.append(Paragraph("User Activation Statistics", styles["Heading2"]))
        
        usage_counts = data[usage_column].value_counts().reset_index()
        usage_counts.columns = ['Status', 'Count']
        
        # Create table data with header for usage stats
        usage_table_data = [['Status', 'Count', 'Percentage']]  # Header row
        
        # Add rows for usage stats
        for _, row in usage_counts.iterrows():
            status = row['Status'] if not pd.isna(row['Status']) else "Not Specified"
            count = row['Count']
            percentage = (count / total_users) * 100 if total_users > 0 else 0
            
            usage_table_data.append([
                str(status), 
                str(count), 
                f"{percentage:.2f}%"
            ])
        
        # Create the usage table
        if len(usage_table_data) > 1:
            usage_table = Table(usage_table_data)
            
            # Add style
            usage_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgreen),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.darkblue),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),  # Reduced top padding
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),  # Reduced bottom padding
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),  # Header row needs a bit more padding
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ])
            
            # Add zebra striping for readability
            for i in range(1, len(usage_table_data)):
                if i % 2 == 0:
                    usage_style.add('BACKGROUND', (0, i), (-1, i), colors.white)
            
            usage_table.setStyle(usage_style)
            elements.append(usage_table)
    
    # Add summary at the end
    elements.append(Paragraph("<br/>", styles["Normal"]))
    elements.append(Paragraph(f"Total Organizations: {len(org_counts)}", styles["Normal"]))
    elements.append(Paragraph(f"Total Users: {total_users}", styles["Normal"]))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

# Function to save data to database
def save_to_database(data):
    try:
        # Clear existing data from the table
        with engine.connect() as connection:
            connection.execute(text("DELETE FROM users_data"))
            connection.commit()
        
        # Create a copy of the data with lowercase column names to avoid SQL case issues
        df_to_save = data.copy()
        df_to_save.columns = [col.lower().replace(' ', '_') for col in df_to_save.columns]
        
        # Clean data to handle nulls and problematic characters
        for col in df_to_save.columns:
            # Replace empty strings with None
            df_to_save[col] = df_to_save[col].replace('', None)
            
            # Convert all non-null values to strings
            df_to_save[col] = df_to_save[col].apply(lambda x: str(x) if not pd.isna(x) else None)
        
        # Add any missing columns required by our schema
        required_columns = ['first_name', 'last_name', 'email', 'user_role', 
                           'accepted_site_invitation', 'description', 'org']
        
        for col in required_columns:
            if col not in df_to_save.columns:
                df_to_save[col] = None
        
        # Try the simpler method first
        try:
            df_to_save.to_sql('users_data', engine, if_exists='append', index=False, 
                             method='multi', chunksize=50)
            return True
        except Exception as sql_err:
            # If the first method fails, try a more direct approach with explicit SQL
            # Get the column names from the table
            with engine.connect() as connection:
                col_query = text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users_data' AND column_name != 'id' AND column_name != 'upload_date'")
                result = connection.execute(col_query).fetchall()
                db_columns = [row[0] for row in result]
            
            # Filter dataframe to only include columns that exist in the database
            df_cols = [col for col in df_to_save.columns if col in db_columns]
            
            if not df_cols:
                st.error("No matching columns found between DataFrame and database schema")
                return False
            
            # Create a string of column names
            columns = ", ".join(df_cols)
            
            # Insert rows one by one
            with engine.connect() as connection:
                inserted_rows = 0
                
                for idx, row in df_to_save.iterrows():
                    try:
                        values = []
                        for col in df_cols:
                            val = row.get(col)
                            if pd.isna(val) or val is None:
                                values.append('NULL')
                            else:
                                # Double escape single quotes for SQL
                                val_str = str(val).replace("'","''")
                                values.append(f"'{val_str}'")
                        
                        values_str = ", ".join(values)
                        
                        insert_query = text(f"INSERT INTO users_data ({columns}) VALUES ({values_str})")
                        connection.execute(insert_query)
                        inserted_rows += 1
                        
                        # Commit every 50 rows to avoid long transactions
                        if inserted_rows % 50 == 0:
                            connection.commit()
                    
                    except Exception:
                        continue
                
                # Final commit
                connection.commit()
            
            return True
        
    except Exception as e:
        st.error(f"Error saving to database: {str(e)}")
        return False

# Function to load data from database
def load_from_database():
    try:
        # Check if table exists first
        with engine.connect() as connection:
            check_query = text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users_data')")
            result = connection.execute(check_query).fetchone()
            
            if not result[0]:
                # Table doesn't exist yet
                return False
        
        # Query all data from the database
        query = text("SELECT * FROM users_data")
        df = pd.read_sql(query, engine)
        
        if not df.empty:
            # Transform column names back to title case for consistency with CSV upload
            df.columns = [col.title().replace('_', ' ') for col in df.columns]
            
            # Ensure 'Org' is properly cased (not 'org')
            if 'Org' not in df.columns and 'org' in df.columns:
                df = df.rename(columns={'org': 'Org'})
            
            # Consistently rename 'Accepted Site Invitation' to 'Has Used'
            if 'Accepted Site Invitation' in df.columns:
                df = df.rename(columns={'Accepted Site Invitation': 'Has Used'})
            
            st.session_state.data = df
            st.session_state.upload_timestamp = "Loaded from database"
            st.session_state.db_data_loaded = True
            st.session_state.schema_created = True
            return True
        return False
    except Exception as e:
        st.error(f"Error loading from database: {str(e)}")
        return False

# Function to process uploaded CSV
def process_csv(uploaded_file):
    try:        
        # Read CSV into pandas DataFrame
        df = pd.read_csv(uploaded_file)
        
        # Clean column names (remove leading/trailing whitespace)
        df.columns = df.columns.str.strip()
        
        # Check for and handle empty rows/columns
        df = df.replace('', None)
        
        # Add Org column based on the logic from SQL query
        df['Org'] = df.apply(determine_org, axis=1)
        
        # Store the column names for schema validation
        st.session_state.columns = list(df.columns)
        st.session_state.schema_created = True
        
        # Store the processed data in session state
        st.session_state.data = df
        
        # Record upload timestamp
        st.session_state.upload_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create users_data table if it doesn't exist
        with engine.connect() as connection:
            # Check if table exists
            check_query = text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users_data')")
            result = connection.execute(check_query).fetchone()
            
            if not result[0]:
                # Create a schema with dynamic columns based on the CSV
                columns_sql = []
                # Always include these columns
                columns_sql.append("id SERIAL PRIMARY KEY")
                columns_sql.append("upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                
                # Add columns based on DataFrame
                for col in df.columns:
                    col_name = col.lower().replace(' ', '_')
                    columns_sql.append(f"{col_name} TEXT")
                
                # Create the table
                create_table_sql = f"CREATE TABLE users_data ({', '.join(columns_sql)})"
                connection.execute(text(create_table_sql))
                connection.commit()
        
        # Save to database
        save_result = save_to_database(df)
        if save_result:
            st.success("Data saved to database successfully!")
        
        return True
    except Exception as e:
        st.error(f"Error processing CSV file: {str(e)}")
        return False

# Function to display the filtered data
def display_data(data, selected_org):
    # Make a copy to avoid modifying the original DataFrame
    display_df = data.copy()
    
    # Filter data by selected organization if not "All"
    if selected_org != "All":
        display_df = display_df[display_df['Org'] == selected_org]
    
    # Get count of records
    record_count = len(display_df)
    
    # Sort data by Description for consistency with PDF
    display_df = display_df.sort_values(by=['Description'])
    
    # Display record count
    st.write(f"**Showing {record_count} records**")
    
    # Rename any variation of 'Accepted site invitation' to 'Has Used'
    for col in display_df.columns:
        if 'accepted' in col.lower() and 'invitation' in col.lower():
            display_df = display_df.rename(columns={col: 'Has Used'})
            break
    
    # Select relevant columns similar to SQL query
    cols_to_display = ['Org', 'First name', 'Last name', 'Email', 'Description', 'Has Used']
    # Filter to only include columns that actually exist in the data
    existing_cols = [col for col in cols_to_display if col in display_df.columns]
    
    # Display the data
    st.dataframe(display_df[existing_cols])

# Main application logic
if login():
    # User is authenticated, show the main app
    st.title(f"CSV Data Explorer - Welcome {st.session_state.username}")
    
    # Show user profile options in sidebar
    st.sidebar.header("User Profile")
    
    # Password change form in sidebar
    with st.sidebar.expander("Change Password"):
        with st.form("change_password_form"):
            cp_current = st.text_input("Current Password", type="password")
            cp_new = st.text_input("New Password", type="password")
            cp_confirm = st.text_input("Confirm New Password", type="password")
            cp_submit = st.form_submit_button("Change Password")
            
            if cp_submit:
                if cp_new != cp_confirm:
                    st.error("New passwords do not match")
                elif len(cp_new) < 4:
                    st.error("New password must be at least 4 characters long")
                else:
                    success, message = change_password(st.session_state.username, cp_current, cp_new)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
                        
    # Email profile management
    with st.sidebar.expander("Update Email Address"):
        with st.form("update_email_form"):
            current_email = st.session_state.user_email if st.session_state.user_email else ""
            email = st.text_input("Email Address", value=current_email)
            email_submit = st.form_submit_button("Update Email")
            
            if email_submit:
                if not email or "@" not in email:
                    st.error("Please enter a valid email address")
                else:
                    success, message = update_user_email(st.session_state.username, email)
                    if success:
                        # Update session state with new email
                        st.session_state.user_email = email
                        st.success(message)
                    else:
                        st.error(message)
    
    # Logout button
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.rerun()
    
    # Try loading data from database on startup
    if not st.session_state.db_data_loaded and st.session_state.data is None:
        load_from_database()
    
    # File uploader
    with st.expander("Upload CSV File", expanded=True):
        uploaded_file = st.file_uploader("Choose a CSV file", type=['csv'])
        if uploaded_file is not None:
            if st.button("Process CSV"):
                success = process_csv(uploaded_file)
                if success:
                    st.success("CSV file processed successfully!")
    
    # Display upload status
    if st.session_state.upload_timestamp:
        st.sidebar.info(f"Last upload: {st.session_state.upload_timestamp}")
    
    # Display data section
    if st.session_state.data is not None:
        st.header("Data Explorer")
        
        # Get unique organizations for dropdown
        org_options = ["All"] + sorted(st.session_state.data['Org'].unique().tolist())
        
        # Create dropdown for organization selection
        selected_org = st.selectbox("Select Organization:", org_options)
        
        # Display filtered data
        display_data(st.session_state.data, selected_org)
        
        # Add Email test section for administrators
        if st.session_state.is_admin:
            with st.expander("Email Configuration Test"):
                st.write("This section allows administrators to test the email configuration.")
                
                email_host = os.environ.get('EMAIL_HOST', '')
                email_port = os.environ.get('EMAIL_PORT', '')
                email_username = os.environ.get('EMAIL_USERNAME', '')
                email_password_exists = "Yes" if os.environ.get('EMAIL_PASSWORD') else "No"
                
                st.write("### Current Email Configuration:")
                st.write(f"- **SMTP Host:** {email_host}")
                st.write(f"- **SMTP Port:** {email_port}")
                st.write(f"- **Username:** {email_username}")
                st.write(f"- **Password Set:** {email_password_exists}")
                
                with st.form("email_test_form"):
                    test_recipient = st.text_input("Test Email Recipient", 
                                                 value=st.session_state.user_email if st.session_state.user_email else "")
                    send_test = st.form_submit_button("Send Test Email")
                    
                    if send_test:
                        if not test_recipient or "@" not in test_recipient:
                            st.error("Please enter a valid email address")
                        else:
                            # Create a simple test email
                            try:
                                # Create message
                                msg = MIMEMultipart()
                                msg['From'] = email_username
                                msg['To'] = test_recipient
                                msg['Subject'] = "CSV Data Explorer - Email Test"
                                
                                # Attach message body
                                body = "This is a test email from the CSV Data Explorer application."
                                msg.attach(MIMEText(body, 'plain'))
                                
                                # Log connection attempt
                                st.write(f"Attempting to connect to {email_host}:{email_port}...")
                                
                                # Create server connection with explicit timeout
                                st.write("Creating SMTP connection...")
                                server = smtplib.SMTP(email_host, int(email_port), timeout=10)
                                
                                # Start TLS
                                st.write("Starting TLS encryption...")
                                server.starttls()
                                
                                # Login
                                st.write("Authenticating with server...")
                                server.login(email_username, os.environ.get('EMAIL_PASSWORD', ''))
                                
                                # Send message
                                st.write("Sending message...")
                                server.send_message(msg)
                                
                                # Close connection
                                st.write("Closing connection...")
                                server.quit()
                                
                                st.success("Test email sent successfully!")
                            except Exception as e:
                                st.error(f"Error sending test email: {str(e)}")
                                st.write("### Troubleshooting Tips:")
                                st.write("1. Check that your email credentials are correct")
                                st.write("2. Ensure the SMTP port isn't blocked by a firewall")
                                st.write("3. For Gmail, enable 'Less secure app access' or use an App Password")
                                st.write("4. Try a different email provider or port number")
        
        # Create export section with buttons side by side
        col1, col2 = st.columns(2)
        
        # Filter data based on selection
        if selected_org != "All":
            filtered_data = st.session_state.data[st.session_state.data['Org'] == selected_org]
        else:
            filtered_data = st.session_state.data
        
        # Create a download button for the filtered data as CSV
        if not filtered_data.empty:
            with col1:
                # Create a copy for CSV with the same formatting as PDF
                csv_data = filtered_data.copy()
                
                # Sort by Description
                csv_data = csv_data.sort_values(by=['Description'])
                
                # Rename any variation of 'Accepted site invitation' to 'Has Used'
                for col in csv_data.columns:
                    if 'accepted' in col.lower() and 'invitation' in col.lower():
                        csv_data = csv_data.rename(columns={col: 'Has Used'})
                        break
                
                csv = csv_data.to_csv(index=False)
                st.download_button(
                    label="Download as CSV",
                    data=csv,
                    file_name=f"filtered_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            # Create a download button for the filtered data as PDF
            with col2:
                pdf_buffer = generate_pdf(filtered_data, selected_org)
                st.download_button(
                    label="Download as PDF",
                    data=pdf_buffer,
                    file_name=f"user_data_report_{selected_org}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf"
                )
        
        # Email report section
        if not filtered_data.empty and 'Email' in filtered_data.columns and 'Description' in filtered_data.columns:
            st.header("Email Reports")
            
            # Get unique descriptions from the filtered data
            descriptions = filtered_data['Description'].unique().tolist()
            
            # Filter out None values before sorting
            descriptions = [desc for desc in descriptions if desc is not None]
            descriptions.sort()
            
            # Allow user to select multiple descriptions to email
            selected_descriptions = st.multiselect(
                "Select contacts to email (by Description):",
                options=descriptions
            )
            
            # Option to include user's own email in recipients
            include_self = False
            if st.session_state.user_email:
                include_self = st.checkbox("Include my email as recipient", value=False,
                                          help=f"Add your email ({st.session_state.user_email}) to the recipient list")
            elif st.checkbox("Include my email as recipient", value=False, disabled=True):
                st.info("Set your email address in the 'Update Email Address' section in the sidebar to include yourself as a recipient.")
            
            # Extract email addresses for selected descriptions
            if selected_descriptions or include_self:
                # Initialize recipient emails list
                recipient_emails = []
                
                # Add emails from selected descriptions if any
                if selected_descriptions:
                    # Get the rows that match the selected descriptions
                    recipient_data = filtered_data[filtered_data['Description'].isin(selected_descriptions)]
                    
                    # Extract the email addresses
                    description_emails = recipient_data['Email'].tolist()
                    
                    # Filter out null or empty emails
                    description_emails = [email for email in description_emails if email and not pd.isna(email)]
                    recipient_emails.extend(description_emails)
                
                # Add user's own email if selected
                if include_self and st.session_state.user_email:
                    recipient_emails.append(st.session_state.user_email)
                
                if recipient_emails:
                    st.write(f"Found {len(recipient_emails)} email(s) for the selected contact(s).")
                    
                    # Email form
                    with st.form("email_form"):
                        email_subject = st.text_input("Email Subject:", 
                            value=f"User Data Report - {selected_org} Organization")
                        
                        email_body = st.text_area("Email Body:", 
                            value=f"Please find attached the user data report for {selected_org} organization.")
                        
                        send_button = st.form_submit_button("Send Report")
                        
                        if send_button:
                            # Create PDF buffer for each recipient
                            pdf_buffer = generate_pdf(filtered_data, selected_org)
                            
                            # Progress indicator
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            # Send emails
                            success_count = 0
                            error_messages = []
                            
                            for i, email in enumerate(recipient_emails):
                                status_text.text(f"Sending email to {email}...")
                                progress_value = (i / len(recipient_emails))
                                progress_bar.progress(progress_value)
                                
                                # Send email with PDF attachment
                                success, message = send_email(
                                    recipient_email=email,
                                    subject=email_subject,
                                    body=email_body,
                                    pdf_buffer=pdf_buffer,
                                    filename=f"user_data_report_{selected_org}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                                )
                                
                                if success:
                                    success_count += 1
                                else:
                                    error_messages.append(f"Failed to send to {email}: {message}")
                            
                            # Final progress
                            progress_bar.progress(1.0)
                            
                            # Show results
                            if success_count == len(recipient_emails):
                                st.success(f"Successfully sent {success_count} email(s)!")
                            else:
                                st.warning(f"Sent {success_count} of {len(recipient_emails)} email(s).")
                                for error in error_messages:
                                    st.error(error)
                else:
                    st.warning("No valid email addresses found for the selected contacts.")
        
        # Display data statistics
        with st.expander("Data Statistics"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write("### Organization Distribution")
                org_counts = st.session_state.data['Org'].value_counts().reset_index()
                org_counts.columns = ['Organization', 'Count']
                st.dataframe(org_counts)
            
            with col2:
                st.write("### Export")
                # Generate and offer PDF download
                pdf_buffer = generate_org_distribution_pdf(st.session_state.data)
                st.download_button(
                    label="Download Statistics PDF",
                    data=pdf_buffer,
                    file_name=f"organization_statistics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    help="Download a comprehensive PDF report of organization distribution and usage statistics"
                )
            
            # Calculate percentage of accepted invitations
            usage_column = None
            # Find the 'Accepted site invitation' column with any casing/formatting
            for col in st.session_state.data.columns:
                if 'accepted' in col.lower() and 'invitation' in col.lower():
                    usage_column = col
                    break
            
            if usage_column:
                accepted_count = st.session_state.data[usage_column].value_counts().get('Yes', 0)
                total_count = len(st.session_state.data)
                acceptance_rate = (accepted_count / total_count) * 100 if total_count > 0 else 0
                st.write(f"### User Activation Rate: {acceptance_rate:.2f}%")
                
                # Show usage breakdown (Yes/No/None)
                st.write("### Has Used Breakdown")
                usage_counts = st.session_state.data[usage_column].value_counts().reset_index()
                usage_counts.columns = ['Status', 'Count']
                st.dataframe(usage_counts)
    else:
        st.info("Upload a CSV file to begin exploring the data. If you've previously uploaded data, it will be automatically loaded.")
