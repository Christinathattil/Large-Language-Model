from dotenv import load_dotenv
load_dotenv()  # Load all environment variables

import streamlit as st
import os
import sqlite3
import pandas as pd
import io
import google.generativeai as genai
import matplotlib.pyplot as plt
import seaborn as sns


## Configure our API key
genai.configure(api_key=os.getenv("GOOGLE_API"))

# Function to load Google Gemini model and provide SQL query as response
def get_gemini_response(question, prompt):
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content([prompt[0], question])
    sql_query = response.text.strip().replace('```sql', '').replace('```', '').strip('"').strip("'")
    print("Generated SQL Query:", sql_query)  # Debugging output
    return sql_query

# Function to retrieve query from the SQL database
def read_sql_query(sql_query, db_name):
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        data = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]  # Extract column names
        conn.close()
        return data, columns, None  # Return data, column names, and no error
    except sqlite3.Error as e:
        return None, None, str(e)  # Return None values and the error message

## Define your prompt
prompt = [
    """
    You are an expert in converting English questions to SQL queries! 
    The SQL database contains the following tables:
    
    1. STUDENT (STUDENT_ID, NAME, CLASS, SECTION, MARKS)
    2. COURSE (COURSE_ID, COURSE_NAME, INSTRUCTOR)
    3. ENROLLMENT (STUDENT_ID, COURSE_ID, ENROLLMENT_DATE)
    
    Important rules:
    - Return ONLY the SQL query without any additional text or formatting.
    - Do not include quotes (''') or markdown formatting.
    - End each query with a semicolon.
    - Use double quotes for string literals.
    - Ensure the query properly joins tables where necessary.
    
    Examples:
    Question: How many students are enrolled in each course?
    SELECT C.COURSE_NAME, COUNT(E.STUDENT_ID) AS ENROLLMENT_COUNT 
    FROM ENROLLMENT E 
    JOIN COURSE C ON E.COURSE_ID = C.COURSE_ID 
    GROUP BY C.COURSE_NAME;
    
    Question: Get details of students enrolled in 'Artificial Intelligence'.
    SELECT S.NAME, S.CLASS, S.SECTION, S.MARKS 
    FROM STUDENT S 
    JOIN ENROLLMENT E ON S.STUDENT_ID = E.STUDENT_ID 
    JOIN COURSE C ON E.COURSE_ID = C.COURSE_ID 
    WHERE C.COURSE_NAME = "Artificial Intelligence";
    """
]

## Streamlit App
st.set_page_config(page_title="Retrieve SQL Queries from Gemini")

st.header("Upload a Database or Use Default")

# File upload feature
st.write("**Optional:** Upload your own dataset or use the default database.")

uploaded_file = st.file_uploader("Upload your SQL data (txt or CSV file)", type=['txt', 'csv'])

# User input for database name if uploading a file
db_name = "student.db"  # Default database
if uploaded_file:
    db_name = st.text_input("Enter a name for your database (without extension):") + ".db"

# Function to create tables from uploaded content
def process_and_store_data(file_content, database_name):
    content = file_content.getvalue().decode('utf-8')
    
    # Convert content to a list of lines
    lines = content.split("\n")

    # Dictionary to hold table data
    tables = {}
    current_table = None
    headers = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Identify table headers based on "_ID" in the first column
        if line.split(",")[0].endswith("_ID"):
            current_table = line.split(",")[0].replace("_ID", "")  # Extract table name
            headers = line.split(",")  # Store headers
            tables[current_table] = [headers]  # Initialize table with headers
        else:
            if current_table:
                tables[current_table].append(line.split(","))  # Append row data

    # Connect to SQLite and create tables in the new database
    conn = sqlite3.connect(database_name)
    
    for table_name, data in tables.items():
        df = pd.DataFrame(data[1:], columns=data[0])  # Skip headers for data
        df.to_sql(table_name.upper(), conn, if_exists="replace", index=False)
    
    conn.close()
    st.success(f"Database '{database_name}' created successfully with all tables!")

