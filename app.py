import ast
import datetime
import json
import random
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
import os
import google.generativeai as genai
import sqlite3
import google.generativeai as genai

# Start App
app = Flask(__name__)
template_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), 'views'))
app = Flask(__name__, template_folder=template_folder)
app.secret_key = '<5@V2z+dY3W'

# Api Key
apikey = "AIzaSyBtvWWX6uqQA_gw6mpxqAiAtG86fk0D_wA"

# Middlewares
@app.before_request
def go_to_home():
    if (request.endpoint == 'login') and ("loggedin" in session):
        return redirect(url_for('home'))
    
@app.before_request
def go_to_login():
    if (request.endpoint in ('show_exams', 'show_exam')) and ("loggedin" not in session or not session["loggedin"]):
        return redirect(url_for('login'))

def response_palm(prompt):
    genai.configure(api_key=apikey)

    defaults = {
      'model': 'models/text-bison-001',
      'temperature': 0.7,
      'candidate_count': 1,
      'top_k': 40,
      'top_p': 0.95,
      'max_output_tokens': 1024,
      'stop_sequences': [],
      'safety_settings': [{"category":"HARM_CATEGORY_DEROGATORY","threshold":"BLOCK_LOW_AND_ABOVE"},{"category":"HARM_CATEGORY_TOXICITY","threshold":"BLOCK_LOW_AND_ABOVE"},{"category":"HARM_CATEGORY_VIOLENCE","threshold":"BLOCK_MEDIUM_AND_ABOVE"},{"category":"HARM_CATEGORY_SEXUAL","threshold":"BLOCK_MEDIUM_AND_ABOVE"},{"category":"HARM_CATEGORY_MEDICAL","threshold":"BLOCK_MEDIUM_AND_ABOVE"},{"category":"HARM_CATEGORY_DANGEROUS","threshold":"BLOCK_MEDIUM_AND_ABOVE"}],
    }

    response = genai.generate_text(**defaults, prompt=prompt)
    return response.result

# Routes
@app.route("/")
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        idCardNumber = request.form['idCardNumber']
        password = request.form['password']

        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db'))
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE idCardNumber = ? AND password = ?', (idCardNumber, password))
        user = cursor.fetchone()

        conn.close()

        if user:
            session['loggedin'] = True
            session['userId'] = user[0]
            session['userName'] = user[1]
            session['userIdCardNumber'] = user[2]
            session['userRole'] = user[4]

            return redirect('/')
        else:
            return render_template('login.html', error='Invalid ID card number or password')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        idCardNumber = request.form['idCardNumber']
        password = request.form['password']
        role = 'student'

        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db'))
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE idCardNumber=?", (idCardNumber,))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.commit()
            conn.close()
            return render_template('register.html', error='ID card number already exists!')
        else:
            cursor.execute("INSERT INTO users (name, idCardNumber, password, role) VALUES (?, ?, ?, ?)", (name, idCardNumber, password, role))
            conn.commit()
            conn.close()
            return redirect('/login')

    return render_template('register.html')
    

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('userId', None)
    session.pop('userName', None)
    session.pop('userIdCardNumber', None)
    session.pop('userRole', None)
    return redirect('/login')

@app.route('/exams')
def show_exams():
    user_id = session['userId']
    
    conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db'))
    cursor = conn.cursor()

    if(session['userRole'] == 'student'):
        cursor.execute('SELECT exams.*, users_exams.* FROM exams LEFT JOIN users_exams ON exams.id = users_exams.exam_id AND users_exams.user_id = ?', (user_id,))
    else:
        cursor.execute("SELECT * FROM exams")
        
    exams = cursor.fetchall()

    conn.commit()
    conn.close()

    return render_template('exams.html', exams=exams)

@app.route('/delete-exam/<int:exam_id>')
def delete_exam(exam_id):
    conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db'))
    cursor = conn.cursor()

    cursor.execute('DELETE FROM exams WHERE id = ?', (exam_id,))
    cursor.execute('DELETE FROM users_exams WHERE exam_id = ?', (exam_id,))

    conn.commit()
    conn.close()
    return redirect('/exams')

