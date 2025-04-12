import os
import re
import io
import hashlib
import warnings
from datetime import datetime

# Suppress SQLAlchemy warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Third-party imports
import streamlit as st
import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
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
                    is_admin BOOLEAN DEFAULT FALSE
                )
                """)
                connection.execute(create_table_query)
                connection.commit()
                
                # Add admin user (default password: admin)
                admin_pass = hashlib.sha256("admin".encode()).hexdigest()
                insert_query = text("""
                INSERT INTO users (username, password, is_admin) 
                VALUES ('admin', :password, TRUE)
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
            SELECT id, username, is_admin FROM users 
            WHERE username = :username AND password = :password
            """)
            result = connection.execute(query, {"username": username, "password": hashed_password}).fetchone()
            
            if result:
                return True, result[0], result[1], result[2]
            return False, None, None, None
    except Exception as e:
        st.error(f"Authentication error: {str(e)}")
        return False, None, None, None
    
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
            success, user_id, user_name, is_admin = verify_user(username, password)
            if success:
                st.session_state.authenticated = True
                st.session_state.username = user_name
                st.session_state.is_admin = is_admin
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
    
    # Add a title
    styles = getSampleStyleSheet()
    title_text = f"User Data Report - {org_name} Organization" if org_name != "All" else "User Data Report - All Organizations"
    title = Paragraph(title_text, styles["Heading1"])
    elements.append(title)
    
    # Add timestamp
    timestamp = Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"])
    elements.append(timestamp)
    elements.append(Paragraph("<br/>", styles["Normal"]))  # Add some space
    
    # Prepare data for the table
    cols_to_display = ['Org', 'First name', 'Last name', 'Email', 'Description', 'Accepted site invitation']
    existing_cols = [col for col in cols_to_display if col in data.columns]
    
    # Create table data with header
    table_data = [existing_cols]  # Header row
    
    # Add rows
    for _, row in data.iterrows():
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
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        
        # Add zebra striping for readability
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                style.add('BACKGROUND', (0, i), (-1, i), colors.white)
        
        table.setStyle(style)
        elements.append(table)
    
    # Add record count
    record_count = len(data)
    elements.append(Paragraph(f"<br/>Total Records: {record_count}", styles["Normal"]))
    
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
        
        # Add any missing columns required by our schema
        required_columns = ['first_name', 'last_name', 'email', 'user_role', 
                           'accepted_site_invitation', 'description', 'org']
        
        for col in required_columns:
            if col not in df_to_save.columns:
                df_to_save[col] = None
                
        # Convert DataFrame to records and insert into database
        try:
            df_to_save.to_sql('users_data', engine, if_exists='append', index=False, 
                             method='multi', chunksize=100)
        except Exception as sql_err:
            # If the first method fails, try a more direct approach with explicit SQL
            st.warning(f"Primary SQL insert failed: {sql_err}. Trying alternative method...")
            
            # Create a string of column names
            columns = ", ".join(df_to_save.columns)
            
            # Insert rows one by one
            with engine.connect() as connection:
                for _, row in df_to_save.iterrows():
                    values = []
                    for val in row:
                        if pd.isna(val):
                            values.append('NULL')
                        else:
                            val_str = str(val).replace('"','').replace("'","''")
                            values.append(f"'{val_str}'")
                    values_str = ", ".join(values)
                    
                    insert_query = text(f"INSERT INTO users_data ({columns}) VALUES ({values_str})")
                    connection.execute(insert_query)
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
            # First, get a mapping of lowercase to original case from the database
            df.columns = [col.title().replace('_', ' ') for col in df.columns]
            
            # Ensure 'Org' is properly cased (not 'org')
            if 'Org' not in df.columns and 'org' in df.columns:
                df = df.rename(columns={'org': 'Org'})
            
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
        
        # Add Org column based on the logic from SQL query
        df['Org'] = df.apply(determine_org, axis=1)
        
        # Store the column names for schema validation
        st.session_state.columns = list(df.columns)
        st.session_state.schema_created = True
        
        # Store the processed data in session state
        st.session_state.data = df
        
        # Record upload timestamp
        st.session_state.upload_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
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
    
    # Sort data by Org and Description
    display_df = display_df.sort_values(by=['Org', 'Description'])
    
    # Display record count
    st.write(f"**Showing {record_count} records**")
    
    # Select relevant columns similar to SQL query
    cols_to_display = ['Org', 'First name', 'Last name', 'Email', 'Description', 'Accepted site invitation']
    # Filter to only include columns that actually exist in the data
    existing_cols = [col for col in cols_to_display if col in display_df.columns]
    
    # Display the data
    st.dataframe(display_df[existing_cols])

# Main application logic
if login():
    # User is authenticated, show the main app
    st.title(f"CSV Data Explorer - Welcome {st.session_state.username}")
    
    # Show logout button in sidebar
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
                csv = filtered_data.to_csv(index=False)
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
        
        # Display data statistics
        with st.expander("Data Statistics"):
            st.write("### Organization Distribution")
            org_counts = st.session_state.data['Org'].value_counts().reset_index()
            org_counts.columns = ['Organization', 'Count']
            st.dataframe(org_counts)
            
            # Calculate percentage of accepted invitations
            if 'Accepted site invitation' in st.session_state.data.columns:
                accepted_count = st.session_state.data['Accepted site invitation'].value_counts().get('Yes', 0)
                total_count = len(st.session_state.data)
                acceptance_rate = (accepted_count / total_count) * 100 if total_count > 0 else 0
                st.write(f"### Invitation Acceptance Rate: {acceptance_rate:.2f}%")
    else:
        st.info("Upload a CSV file to begin exploring the data. If you've previously uploaded data, it will be automatically loaded.")
