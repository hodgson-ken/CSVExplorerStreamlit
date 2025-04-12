import streamlit as st
import pandas as pd
import re
import io
from datetime import datetime

# Set page title and layout
st.set_page_config(
    page_title="CSV Data Explorer",
    layout="wide"
)

# Initialize session state variables if they don't exist
if 'data' not in st.session_state:
    st.session_state.data = None
if 'schema_created' not in st.session_state:
    st.session_state.schema_created = False
if 'columns' not in st.session_state:
    st.session_state.columns = []
if 'upload_timestamp' not in st.session_state:
    st.session_state.upload_timestamp = None

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

# Main application layout
st.title("CSV Data Explorer")

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
    
    # Download button for filtered data
    if selected_org != "All":
        filtered_data = st.session_state.data[st.session_state.data['Org'] == selected_org]
    else:
        filtered_data = st.session_state.data
    
    # Create a download button for the filtered data
    if not filtered_data.empty:
        csv = filtered_data.to_csv(index=False)
        st.download_button(
            label="Download filtered data as CSV",
            data=csv,
            file_name=f"filtered_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
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
    st.info("Upload a CSV file to begin exploring the data.")