@app.route('/create-exam', methods=['GET', 'POST'])
def create_exam():
    if request.method == 'POST':
        name = request.form.get('name')
        questions_count = int(request.form.get('questions'))
        questions = request.form.getlist('question[]')
        answers = request.form.getlist('answer[]')
        duration = int(request.form.get('duration'))

        questions_and_answers = [{"question": q, "answer": a} for q, a in zip(questions, answers)]
        answers_json = json.dumps(questions_and_answers)

        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db'))
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO exams (name, questions, answers, duration)
            VALUES (?, ?, ?, ?)
        ''', (name, questions_count, answers_json, duration))
        conn.commit()
        conn.close()

        return redirect('/exams')
    
    return render_template('create_exam.html')

@app.route('/exam/<int:exam_id>')
def show_exam(exam_id):
    user_id = session['userId']
    conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db'))
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM exams WHERE id = ?', (exam_id,))
    exam_data = cursor.fetchone()
    
    if exam_data:
        exam = {
            'id': exam_data[0],
            'name': exam_data[1],
            'questions': exam_data[2],
            'answers': json.loads(exam_data[3]),
            'duration': exam_data[4] 
        }

        cursor.execute('SELECT * FROM users_exams WHERE user_id = ? AND exam_id = ?', (user_id, exam_id))
        user_test = cursor.fetchone()

        if not user_test:
            start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            end_time = datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S') + datetime.timedelta(minutes=int(exam['duration']))
            
            cursor.execute('INSERT INTO users_exams (user_id, exam_id, start_time, end_time, full_mark) VALUES (?, ?, ?, ?, ?)', (user_id, exam_id, start_time, end_time, len(exam['answers'])))
    
        cursor.execute('SELECT * FROM users_exams WHERE user_id = ? AND exam_id = ?', (user_id, exam_id))
        user_test = cursor.fetchone()

        conn.commit()
        conn.close()

        answers_indexes = []
        answers_list = []
        selected_indexes = random.sample(range(len(exam['answers'])), min(int(exam['questions']), len(exam['answers'])))

        for index in selected_indexes:
            question = exam['answers'][index]
            answers_indexes.append(index)
            answers_list.append(question)

        exam['answers'] = answers_list
        exam['answers_indexes'] = json.dumps(answers_indexes)

        return render_template('exam.html', exam=exam, user_test=user_test)
    else:
        conn.close()
        return "Exam not found", 404
    
@app.route('/results-exam/<int:exam_id>')
def results_exam(exam_id):
    conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db'))
    cursor = conn.cursor()
   
    cursor.execute('SELECT * FROM exams WHERE id = ?', (exam_id,))
    exam = cursor.fetchone()

    cursor.execute('''
        SELECT users_exams.*, users.name 
        FROM users_exams
        LEFT JOIN users ON users_exams.user_id = users.id
        WHERE users_exams.exam_id = ?;
    ''', (exam_id,))
    exam_results = cursor.fetchall()


    conn.commit()
    conn.close()

    return render_template('results_exam.html', exam=exam, exam_results=exam_results)

@app.route('/submit-exam', methods=['POST'])
def submit_exam():
    if 'userId' not in session:
        return redirect(url_for('login'))
    
    user_id = session['userId']

    exam_id = request.form.get('exam_id')
    answers = request.form.getlist('answer[]')
    answers_indexes = request.form.get('answers_indexes')
    answers_indexes = ast.literal_eval(answers_indexes)

    with sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')) as conn:
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM exams WHERE id = ?', (exam_id,))
        exam_data = cursor.fetchone()
        exam_data = json.loads(exam_data[3])

        if exam_data:
            mark = 0

            exam_answers = exam_data

            for index, answer_index in enumerate(answers_indexes):
                    user_response = response_palm(f"""
                        If true, write 'yes'. If not, type 'no'.
                        Does the phrase '{exam_answers[answer_index]['answer']}' describe the meaning of '{answers[index]}'?
                    """)

                    if user_response.lower() == 'yes': mark += 1

            cursor.execute('UPDATE users_exams SET mark = ?, is_finshed = ? WHERE user_id = ? AND exam_id = ?', (mark, 1, user_id, exam_id))
            conn.commit()

            return render_template('result_exam.html', mark=mark, fullMark=len(answers_indexes))
        else:
            return "Exam not found", 404
        
if __name__ == '__main__':
    app.run(debug=True)