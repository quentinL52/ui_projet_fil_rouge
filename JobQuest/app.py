import os
import sys
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import requests
from datetime import datetime
from dotenv import load_dotenv
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import importlib.util
import tempfile
from werkzeug.utils import secure_filename

# Ajouter le répertoire actuel au path pour assurer les importations relatives
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Charger les variables d'environnement du fichier .env
load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # Génère une clé secrète aléatoire

# URL de l'API
API_BASE_URL = "https://quentinl52-data-api.hf.space/"

GMAIL_USER = os.getenv('GMAIL_USER')
GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD')

# Configuration pour l'upload de fichiers
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_job_offers():
    """Récupère les offres d'emploi depuis l'API"""
    try:
        print(f"Tentative de connexion à l'API : {API_BASE_URL}/offre-emploi")
        response = requests.get(f"{API_BASE_URL}/offre-emploi")
        print(f"Réponse de l'API : {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Données reçues : {len(data)} offres")
            return data
        else:
            print(f"Erreur API: {response.status_code}")
            print(f"Contenu de la réponse : {response.text}")
            return []
    except requests.exceptions.ConnectionError:
        print("Erreur de connexion à l'API. Vérifiez que l'API est démarrée.")
        return []
    except Exception as e:
        print(f"Erreur lors de la récupération des offres: {str(e)}")
        return []

def get_job_details(job_id):
    """Récupère les détails d'une offre d'emploi spécifique"""
    try:
        print(f"Tentative de récupération des détails pour l'offre {job_id}")
        response = requests.get(f"{API_BASE_URL}/offre-emploi/{job_id}")
        print(f"Réponse de l'API : {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Détails reçus pour l'offre {job_id}")
            return data
        else:
            print(f"Erreur API: {response.status_code}")
            print(f"Contenu de la réponse : {response.text}")
            return None
    except requests.exceptions.ConnectionError:
        print("Erreur de connexion à l'API. Vérifiez que l'API est démarrée.")
        return None
    except Exception as e:
        print(f"Erreur lors de la récupération des détails: {str(e)}")
        return None

def send_gmail(subject, body, to):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = to
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, to, msg.as_string())

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/offres')
def offres():
    try:
        jobs = get_job_offers()
        if not jobs:
            flash("Aucune offre d'emploi disponible pour le moment.", "warning")
            return render_template('index.html', jobs=[])
        # Formater la date pour chaque offre
        for job in jobs:
            if job.get('publication'):
                try:
                    date_obj = datetime.strptime(job['publication'], '%d/%m/%Y')
                    job['publication'] = date_obj.strftime('%d/%m/%Y')
                except ValueError:
                    job['publication'] = "Date non disponible"
        return render_template('index.html', jobs=jobs)
    except Exception as e:
        print(f"Erreur lors de la récupération des offres: {str(e)}")
        flash("Une erreur est survenue lors du chargement des offres d'emploi.", "error")
        return render_template('index.html', jobs=[])

@app.route('/job/<job_id>')
def job_details(job_id):
    try:
        job = get_job_details(job_id)
        if not job:
            flash(f"Offre d'emploi {job_id} introuvable.", "error")
            return redirect(url_for('offres'))

        # Formater la date si elle existe
        if job.get('publication'):
            try:
                date_obj = datetime.strptime(job['publication'], '%d/%m/%Y')
                job['publication'] = date_obj.strftime('%d/%m/%Y')
            except ValueError:
                job['publication'] = "Date non disponible"

        # Mettre en cache les données de l'offre pour le simulateur
        from data.cache_api_offres import job_offer_cache_manager
        cache_data = {
            "entreprise": job.get('entreprise', ''),
            "poste": job.get('poste', ''),
            "description": job.get('description_poste', '')
        }
        print(f"Mise en cache des données pour l'offre {job_id}: {cache_data}")  # Debug
        job_offer_cache_manager.set(job_id, cache_data)

        # Synchroniser la variable globale id_offre_emploi du simulateur
        try:
            from models.interview_simulator import essais_entretient_dev
            essais_entretient_dev.id_offre_emploi = job_id
            print(f"Synchronisation de id_offre_emploi pour le simulateur: {job_id}")
        except Exception as e:
            print(f"Erreur lors de la synchronisation de l'id_offre_emploi: {e}")

        return render_template('job_details.html', job=job)

    except Exception as e:
        print(f"Erreur lors de la récupération des détails de l'offre {job_id}: {str(e)}")
        flash("Une erreur est survenue lors du chargement des détails de l'offre.", "error")
        return redirect(url_for('offres'))

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        nom = request.form.get('nom')
        email = request.form.get('email')
        message = request.form.get('message')
        if not nom or not email or not message:
            flash('Tous les champs sont obligatoires.', 'warning')
            return render_template('contact.html')
        try:
            subject = f'Nouveau message de {nom} via le formulaire de contact'
            body = f"Nom: {nom}\nEmail: {email}\n\nMessage:\n{message}"
            send_gmail(subject, body, "quentin_loumeau@proton.me")
            flash('Votre message a bien été envoyé. Merci !', 'success')
            return redirect(url_for('contact'))
        except Exception as e:
            print(f"Erreur lors de l'envoi du mail : {e}")
            flash("Une erreur est survenue lors de l'envoi du message.", 'danger')
            return render_template('contact.html')
    return render_template('contact.html')

