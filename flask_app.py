import os
from flask import Flask, render_template_string
from main import *  # Import your function

app = Flask(__name__)

# The path to the file your main.py creates
SQL_FILE_PATH = "audit_query.sql"


@app.route('/')
def index():
    # 1. Trigger the script logic
    with open('audit_query.sql','w') as f:
        f.write(f"""{get_workflow_query()}\n{get_dataset_queries()} \n SELECT * FROM datasets""")   
    
    # 2. Read the file content
    if os.path.exists(SQL_FILE_PATH):
        with open(SQL_FILE_PATH, "r") as f:
            sql_content = f.read()
    else:
        sql_content = "Error: SQL file was not generated."

    # 3. Display it in a simple HTML format
    return render_template_string("""
        <h1>Generated SQL Query</h1>
        <pre style="background: #f4f4f4; padding: 15px; border: 1px solid #ddd;">
{{ content }}
        </pre>
        <br>
        <a href="/">Run Again</a>
    """, content=sql_content)

if __name__ == '__main__':
    app.run(debug=True)