import os
import sys
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, g
import requests
from datetime import datetime
from dotenv import load_dotenv
import secrets
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth
import json
from functools import wraps
from data.mongodb_candidats.mongo_utils import MongoManager
from flask_sqlalchemy import SQLAlchemy
from data.mongodb_candidats.cv_parsing_agents import CvParserAgent

import subprocess
import requests
from models.interview_simulator.essais_entretient_dev import InterviewProcessor
from data.mongodb_candidats.mongo_utils import MongoManager
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))
app.config.update(
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False  
)
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(30), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=True)
    picture_url = db.Column(db.String(255), nullable=True)
    candidate_mongo_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.email}>'


oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:  
            flash("Veuillez vous connecter pour accéder à cette page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = User.query.get(user_id)

@app.context_processor
def inject_user():
    return dict(user=g.user)  

@app.route('/login')
def login():
    redirect_uri = url_for('authorized', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/logout')
def logout():
    session.clear()  
    flash("Vous avez été déconnecté.", "success")
    return redirect(url_for('landing'))

@app.route('/login/authorized')
def authorized():
    token = oauth.google.authorize_access_token()
    if not token:
        flash("Accès refusé par Google.", "danger")
        return redirect(url_for('landing'))

    user_info = token.get('userinfo')
    if not user_info:
        user_info = oauth.google.get('https://www.googleapis.com/oauth2/v1/userinfo').json()

    google_id = user_info['sub']  
    user = User.query.filter_by(google_id=google_id).first()

    if user is None:
        user = User(
            google_id=google_id,
            email=user_info['email'],
            name=user_info['name'],
            picture_url=user_info.get('picture')
        )
        db.session.add(user)
        db.session.commit()
        flash(f"Bienvenue, {user.name} ! Votre compte a été créé.", "success")
    else:
        user.name = user_info['name']
        user.picture_url = user_info.get('picture')
        db.session.commit()
        flash(f"Heureux de vous revoir, {user.name} !", "info")
    session.clear()
    session['user_id'] = user.id
    return redirect(url_for('home'))



@app.route('/')
def landing():
    if g.user: 
        return redirect(url_for('home'))
    return render_template('landing.html')

@app.route('/home')
@login_required
def home():
    return render_template('home.html')

@app.route('/resume')
@login_required
def resume():
    if not g.user.candidate_mongo_id:
        return render_template('resume.html', cv_data=None)
    
    try:
        mongo_manager = MongoManager()
        cv_data_full = mongo_manager.get_profile_by_id(g.user.candidate_mongo_id)
        mongo_manager.close_connection()
        
        if not cv_data_full:
            flash("Aucun CV n'a été trouvé pour votre profil.", "warning")
            return render_template('resume.html', cv_data=None)
            
        if 'candidat' not in cv_data_full or not isinstance(cv_data_full['candidat'], dict):
            flash("Les données du CV sont dans un format incorrect.", "danger")
            return render_template('resume.html', cv_data=None)
            
        cv_profile = cv_data_full['candidat']
        if not cv_profile:
            flash("Les données du CV sont vides.", "warning")
            return render_template('resume.html', cv_data=None)
            
        return render_template('resume.html', cv_data=cv_profile)

    except Exception as e:
        print(f"Une erreur inattendue est survenue dans la route /resume: {str(e)}")
        flash("Une erreur est survenue lors de la récupération de votre CV.", "danger")
        return render_template('resume.html', cv_data=None)


@app.route('/upload-resume', methods=['POST'])
@login_required
def upload_resume():
    if 'resume' not in request.files:
        return jsonify({'error': 'Aucun fichier envoyé'}), 400

    file = request.files['resume']
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        user_email_safe = g.user.email.replace('@', '_').replace('.', '_')
        unique_filename = f"{user_email_safe}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        try:
            file.save(filepath)
            print(f"Fichier CV sauvegardé sur : {filepath}")

            print("Lancement du CvParserAgent pour le traitement...")
            cv_agent = CvParserAgent(pdf_path=filepath)
            candidate_mongo_id = cv_agent.process()

            if candidate_mongo_id:
                g.user.candidate_mongo_id = str(candidate_mongo_id)
                db.session.commit()
                flash('CV téléchargé et lié à votre profil avec succès !', 'success')
                return jsonify({'success': True, 'message': 'CV traité et lié au profil'})
            else:
                flash("Une erreur est survenue lors de l'analyse de votre CV.", 'danger')
                return jsonify({'error': "Le traitement du CV a échoué."}), 500

        except Exception as e:
            print(f"Erreur critique lors du traitement du CV : {e}")
            flash('Une erreur serveur est survenue.', 'danger')
            return jsonify({'error': f'Une erreur serveur est survenue : {e}'}), 500
            
    return jsonify({'error': 'Format de fichier non autorisé. Veuillez utiliser un PDF.'}), 400


@app.route('/jobs')
@login_required
def jobs():
    try:
        response = requests.get('https://quentinl52-data-api.hf.space/offre-emploi/')
        if response.status_code == 200:
            jobs_data = response.json()
            return render_template('jobs.html', jobs=jobs_data)
        else:
            flash("Erreur lors de la récupération des offres d'emploi.", "danger")
            return render_template('jobs.html', jobs=[])
    except Exception as e:
        print(f"Erreur lors de la récupération des offres d'emploi : {str(e)}")
        flash("Une erreur est survenue lors de la récupération des offres d'emploi.", "danger")
        return render_template('jobs.html', jobs=[])

@app.route('/interview-ai', methods=['GET', 'POST'])
@login_required
def interview_ai():
    if request.method == 'POST':
        try:
            data = request.get_json()
            messages = data.get('messages', [])
            job_id = data.get('job_id')
            if not job_id:
                return jsonify({'error': 'job_id manquant.'}), 400
        except:
            return jsonify({'error': 'Requête JSON invalide.'}), 400

        try:
            mongo_manager = MongoManager()
            cv_document = mongo_manager.get_profile_by_id(g.user.candidate_mongo_id)
            mongo_manager.close_connection()

            response = requests.get('https://quentinl52-data-api.hf.space/offre-emploi/')
            response.raise_for_status()
            jobs = response.json()
            job_offer = next((job for job in jobs if job.get('id') == job_id), None)
            
            if not cv_document or not job_offer:
                return jsonify({'error': 'CV ou offre d\'emploi introuvable.'}), 404
        except Exception as e:
            return jsonify({'error': f'Erreur de chargement des données: {e}'}), 500

        try:
            # On utilise un thread_id unique par utilisateur pour la mémoire du graph
            interview_processor = InterviewProcessor(cv_document, job_offer)
            response_state = interview_processor.run(messages)
            last_message_obj = response_state["messages"][-1]
            return jsonify({"response": last_message_obj.content})
        except Exception as e:
            print(f"Erreur lors de l'exécution de l'entretien: {e}")
            return jsonify({'error': "Une erreur s'est produite lors du traitement de votre message."}), 500


    job_id = request.args.get('job_id')
    if not job_id:
        flash("Aucun ID d'offre d'emploi spécifié.", "danger")
        return redirect(url_for('jobs')) 
    job_info = None
    cv_info = None
    

    try:
        response = requests.get('https://quentinl52-data-api.hf.space/offre-emploi/')
        response.raise_for_status() 
        jobs = response.json()
        job_info = next((job for job in jobs if job.get('id') == job_id), None)
        if not job_info:
            flash(f"L'offre d'emploi avec l'ID {job_id} est introuvable.", "warning")
            return redirect(url_for('jobs'))
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération des offres : {e}")
        flash("Erreur de communication avec le service des offres d'emploi.", "danger")
        return redirect(url_for('jobs'))
    if g.user and g.user.candidate_mongo_id:
        try:
            mongo_manager = MongoManager()
            full_cv = mongo_manager.get_profile_by_id(g.user.candidate_mongo_id)
            cv_info = full_cv.get('candidat') if full_cv else None
            mongo_manager.close_connection()
        except Exception as e:
            print(f"Erreur lors de la récupération du CV : {e}")
            flash("Erreur lors de la récupération de votre CV.", "danger")    
    if not cv_info:
        flash("Votre profil CV n'a pas pu être chargé. Veuillez vérifier votre profil.", "warning")
        return redirect(url_for('resume')) 
    return render_template('interview_ai.html', job_info=job_info, cv_info=cv_info, job_id=job_id)

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash("Merci pour votre message !", "success")
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# waitress-serve --host=127.0.0.1 --port=5000 app:app 
"""
if __name__ == '__main__':
    with app.app_context():
        db.create_all() 
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)"""