@app.route('/upload-cv/<job_id>', methods=['POST'])
def upload_cv(job_id):
    if 'cv' not in request.files:
        return jsonify({'error': 'Aucun fichier envoyé'}), 400
    
    file = request.files['cv']
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Créer un fichier temporaire
            temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
            file.save(temp_file.name)
            
            # Traiter le CV avec CvParserAgent
            from data.mongodb_candidats.cv_parsing_agents import CvParserAgent
            cv_agent = CvParserAgent(temp_file.name)
            json_path = cv_agent.process()
            
            # Stocker le chemin du JSON dans la session
            session['cv_json_path'] = json_path
            
            # Nettoyer l'ancien fichier JSON s'il existe
            old_json_path = session.get('old_cv_json_path')
            if old_json_path and os.path.exists(old_json_path):
                try:
                    os.unlink(old_json_path)
                except Exception as e:
                    print(f"Erreur lors de la suppression de l'ancien JSON : {e}")
            
            # Sauvegarder le chemin pour le nettoyage futur
            session['old_cv_json_path'] = json_path
            
            return jsonify({'success': True, 'message': 'CV traité avec succès'})
        except Exception as e:
            print(f"Erreur lors du traitement du CV : {e}")
            return jsonify({'error': 'Erreur lors du traitement du CV'}), 500
    
    return jsonify({'error': 'Format de fichier non autorisé'}), 400

@app.route('/simuler-entretien/<job_id>', methods=['GET', 'POST'])
def simuler_entretien(job_id):
    if request.method == 'POST':
        print(f"[DEBUG] POST reçu sur /simuler-entretien/{job_id}")
        from models.interview_simulator import essais_entretient_dev
        
        # Récupérer le chemin du JSON depuis la session
        json_path = session.get('cv_json_path')
        print(f"[DEBUG] Chemin du CV : {json_path}")
        
        if json_path:
            if os.path.exists(json_path):
                print(f"[DEBUG] CV trouvé à {json_path}")
                essais_entretient_dev.json_path = json_path
            else:
                print(f"[DEBUG] CV non trouvé à {json_path}")
                return jsonify({"response": "Le CV n'est plus disponible. Veuillez le déposer à nouveau."})
        else:
            print("[DEBUG] Aucun CV dans la session")
            return jsonify({"response": "Veuillez d'abord déposer votre CV pour commencer l'entretien."})
        
        essais_entretient_dev.id_offre_emploi = job_id
        if request.is_json:
            data = request.get_json()
            messages = data.get('messages', [])
            question_count = data.get('question_count', 0)
        else:
            user_message = request.form.get('message', 'Bonjour')
            messages = [{"role": "user", "content": user_message}]
            question_count = 0
        
        print(f"[DEBUG] Messages reçus : {messages}")
        print(f"[DEBUG] Nombre de questions : {question_count}")
        
        ai_response = essais_entretient_dev.chatbot({
            "messages": messages,
            "question_count": question_count
        }, job_id)
        
        # Récupérer le dernier message de la réponse
        last_message = ai_response["messages"][-1]["content"] if ai_response["messages"] else ""
        print(f"[DEBUG] Réponse générée : {last_message[:100]}...")
        return jsonify({"response": last_message})
    return render_template('chat.html', job_id=job_id)

# --- Gestionnaires d'erreurs ---
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    print(f"Erreur interne du serveur: {str(e)}")
    import traceback
    traceback.print_exc()
    flash("Une erreur interne est survenue. L'équipe technique a été notifiée.", "error")
    return render_template('500.html'), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Démarrage de l'application sur le port {port}")
    print(f"URL de l'API : {API_BASE_URL}")
    app.run(debug=True, host='0.0.0.0', port=port)