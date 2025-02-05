import streamlit as st
import json
import os
import csv
import re
import psycopg2
from psycopg2 import sql
from swarm import Swarm, Agent
import time 
import random
import logging
 
#synonym map
synonym_map = {
    "investor_id": ["Investor ID", "id", "ID", "investor id", "investorId"],
    "full_name": ["Full Name", "name", "Name", "full name", "fullName"],
    "mobile_number": ["Work Phone", "phone number", "mobile number", "contact number", "phone", "contact", "mobile", "mobileNumber"],
    "email_id": ["Email", "Email ID", "email id", "email address", "Email Address", "email", "emailId"],
    "address": ["Address", "address", "Addresss", "personal address", "Personal Address"],
    "date_of_birth": ["Date of Birth", "date of birth", "dob", "DOB", "birthdate", "Birthdate", "dateofbirth", "DateOfBirth"],
    "company_name": ["Company Name", "company", "Company", "employer", "Employer", "companyName"],
    "designation": ["Designation", "designation", "Position", "position", "job title", "Job Title", "designation"],
    "employment_duration": ["Employment Duration", "duration", "Duration", "employment period", "Employment Period", "employment time", "Employment Time", "employmentDuration","employment tenure", "Employment Tenure"],
    "work_email_address": ["Work Email", "work email", "work email address", "Work Email Address", "work email id", "Work Email Id", "workEmailAddress"],
    "work_phone_number": ["Work Phone Number", "work phone", "work phone number", "Work Phone Number", "work contact", "Work Contact", "work phone no", "Work Phone No", "workPhoneNumber"],
    "previous_company_details": ["previous_company", "Previous Company", "old employer details", "Old Employer Details", "old company", "Old Company", "past company", "Past Company", "previousEmployment"],
    "current_company_details": ["current_company", "Current Company", "new employer details", "New Employer Details", "new company", "New Company", "present company", "Present Company", "currentEmployer"],
    "previous_company_address": ["previous company address", "Previous Company Address", "old employer address", "Old Employer Address", "old company address", "Old Company Address", "past company address", "Past Company Address"], # Added this line
    "current_company_address": ["current company address", "Current Company Address", "new employer address", "New Employer Address", "new company address", "New Company Address", "present company address", "Present Company Address"] # Added this line
}

os.environ["OPENAI_API_KEY"]="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"

def normalize_key(key, synonym_map):
    for canonical_key, synonyms in synonym_map.items():
        if key.lower() in [s.lower() for s in synonyms] or key.lower() == canonical_key.lower(): # Lowercase comparison
            return canonical_key
    return key  


