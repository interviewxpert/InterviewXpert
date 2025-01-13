from flask import Flask, render_template, redirect, url_for, session, request, jsonify, flash, json
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, ValidationError
import hashlib
from flask_mysqldb import MySQL
import google.generativeai as genai
import openai
import constants as c

app = Flask(__name__)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'ix_db'
app.secret_key = 'flask_secret'

# Database Config
TABLE_PREFIX = "ix_"

mysql = MySQL(app)

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(hashed_password, password):
    return hashed_password == hash_password(password)

# Forms
class RegisterForm(FlaskForm):
    firstname = StringField("FirstName", validators=[DataRequired()])
    lastname = StringField("LastName", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Register")

    def validate_email(self, field):
        cursor = mysql.connection.cursor()
        cursor.execute(f"SELECT * FROM {TABLE_PREFIX}users WHERE email=%s", (field.data,))
        user = cursor.fetchone()
        cursor.close()
        if user:
            raise ValidationError('Email already taken.')

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        firstname = form.firstname.data
        lastname = form.lastname.data
        username = firstname.lower() + "_" + lastname.lower()
        email = form.email.data
        password = form.password.data

        # hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        hashed_password = hash_password(password)

        cursor = mysql.connection.cursor()
        cursor.execute(f"INSERT INTO {TABLE_PREFIX}users (firstname, lastname, username, email, password) VALUES (%s, %s, %s, %s, %s)", (firstname, lastname, username, email, hashed_password))
        mysql.connection.commit()
        cursor.close()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    print("Form Submitted")
    if form.validate_on_submit():
        print("Form Validated")
        email = form.email.data
        password = form.password.data

        cursor = mysql.connection.cursor()
        cursor.execute(f"SELECT * FROM {TABLE_PREFIX}users WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()

        hashed_password_from_db = user[4]
        print(verify_password(hashed_password_from_db, password))
        
        if user and verify_password(hashed_password_from_db, password):
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password.", "danger")

    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        return render_template('panel/dashboard.html', user_name=session['user_name'])
    flash("You need to log in first.", "warning")
    return redirect(url_for('login'))

# Interview Simulator
@app.route('/simulation', methods=['GET'])
def simulation():
    return render_template('panel/simulation.html')
    
@app.route('/api/save-settings', methods=['POST'])
def save_settings():
    data = request.get_json()

    interview_type = data.get('interviewType')
    difficulty = data.get('difficulty')
    field = data.get('field')
    length = data.get('length')
    feedback_focus = data.get('feedbackFocus')

    # Define table name with prefix
    table_name = f"{TABLE_PREFIX}interview_settings"

    # SQL statements
    create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL UNIQUE, -- Add UNIQUE constraint
            interview_type VARCHAR(255) NOT NULL,
            difficulty VARCHAR(255) NOT NULL,
            field VARCHAR(255) NOT NULL,
            length INT NOT NULL,
            feedback_focus VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """

    update_or_insert_sql = f"""
        INSERT INTO {table_name} (user_id, interview_type, difficulty, field, length, feedback_focus)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
            interview_type = VALUES(interview_type), 
            difficulty = VALUES(difficulty), 
            field = VALUES(field), 
            length = VALUES(length), 
            feedback_focus = VALUES(feedback_focus)
    """

    try:
        cursor = mysql.connection.cursor()
        cursor.execute(create_table_sql)
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not logged in'}), 403
        
        cursor.execute(update_or_insert_sql, (user_id, interview_type, difficulty, field, length, feedback_focus))
        
        mysql.connection.commit()
    except Exception as e:
        mysql.connection.rollback()
        
        return jsonify({'error': f"Failed to save settings: {str(e)}"}), 500
    finally:
        cursor.close()

    return jsonify({'success': True, 'message': 'Settings saved successfully.'})


# AI Model
def aiModel(prompt):
    genai.configure(api_key=c.GEMINI_API)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text.strip()

def aiModelGPT(prompt):
    import openai
    openai.api_key = c.OPENAI_API_KEY
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        ai_response = response['choices'][0]['message']['content']
        return ai_response.strip()

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# AI Questoin Generation
@app.route('/api/get-question', methods=['POST'])
def get_first_question():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not logged in'}), 403

    table_name = f"{TABLE_PREFIX}interview_settings"

    data = request.get_json()
    question_log = data.get('questions_log', [])
    print(f"questions log: {question_log}")

    try:
        cursor = mysql.connection.cursor()
        cursor.execute(f"SELECT interview_type, difficulty, field, feedback_focus FROM {table_name} WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({'error': 'No settings found for the user'}), 404

        interview_type, difficulty, field, feedback_focus = result
        
        asked_questions = ""
        if question_log:
            asked_questions = "\n".join(f"- {q['question']}" for q in question_log)
        
        prompt = (
            f"Generate a {difficulty} level interview question (not too long can answer with voice or text) for a {interview_type} interview for the field of {field}.\n"
            f"The question should focus on {feedback_focus} skills."
        )
        
        if asked_questions:
            prompt += f"The following questions have already been asked and should not be repeated:\n{asked_questions}"
        
        question = aiModelGPT(prompt)
        # question = aiModel(prompt)

    except Exception as e:
        return jsonify({'error': f"Failed to fetch settings or generate question: {str(e)}"}), 500

    finally:
        cursor.close()

    return jsonify({'question': question})

# AI Question Answer/Response
@app.route('/api/get-answer', methods=['POST'])
def get_answer():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not logged in'}), 403

    data = request.get_json()
    print(data)
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400
    
    question = data.get('ix_question')
    answer = data.get('ix_answer')
    print(question)
    print(answer)
    if not question or not answer:
        return jsonify({'error': 'Missing question or answer'}), 400
    
    prompt = (
        f"Question asked by you: {question}\n"
        f"Answer by the user (interviewee): {answer}\n"
        f"Please verify if it's a correct or wrong answer in a single line.\n"
        f"NOTE: The response should be in this format:\n"
        f"- if the answer is correct: Correct: your thoughts on why it's correct.\n"
        f"- if the answer is wrong: Wrong: your thoughts on why it's wrong."
    )
    
    try:
        # Ai Model Currently (Gemini)
        ai_response = aiModel(prompt)

        # Choose Correct/Wrong format
        if ai_response.lower().startswith("correct"):
            return jsonify({'Correct': ai_response})
        elif ai_response.lower().startswith("wrong"):
            return jsonify({'Wrong': ai_response})
        else:
            return jsonify({'error': 'Invalid response format from AI model'}), 500

    except Exception as e:
        return jsonify({'error': 'AI model failed', 'details': str(e)}), 500

# Interview Length
@app.route('/api/get-length', methods=['GET'])
def get_interview_length():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not logged in'}), 403

    table_name = f"{TABLE_PREFIX}interview_settings"

    try:
        cursor = mysql.connection.cursor()
        cursor.execute(f"SELECT length FROM {table_name} WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({'error': 'No settings found for the user'}), 404

        length = result[0]

    except Exception as e:
        return jsonify({'error': f"Failed to fetch interview length: {str(e)}"}), 500

    finally:
        cursor.close()

    return jsonify({'length': length})

# Save Interview Log/Result
@app.route('/api/save-log', methods=['POST'])
def save_log():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not logged in'}), 403

    data = request.get_json()
    questions_log = data.get('questions_log')
    if not questions_log:
        return jsonify({'error': 'Invalid request body'}), 400

    try:
        table_name = f"{TABLE_PREFIX}interviews"
        cursor = mysql.connection.cursor()

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                interview_details JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        interview_details = [{
            'question': entry['question'],
            'answer': entry['answer'],
            'grade': next((key for key in entry.get('report', {}) if key in ['Correct', 'Wrong']), None),
            'remarks': entry.get('report', {}).get('remarks', None)
        } for entry in questions_log]

        cursor.execute(
            f"""
            INSERT INTO {table_name} (user_id, interview_details) 
            VALUES (%s, %s)
            """, (user_id, json.dumps(interview_details))
        )

        mysql.connection.commit()
        
        cursor.execute("SELECT LAST_INSERT_ID()")
        interview_id = cursor.fetchone()[0]

    except Exception as e:
        return jsonify({'error': 'Failed to save log', 'details': str(e)}), 500

    finally:
        cursor.close()

    return jsonify({'success': True, 'interview_id': interview_id})

# Interview Result
@app.route('/result', methods=['GET'])
def result():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    interview_id = request.args.get('interview_id')
    if not interview_id:
        return "Interview ID is required", 400

    table_name = f"{TABLE_PREFIX}interviews"

    try:
        cursor = mysql.connection.cursor()

        cursor.execute(
            f"""
            SELECT interview_details 
            FROM {table_name} 
            WHERE user_id = %s AND id = %s
            """, 
            (user_id, interview_id)
        )
        interview_data = cursor.fetchone()

        if not interview_data:
            return "Interview not found", 404

        interview_details = json.loads(interview_data[0])
        logs = interview_details

    except Exception as e:
        return f"Failed to load progress: {str(e)}", 500

    finally:
        cursor.close()

    return render_template('panel/result.html', logs=logs)


if __name__ == '__main__':
    app.run(debug=True)