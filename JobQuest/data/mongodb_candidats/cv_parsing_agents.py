import os
import sys
import tempfile
import json
from langchain_community.document_loaders import PyPDFLoader
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
from models.crew.crew_pool import analyse_cv
from models.config import load_pdf

def load_profile_from_json(json_path):
    """Charge le profil candidat depuis un fichier JSON"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'candidat' in data:
                return data['candidat']
            else:
                raise ValueError("Le JSON ne contient pas la clé 'candidat'")
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier JSON : {e}")
        return None

class CvParserAgent:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        # Créer le fichier JSON dans le même répertoire que le PDF
        json_filename = os.path.splitext(os.path.basename(pdf_path))[0] + '.json'
        self.json_path = os.path.join(os.path.dirname(pdf_path), json_filename)
        self._processed_objects = set()  # Pour éviter les références circulaires

    def _serialize_object(self, obj, depth=0, max_depth=10):
        """Sérialise récursivement un objet en format JSON compatible avec une limite de profondeur"""
        if depth > max_depth:
            return str(obj)

        # Éviter les références circulaires
        obj_id = id(obj)
        if obj_id in self._processed_objects:
            return str(obj)
        self._processed_objects.add(obj_id)

        try:
            if hasattr(obj, 'raw_output'):
                return self._serialize_object(obj.raw_output, depth + 1, max_depth)
            elif hasattr(obj, '__dict__'):
                result = {}
                for k, v in obj.__dict__.items():
                    if not k.startswith('_'):  # Ignorer les attributs privés
                        result[k] = self._serialize_object(v, depth + 1, max_depth)
                return result
            elif isinstance(obj, (list, tuple)):
                return [self._serialize_object(item, depth + 1, max_depth) for item in obj]
            elif isinstance(obj, dict):
                return {k: self._serialize_object(v, depth + 1, max_depth) for k, v in obj.items()}
            else:
                return str(obj)
        except Exception as e:
            print(f"Erreur lors de la sérialisation de l'objet : {e}")
            return str(obj)

    def process(self) -> str:
        print(f"Début du traitement du CV : {self.pdf_path}")
        try:
            # Réinitialiser l'ensemble des objets traités
            self._processed_objects.clear()
            
            # Charger et analyser le CV
            cv_text_content = load_pdf(self.pdf_path)
            result = analyse_cv(cv_text_content)
            
            # Sérialiser le résultat
            json_data = self._serialize_object(result)
            
            # Sauvegarder le résultat dans le fichier JSON
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump({"candidat": json_data}, f, ensure_ascii=False, indent=2)
            
            print(f"CV traité avec succès, JSON sauvegardé dans : {self.json_path}")
            return self.json_path
        except Exception as e:
            print(f"Erreur lors du traitement du CV : {e}")
            raise

    def cleanup(self):
        """Méthode pour nettoyer les fichiers temporaires"""
        try:
            if os.path.exists(self.json_path):
                os.unlink(self.json_path)
            if os.path.exists(self.pdf_path):
                os.unlink(self.pdf_path)
        except Exception as e:
            print(f"Erreur lors du nettoyage des fichiers temporaires : {e}")

if __name__ == "__main__":
    pdf_file = r'data\CV - Quentin Loumeau.pdf'
    cv_agent = CvParserAgent(pdf_file)
    json_output_path = cv_agent.process()