# process_email_json_agent1
def process_email_json_agent1(client, file_path, agent1):
    try:
        with open(file_path, "r") as file:
            data = json.load(file)

        email = data.get("email", {})
        subject = email.get("subject", "No Subject")
        body = email.get("body", {}).get("text", "No Body Provided")

        messages = [
            {
                "role": "user",
                "content": f"Summarize the following email. Subject: {subject}. Body: {body}. Extract a brief summary about the context and return it."
            }
        ]

        response = client.run(agent=agent1, messages=messages)

        if response is None:
            st.error("LLM returned None. Check API key, network, or LLM availability.")
            return None  

        if not response.messages:
            st.error("LLM returned an empty messages list. Check the prompt or agent instructions.")
            return None

        summary = response.messages[-1]['content']
        return {"subject": subject, "summary": summary}

    except FileNotFoundError:
        st.error(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON format: {e}") 
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred in Agent 1 processing: {e}")
        return None

def extract_details_from_emails_agent2(client, file_path, agent2):
    try:
        with open(file_path, "r") as file:
            emails = json.load(file)

        messages = [
            {
                "role": "user",
                "content": f"Extract all details from the following emails and return them in a structured JSON format: {json.dumps(emails)}"
            }
        ]

        response = client.run(agent=agent2, messages=messages)
        raw_output = response.messages[-1]["content"]
        print(f"Raw Agent 2 Output: {raw_output}")

        try:
            reader = csv.reader([raw_output])
            extracted_values = next(reader)
            print(extracted_values)

            # Create the JSON structure
            extracted_data = {
                "personal_information": {
                    "full_name": extracted_values[0],
                    "investor_id": extracted_values[1],
                    "phone_number": extracted_values[2],
                    "email_id": extracted_values[3],
                    "address": extracted_values[4],
                    "date_of_birth": extracted_values[5],
                },
                "employment_details": {
                    "previous_company_details": {
                        "company_name": extracted_values[6],
                        "designation": extracted_values[7],
                        "employment_duration": extracted_values[8],
                        "work_email_address": extracted_values[9],
                        "work_phone_number": extracted_values[10],
                        "address": extracted_values[11], 
                    },
                    "current_company_details": {
                        "company_name": extracted_values[12],
                        "designation": extracted_values[13],
                        "employment_duration": extracted_values[14],
                        "work_email_address": extracted_values[15],
                        "work_phone_number": extracted_values[16],
                        "address": extracted_values[17], 
                    },
                },
            }
            normalized_data = {}
            for key, value in extracted_data.items():
                normalized_key = normalize_key(key, synonym_map)
                normalized_data[normalized_key] = value

            employment_details = normalized_data.get("employment_details", {})
            if "previous_company" in employment_details:
                employment_details["previous_company_details"] = employment_details.pop("previous_company")
            if "current_company" in employment_details:
                employment_details["current_company_details"] = employment_details.pop("current_company")
            normalized_data["employment_details"] = employment_details

            if "employment_details" in normalized_data and normalized_data["employment_details"]:
                for company_type in ["previous_company_details", "current_company_details"]:
                    if company_type in normalized_data["employment_details"] and normalized_data["employment_details"][company_type]:
                        normalized_company_details = {}
                        for key, value in normalized_data["employment_details"][company_type].items():
                             normalized_key = normalize_key(key, synonym_map)
                             normalized_company_details[normalized_key] = value
                        normalized_data["employment_details"][company_type] = normalized_company_details
            print("Extracted Data:")
            print(json.dumps(normalized_data, indent=4))
            return normalized_data

        except csv.Error as e:
            print(f"CSV Parsing Error: {e}. Raw output: {raw_output}")
            return None
        except IndexError as e:
            print(f"Index Error (Likely incorrect number of values returned by agent): {e}. Raw output: {raw_output}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during extracting data: {e}")
            return None
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in file: {file_path}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during file processing or agent execution: {e}")
        return None


def dynamic_query_execution(agent, query_purpose, table_name, conditions, connection_params):
    try:
        
        messages = []
        all_valid = True

        # Connect to the database
        with psycopg2.connect(**connection_params) as conn:
            with conn.cursor() as cursor:
                # Check each condition separately
                for field, value in conditions.items():
                    query = f"SELECT EXISTS(SELECT 1 FROM {table_name} WHERE {field} = %s);"
                    cursor.execute(query, (value,))
                    exists = cursor.fetchone()[0]
                    
                    if not exists:
                        all_valid = False
                        messages.append(f"{field.replace('_', ' ').title()} does not match.")
                    else:
                        messages.append(f"{field.replace('_', ' ').title()} matches.")
        
      
        for message in messages:
            logging.debug(message)
        
        # Determine the overall validation message
        if all_valid:
            return True, "All details validated successfully."
        else:
            return False, "Validation failed: " + ", ".join(messages)

    except psycopg2.Error as e:
        logging.error(f"Database error during {query_purpose} validation: {e}")
        return False, f"Database error during {query_purpose} validation: {e}"
    except Exception as e:
        logging.error(f"Error during {query_purpose} validation: {e}")
        return False, f"Error during {query_purpose} validation: {e}"


def update_employer_details(agent, investor_id, new_employer_details, connection_params):
    try:
        with psycopg2.connect(**connection_params) as conn:
            with conn.cursor() as cursor:
              
                set_parts = []
                values = []

                # Map normalized keys to database columns
                column_map = {
                    "company_name": "company_name",
                    "designation": "designation",
                    "employment_duration": "employment_duration",
                    "work_email_address": "work_email", 
                    "work_phone_number": "work_phone",  
                    "address": "address" 
                }

                for normalized_key, db_column in column_map.items():
                    if normalized_key in new_employer_details and new_employer_details[normalized_key]: 
                        set_parts.append(sql.SQL("{} = %s").format(sql.Identifier(db_column)))
                        values.append(new_employer_details[normalized_key])

                if not set_parts: 
                    return True, "No employer details to update."

                query = sql.SQL("UPDATE investor_employer_details SET {} WHERE investor_id = %s").format(sql.SQL(", ").join(set_parts))
                cursor.execute(query, values + [investor_id])
                conn.commit()

                return True, "Employer details updated successfully."

    except psycopg2.Error as e:
        return False, f"Database error updating employer details: {e}"



# Function to display JSON in a human-readable format
def display_human_readable(data, title="Details"):
    st.markdown(f"<div class='section-header'>{title}</div>", unsafe_allow_html=True)
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                st.markdown(f"<div class='sub-section-header'>{key.replace('_', ' ').title()}:</div>", unsafe_allow_html=True)
                display_human_readable(value)
            elif isinstance(value, list):
                st.markdown(f"<div class='sub-section-header'>{key.replace('_', ' ').title()}:</div>", unsafe_allow_html=True)
                for i, item in enumerate(value, start=1):
                    st.markdown(f"<div style='margin-left: 20px;'><b>Item {i}:</b></div>", unsafe_allow_html=True)
                    display_human_readable(item)
            else:
                st.markdown(f"<div style='margin-left: 20px;'><b>{key.replace('_', ' ').title()}:</b> {value}</div>", unsafe_allow_html=True)




# Set page layout
st.set_page_config(layout="wide")

#  UI 
st.markdown(
    """
    <style>
    body {
        font-family: 'Arial', sans-serif;
        background-color: #f0f2f6;
        color: #333;
    }
    .stApp {
        padding: 20px;
    }

    /* Main Title */
    .header-title {
        font-size: 26px; /* Now clearly smaller */
        color: #1b5e20;
        font-weight: bold;
        text-align: center;
        margin-bottom: 15px;
        padding: 10px;
        background: linear-gradient(to right, #a5d6a7, #4caf50);
        border-radius: 8px;
        color: white;
    }

    /* Sub-Headers */
    .sub-header {
        font-size: 20px; /* Reduced for better balance */
        color: #2e7d32;
        margin-top: 12px;
        margin-bottom: 8px;
        font-weight: bold;
        border-bottom: 2px solid #66bb6a;
        padding-bottom: 4px;
    }

    /* Compact Boxed Sections */
    .box {
        background-color: #ffffff;
        border: 1px solid #dcedc8;
        padding: 12px;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.15);
        margin-bottom: 10px; /* Reduced space */
    }

    /* Success Status */
    .status-box {
        background-color: #e8f5e9;
        border: 2px solid #388e3c;
        padding: 10px;
        border-radius: 6px;
        color: #1b5e20;
        font-weight: bold;
        text-align: center;
        margin-top: 10px;
        font-size: 16px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    /* Error Message */
    .error-box {
        background-color: #ffebee;
        border: 2px solid #d32f2f;
        padding: 10px;
        border-radius: 6px;
        color: #b71c1c;
        font-weight: bold;
        text-align: center;
        margin-top: 10px;
        font-size: 16px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    /* Info Message */
    .info-box {
        background-color: #e3f2fd;
        border: 2px solid #1565c0;
        padding: 10px;
        border-radius: 6px;
        color: #0d47a1;
        font-weight: bold;
        text-align: center;
        margin-top: 10px;
        font-size: 16px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# Header title
st.markdown("<div class='header-title'>AI Assistance to Update Investor's Basic Details</div>", unsafe_allow_html=True)

connection_params = {  
    "dbname": "Investor Details",
    "user": "postgres",
    "password": "admin",
    "host": "localhost",
    "port": "5432"
}

# Split UI into two panels
col1, col2 = st.columns([4, 2])

# **Left Panel: Email Selection & JSON Display**
with col1:
    st.header("📩 Email Selection")

    # Load available JSON files
    json_directory = "email_data"
    if not os.path.exists(json_directory):
        os.makedirs(json_directory)
    json_files = [os.path.join(json_directory, f) for f in os.listdir(json_directory) if f.endswith('.json')]

    # Define a fixed set of ticket numbers to assign
    ticket_numbers = [103456, 150245, 107568, 108764, 107487]
    assigned_tickets = {}

    # Create a mapping of formatted filenames
    formatted_filenames = {}
    for index, file_path in enumerate(json_files):
        filename = os.path.basename(file_path).replace('.json', '')  
        formatted_name = filename.split("_")[0].capitalize() 


        # Assign ticket number in a fixed manner (Avoiding duplication)
        if file_path not in assigned_tickets:
            assigned_tickets[file_path] = ticket_numbers[index % len(ticket_numbers)] 

        ticket_number = assigned_tickets[file_path]  

        # Load email data to get the subject
        try:
            with open(file_path, "r") as f:
                email_data = json.load(f) or {}
            subject = email_data.get('email', {}).get('subject', 'No Subject')
        except (json.JSONDecodeError, FileNotFoundError):
            subject = "No Subject"

      
        formatted_subject = subject.replace("Fwd:", "").strip()

        
        formatted_filenames[file_path] = f"#Ticket No: {ticket_number}, {formatted_name} {formatted_subject}"
    # Dropdown to select an email with formatted names
    selected_file = st.selectbox("Select an Email", list(formatted_filenames.keys()), format_func=lambda x: formatted_filenames[x], key="email_select")

  
    if "selected_file" not in st.session_state or st.session_state.selected_file != selected_file:
        st.session_state.selected_file = selected_file
        email_data = {}  
    # Display email content automatically
    if selected_file:
        try:
            with open(selected_file, "r") as f:
                email_data = json.load(f) or {}

            email_content = email_data.get('email', {})

            st.markdown(f"**📧 From:** {email_content.get('from', 'Unknown Sender')}")
            st.markdown(f"**📜 Subject:** {email_content.get('subject', 'No Subject')}")

            
            st.text_area("📜 Email Body", email_content.get('body', {}).get('text', 'No content available'), height=300)

        except (json.JSONDecodeError, FileNotFoundError) as e:
            st.error(f"Error loading JSON file: {e}")

# Right Panel: AI Processing Responses
with col2:
    st.header("🤖 Email Agent AI")

    if st.button("Process Email"):
        #with st.spinner("Processing..."):
            client = Swarm()
            agent1 = Agent(
                name="Email Summarization Agent",
                instructions="Extract the core request or action from the following email and summarize it in ONE SENTENCE."
            )
            agent2 = Agent(
                name="Detail Extraction Agent",
                instructions="""
                Extract the following information from the provided text:
                * Full Name
                * Investor ID
                * Mobile Number
                * Email ID
                * Address
                * Date of birth
                * Previous Company Name
                * Previous Designation
                * Previous Employment Duration
                * Previous Work Email
                * Previous Work Phone
                * Previous Work Phone
                * Current Company
                * Current Designation
                * Current Employment Duration
                * Current Work Email
                * Current Work Phone
                * Current Work Address

                Return the extracted information as comma-separated values (CSV) in the order listed above. If a piece of information cannot be found, return an empty string for that field. Do not include any headers or extra text; only the comma-separated values.
                """
            )
            agent3 = Agent(
                name="Validation Agent",
                instructions="You are a helpful agent responsible for dynamically generating and executing queries to validate investor details against a database. Your task is to connect to the database, validate investor ID, investor email Id, investor phone number and old employer details, and return validation results. If any detail is invalid, stop further processing and provide an appropriate error message."
            )
            agent4 = Agent(
                name="Update Agent",
                instructions="You are a helpful agent responsible for updating the database with new employer details. Your task is to generate and execute an update query to modify the employer details for the given investor ID. If the update is successful, return a confirmation message."
            )

            # **Agent 1: **
            st.markdown("<div class='sub-header'>📝 Task 1: Email Summary</div>", unsafe_allow_html=True)
            with st.spinner("🔍 Analyzing the mail..."):
                time.sleep(5)  
                agent1_response = process_email_json_agent1(client, selected_file, agent1)

            if agent1_response:
                st.markdown(f"**✉️ Subject:** {agent1_response['subject']}")
                st.markdown(f"**📑 Summary:** {agent1_response['summary']}")
            else:
                st.markdown("<div class='error-box'>⚠️ Error in summarizing the email.</div>", unsafe_allow_html=True)

            # **Agent 2: **
            st.markdown("<div class='sub-header'>🔍 Task 2: Extracted Details</div>", unsafe_allow_html=True)
            with st.spinner("🔎 Scanning the investor details..."):
                time.sleep(10)  
                extracted_data = extract_details_from_emails_agent2(client, selected_file, agent2) or {}

            if extracted_data:
                st.markdown("### 📌 Investor Personal Information")
                personal_info = extracted_data.get("personal_information", {})
                for key, value in personal_info.items():
                    st.markdown(f"**{key.replace('_', ' ').title()}:** {value}")

                
                st.markdown("<div class='info-box' style='opacity: 0.6;'>⏳ Extracting employment details...</div>", unsafe_allow_html=True)
                time.sleep(5)
            #     st.markdown("### 🏢 Employment Details")
            #     employment_details = extracted_data.get("employment_details", {})
            #     for key, value in employment_details.items():
            #         st.markdown(f"**{key.replace('_', ' ').title()}:** {value}")
            # else:
            #     st.markdown("<div class='error-box'>⚠️ Error in extracting investor details.</div>", unsafe_allow_html=True)
                st.markdown("### 🏢 Employment Details")
                employment_details = extracted_data.get("employment_details", {})
                for section_key, company_info in employment_details.items():
                    section_title = section_key.replace('_', ' ').title()
                    st.markdown(f"#### {section_title}")
                    if isinstance(company_info, dict):
                        for field_key, field_value in company_info.items():
                            label = field_key.replace('_', ' ').title()
                            if field_value:
                                st.markdown(f"- **{label}:** {field_value}")
                    else:
                        st.markdown("<div class='error-box'>⚠️ Error in extracting investor details.</div>", unsafe_allow_html=True)

          # **Agent 3: Validate Details**
            st.markdown("<div class='sub-header'>✅ Task 3: Validation</div>", unsafe_allow_html=True)
            investor_id = personal_info.get("investor_id")
            email_id = personal_info.get("email_id")
            phone_number = personal_info.get("phone_number")

            conditions = {
                "investor_id": investor_id,
                "email_id": email_id,
                "phone_number": phone_number
            }

            missing_fields = [key for key, value in conditions.items() if not value]

            if missing_fields:
                missing_fields_formatted = ', '.join([f"{field.replace('_', ' ')}" for field in missing_fields])
                st.markdown(f"<div class='error-box'>⚠️ We can't proceed for validation as the following details are missing: {missing_fields_formatted}. Please collect them from the investor.</div>", unsafe_allow_html=True)
            else:
                # Simulate connecting to the database
                with st.spinner("🖥️ Connecting to DB..."):
                    time.sleep(6)  
                st.markdown("<div class='status-box'>✅ Connected to database</div>", unsafe_allow_html=True)

                with st.spinner("🔍 Validating details..."):
                    valid, message = dynamic_query_execution(agent3, "Investor Identity Validation", "investor_identity_details", conditions, connection_params)
                
                if valid:
                    st.markdown("<div class='status-box'>✔️ All details verified successfully.</div>", unsafe_allow_html=True)

                    # Enhanced Employer Validation
                    company_name = employment_details.get("previous_company_details", {}).get("company_name")
                    work_email = employment_details.get("previous_company_details", {}).get("work_email_address")
                    old_work_phone = employment_details.get("previous_company_details", {}).get("work_phone_number")

                    employer_conditions = {
                        "company_name": company_name,
                        "work_email": work_email,
                        "work_phone": old_work_phone
                    }

                    with st.spinner("🏢 Validating Employment Details..."):
                        time.sleep(8)
                        valid_employer, employer_message = dynamic_query_execution(
                            agent3, "Old Employer Details", "investor_employer_details", employer_conditions, connection_params
                        )

                    if valid_employer:
                        st.markdown("<div class='status-box'>✔️ Employment details verified successfully.</div>", unsafe_allow_html=True)
                        
                        # **Agent 4: **
                        st.markdown("<div class='sub-header'>💾 Task 4: Updating Records</div>", unsafe_allow_html=True)
                        with st.spinner("🖥️ Updating details in the database..."):
                            time.sleep(12)
                            update_successful, update_message = update_employer_details(
                                agent4, investor_id, employment_details.get("current_company_details", {}), connection_params
                            )

                        if update_successful:
                            st.markdown("<div class='status-box'>✔️ Update Successful: Records updated in the database.</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div class='error-box'>⚠️ Error while updating records: {update_message}</div>", unsafe_allow_html=True)
                    else:
                        errors = employer_message.split(", ")
                        detailed_error_message = ". ".join(errors)
                        st.markdown(f"<div class='error-box'>⚠️ The employer information provided does not match our records. {detailed_error_message}. Please verify these details with the employer.</div>", unsafe_allow_html=True)
                else:
                    errors = message.split(", ")
                    detailed_error_message = ". ".join(errors)
                    st.markdown(f"<div class='error-box'>⚠️ The investor has provided incorrect information. {detailed_error_message}. I cannot update the database. Please verify the details with the investor.</div>", unsafe_allow_html=True)

