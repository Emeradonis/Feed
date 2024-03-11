import tempfile
from flask import Flask, request, render_template, redirect, url_for, session
import pyrebase
import speech_recognition as sr
import gramformer
import firebase_admin
import os
import sys
from firebase_admin import credentials, storage, firestore
import requests


from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'Focus'

cred = credentials.Certificate("C:/Users/hp/PycharmProjects/flaskProject/.venv/Lib/site-packages/firebase_admin/feedies-firebase-adminsdk-ah76m-4c2761bceb.json")
firebase_admin.initialize_app(cred, {'storageBucket': 'feedies.appspot.com'})

config = {
    "apiKey": "AIzaSyB5OQR_tJh3eb-ACcAxxgxEyvty0EZy7ok",
    "authDomain": "feedies.firebaseapp.com",
    "databaseURL": "https://feedies.web.app",
    "storageBucket": "feedies.appspot.com",
}

firebase = pyrebase.initialize_app(config)
storage_client = firebase.storage()
auth = firebase.auth()
db = firebase.database()

ALLOWED_EXTENSIONS = {'wav'}


def check_logged_in():
    if 'user_id' not in session:
        return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        print(request.form)
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            user = auth.create_user_with_email_and_password(email, password)
            session['user_id'] = user['localId']
            return redirect(url_for('upload'))  # Redirect to the upload page after signing up
        except pyrebase.pyrebase.HTTPError as e:
            return render_template('signup.html', error_message='Failed to create an account. Please try again.')

    return render_template('signup.html')

@app.route('/')
def home():
    check_logged_in()
    return render_template('login.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        print(request.form)
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            user = auth.sign_in_with_email_and_password(email, password)
            session['user_id'] = user['localId']
            return redirect(url_for('upload'))
        except pyrebase.pyrebase.HTTPError as e:
            return render_template('login.html', error_message='Invalid credentials. Please try again.')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/upload')
def upload():
    check_logged_in()
    return render_template('upload.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def process_text(text):
    # Process the recognized text using gramformer
    gf = gramformer.Gramformer(models=1)
    corrected_sentences = gf.correct(text)

    corrections_output = []

    for original, corrected in zip(text, corrected_sentences):
        if corrected is None:
            corrections_output.append(f"No corrections suggested for: '{original}'")
        else:
            if original != corrected:
                edits = gf.get_edits(text, corrected)
                formatted_output = [(edit[0], edit[1]) for edit in edits]
                correction_details = []
                for tag, word in formatted_output:
                    correction_detail = ""
                    if tag == 'DET':
                        correction_detail += " - Determinants\n"
                        correction_detail += f"    - {word}\n"

                    elif tag == 'VERB:SVA':
                        correction_detail += " - One is related to Subject Verb Agreement\n"
                        correction_detail += f"    - {word}\n"
                    elif tag == 'MORPH':
                        correction_detail += " - Parts of Speech\n"
                        correction_detail += f"    - {word}\n"
                    elif tag == 'VERB:TENSE':
                        correction_detail += " - Tenses\n"
                        correction_detail += f"    - {word}\n"
                    elif tag == 'VERB:FORM':
                        correction_detail += " - Tenses\n"
                        correction_detail += f"    - {word}\n"
                    elif tag == 'SPELL':
                        correction_detail += " - Pronunciation\n"
                        correction_detail += f"    - {word}\n"
                    else:
                       pass

                    if correction_detail:
                        correction_details.append(correction_detail)

                corrections_output.append(f"The mistakes in this sentence '{text}' are:\n{''.join(correction_details)}\n{'-' * 30}")
                print(text)
                print(corrected)
            else:
                corrections_output.append(f"Cannot process this text: '{original}'")

    return "<br>".join(corrections_output)



@app.route('/upload', methods=['GET', 'POST'])
def upload_audio():
    if 'file' not in request.files:
        return "No file part"

    file = request.files['file']
    if file.filename == '':
        return "No selected file"    # Process the file here if needed
    # Upload the file to Firebase storage
    storage_ref = storage_client.child("audio_files/" + file.filename)
    storage_ref.put(file)

    # Get the download URL of the uploaded file
    download_url = storage_client.child("audio_files/" + file.filename).get_url(None)
    print(f'If ever you want to download the uploaded file, click on this link: {download_url}')

    recognizer = sr.Recognizer()

    if file and allowed_file(file.filename):
        with tempfile.NamedTemporaryFile(delete=False) as temp_audio:
            response = requests.get(download_url)
            temp_audio.write(response.content)

        with sr.AudioFile(temp_audio.name) as source:
            audio_data = recognizer.record(source)

        try:
            text = recognizer.recognize_google(audio_data)
            print(f'You said: {text}')
            corrections_output = process_text(text)
            print(corrections_output)

            return render_template('process_result.html', text=corrections_output)
        except sr.UnknownValueError:
            return "Speech recognition could not understand the audio"
        except sr.RequestError:
            return "Speech recognition service is unavailable"
    else:
        return "Invalid file format. Please upload a .wav file."



if __name__ == '__main__':
    app.run(debug=True)