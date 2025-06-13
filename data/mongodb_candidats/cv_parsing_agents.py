import os
import sys
import json

# uuid et pathlib ne sont plus nécessaires
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from models.crew.crew_pool import analyse_cv
from models.config import load_pdf
from data.mongodb_candidats.mongo_utils import MongoManager

class CvParserAgent:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.manager = MongoManager()

    def process(self, old_mongo_id=None) -> str:
        """
        Traite un CV, extrait le JSON, le nettoie, et l'enregistre sur MongoDB.
        """
        print(f"Début du traitement du CV : {self.pdf_path}")
        
        if old_mongo_id:
            print(f"Suppression de l'ancien profil avec l'ID : {old_mongo_id}")
            self.manager.delete_profile_by_id(old_mongo_id)
        
        try:
            cv_text_content = load_pdf(self.pdf_path)
            crew_output = analyse_cv(cv_text_content)

            if not crew_output or not hasattr(crew_output, 'raw') or not crew_output.raw.strip():
                print("Erreur : L'analyse par le crew n'a pas retourné de résultat ou le résultat est vide.")
                return None
            
            # --- ÉTAPE DE NETTOYAGE ---
            # On retire les blocs de code Markdown (```json ... ```)
            raw_string = crew_output.raw
            if '```' in raw_string:
                # Trouve le premier '{' et le dernier '}' pour extraire le JSON pur
                start_index = raw_string.find('{')
                end_index = raw_string.rfind('}')
                if start_index != -1 and end_index != -1:
                    json_string_cleaned = raw_string[start_index : end_index + 1]
                else:
                    print(f"Erreur: Impossible d'extraire le JSON des données brutes:\n{raw_string}")
                    return None
            else:
                # Si pas de bloc Markdown, on utilise la chaîne telle quelle
                json_string_cleaned = raw_string

            # Parser le JSON nettoyé en dictionnaire Python
            try:
                profile_data = json.loads(json_string_cleaned)
            except json.JSONDecodeError as e:
                print(f"Erreur lors du parsing du JSON nettoyé : {e}")
                print(f"Données après nettoyage : {json_string_cleaned}")
                return None

            # Insérer directement les données dans MongoDB
            inserted_id = self.manager.save_profile(profile_data)
            
            if inserted_id:
                print(f"Profil inséré avec succès dans MongoDB. ID : {inserted_id}")
                return str(inserted_id)
            else:
                print("Échec de l'insertion dans MongoDB.")
                return None

        except Exception as e:
            print(f"Une erreur inattendue est survenue durant le processus : {e}")
            return None

# --- Exemple d'utilisation ---
if __name__ == "__main__":
    pdf_file_path = os.path.join('data', 'CV - Quentin Loumeau.pdf')
    agent = CvParserAgent(pdf_file_path)
    
    print("--- Lancement du traitement ---")
    new_id = agent.process()
    if new_id:
        print(f"Opération terminée avec succès. ID MongoDB : {new_id}")