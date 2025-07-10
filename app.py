import os
import re
import time
import pandas as pd
from flask import Flask, request, jsonify, render_template, session, send_from_directory
from flask_cors import CORS
 
app = Flask(__name__)
CORS(app)
app.secret_key = 'wiqar123'
 
# Load Excel SOP data
sop_df = pd.read_excel('sop_docs/sop_data2.xlsx')
 
@app.route('/static_files/<path:filename>')
def static_files(filename):
    return send_from_directory('static_files', filename)
 
def convert_embeds_to_html(content):
    content = re.sub(r'\[image:\s*([^\]]+)\]',
                     r'<br><img src="/static_files/\1" style="max-width:100%; border:1px solid #ccc;"><br>',
                     content, flags=re.IGNORECASE)
 
    def file_replacer(match):
        filename = match.group(1).strip()
        filepath = os.path.join('static_files', filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = f.read()
                return f'<br><strong>{filename}:</strong><br><pre>{data}</pre><br>'
            except:
                return f'<br><em>Error reading file: {filename}</em><br>'
        else:
            return f'<br><em>File not found: {filename}</em><br>'
 
    content = re.sub(r'\[file:\s*([^\]]+)\]', file_replacer, content, flags=re.IGNORECASE)
    return content
 
@app.route('/')
def home():
    session.clear()
    return render_template('index_sop.html')
 
@app.route('/ask', methods=['POST'])
def ask():
    user_query = request.form.get('query', '').strip()
    delay = 2  # seconds for typing simulation
 
    if not user_query:
        return jsonify({'answer': "Please enter a valid question."})
 
    if 'started' not in session:
        session['started'] = True
        time.sleep(delay)
        return jsonify({'answer': "Hello! 👋 How may I assist you in SOP queries?"})
 
    # Handle follow-up: steps execution
    if session.get('awaiting_step_confirmation'):
        if user_query.lower() in ['yes', 'y']:
            sop_name = session.get('last_sop')
            filtered = sop_df[sop_df['SOP Name'].str.contains(sop_name, case=False, na=False)]
            steps = filtered[['Subsection', 'Content']].dropna()
 
            response = "<strong>Steps to be executed:</strong><br>"
            for subsec in steps['Subsection'].unique():
                sub_contents = steps[steps['Subsection'] == subsec]['Content']
                response += f"<br><strong>{subsec}:</strong><br>"
                for content in sub_contents:
                    response += convert_embeds_to_html(str(content)) + "<br>"
            session.pop('awaiting_step_confirmation')
            time.sleep(delay)
            return jsonify({'answer': response + "<br><br>Do you need more assistance? (Yes/No)"})
 
        elif user_query.lower() in ['no', 'n']:
            session.pop('awaiting_step_confirmation')
            session['ask_more'] = True
            time.sleep(delay)
            return jsonify({'answer': "Do you need more assistance? (Yes/No)"})
 
    # Handle chat end
    if session.get('ask_more'):
        if user_query.lower() in ['no', 'n']:
            session.clear()
            time.sleep(delay)
            return jsonify({'answer': "Okay, happy to help. Goodbye! 👋"})
        else:
            session.pop('ask_more')
            time.sleep(delay)
            return jsonify({'answer': "Sure, please ask your SOP-related query."})
 
    # === Step 1: Try to extract probable SOP name based on keywords ===
    keywords = re.findall(r'\b[a-zA-Z]+\b', user_query.lower())
    possible_matches = pd.DataFrame()
 
    for word in keywords:
        matched = sop_df[sop_df['SOP Name'].str.contains(word, case=False, na=False)]
        if not matched.empty:
            possible_matches = pd.concat([possible_matches, matched])
 
    if possible_matches.empty:
        time.sleep(delay)
        return jsonify({'answer': "Sorry, I couldn't find any SOP related to your query."})
 
    # Use the most common SOP Name among matches
    most_common_sop = (
        possible_matches['SOP Name']
        .value_counts()
        .idxmax()
    )
 
    session['last_sop'] = most_common_sop
    session['awaiting_step_confirmation'] = True
 
    matched_rows = sop_df[sop_df['SOP Name'].str.lower() == most_common_sop.lower()]
    response = f"<strong>SOP Found:</strong> {most_common_sop}<br><br>"
 
    for section in ['Problem Statement', 'Impact', 'Scenarios']:
        sec_rows = matched_rows[matched_rows['Section'].str.lower() == section.lower()]
        if not sec_rows.empty:
            response += f"<strong>{section}:</strong><br>"
            for content in sec_rows['Content']:
                if pd.isna(content): continue
                response += convert_embeds_to_html(str(content)) + "<br>"
            response += "<br>"
 
    response += "Would you like to view the steps to be executed? (Yes/No)"
    time.sleep(delay)
    return jsonify({'answer': response})
 
if __name__ == '__main__':
    app.run(debug=True)