# Process the uploaded file
if uploaded_file:
    process_and_store_data(uploaded_file, db_name)
else:
    st.info("Using the default database.")

st.write(f"**Current Database in Use:** `{db_name}`")

# User input
question = st.text_input("Enter your question: ", key='input')
if st.button("Generate SQL Query"):
    sql_query = get_gemini_response(question, prompt)
    st.subheader("Generated SQL Query")
    st.code(sql_query, language='sql')

if st.button("Execute and Show Results"):
    sql_query = get_gemini_response(question, prompt)
    data, columns, error_msg = read_sql_query(sql_query, db_name)

    if error_msg:
        st.error(error_msg)
    elif data:
        df = pd.DataFrame(data, columns=columns)
        st.subheader("Query Results")
        st.dataframe(df)

        # Enhanced Visualization Section
        if st.checkbox("Visualize Data"):
            st.subheader("Data Visualization")

            # Detect numeric and categorical columns
            numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
            categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
            
            if len(numeric_cols) > 0:
                # Create two columns for visualization controls
                col1, col2 = st.columns(2)
                
                with col1:
                    plot_type = st.selectbox(
                        "Choose Plot Type",
                        ["Bar Chart", "Line Chart", "Scatter Plot", "Box Plot", "Violin Plot"]
                    )
                    
                    x_axis = st.selectbox(
                        "Select X-axis:",
                        categorical_cols + numeric_cols,
                        key='x_axis'
                    )

                with col2:
                    y_axis = st.selectbox(
                        "Select Y-axis:",
                        numeric_cols,
                        key='y_axis'
                    )
                    
                    color_by = st.selectbox(
                        "Color by (optional):",
                        ['None'] + categorical_cols,
                        key='color'
                    )

                # Create figure with improved styling
                plt.style.use('seaborn')
                fig, ax = plt.subplots(figsize=(10, 6))

                try:
                    if plot_type == "Bar Chart":
                        if color_by != 'None':
                            sns.barplot(data=df, x=x_axis, y=y_axis, hue=color_by, ax=ax)
                        else:
                            sns.barplot(data=df, x=x_axis, y=y_axis, ax=ax)
                    
                    elif plot_type == "Line Chart":
                        if color_by != 'None':
                            sns.lineplot(data=df, x=x_axis, y=y_axis, hue=color_by, ax=ax)
                        else:
                            sns.lineplot(data=df, x=x_axis, y=y_axis, ax=ax)
                    
                    elif plot_type == "Scatter Plot":
                        if color_by != 'None':
                            sns.scatterplot(data=df, x=x_axis, y=y_axis, hue=color_by, ax=ax)
                        else:
                            sns.scatterplot(data=df, x=x_axis, y=y_axis, ax=ax)
                    
                    elif plot_type == "Box Plot":
                        if color_by != 'None':
                            sns.boxplot(data=df, x=x_axis, y=y_axis, hue=color_by, ax=ax)
                        else:
                            sns.boxplot(data=df, x=x_axis, y=y_axis, ax=ax)
                    
                    elif plot_type == "Violin Plot":
                        if color_by != 'None':
                            sns.violinplot(data=df, x=x_axis, y=y_axis, hue=color_by, ax=ax)
                        else:
                            sns.violinplot(data=df, x=x_axis, y=y_axis, ax=ax)

                    # Improve plot styling
                    plt.xticks(rotation=45, ha='right')
                    plt.tight_layout()
                    
                    # Add title and labels
                    ax.set_title(f'{plot_type} of {y_axis} by {x_axis}', pad=20)
                    ax.set_xlabel(x_axis)
                    ax.set_ylabel(y_axis)

                    # Display the plot
                    st.pyplot(fig)
                    plt.close()

                except Exception as e:
                    st.error(f"Error creating visualization: {str(e)}")
                    st.write("Try selecting different columns or plot type.")
            else:
                st.warning("No numeric columns available for visualization. The current query results don't contain any numerical data to plot.")
    else:
        st.warning("No data returned from the query.")