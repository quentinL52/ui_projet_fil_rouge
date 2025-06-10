import os
from dotenv import load_dotenv
load_dotenv()
from langchain_groq import ChatGroq
from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict, List, Any, Tuple, Optional, Type
#########################################################################################################
# formatage du json
def format_cv(document):
    def format_section(title, data, indent=0):
        prefix = "  " * indent
        lines = [f"{title}:"]
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"{prefix}- {k.capitalize()}:")
                    lines.extend(format_section("", v, indent + 1))
                else:
                    lines.append(f"{prefix}- {k.capitalize()}: {v}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                lines.append(f"{prefix}- Élément {i + 1}:")
                lines.extend(format_section("", item, indent + 1))
        else:
            lines.append(f"{prefix}- {data}")
        return lines
    sections = []
    for section_name, content in document.items():
        title = section_name.replace("_", " ").capitalize()
        sections.extend(format_section(title, content))
        sections.append("") 
    return "\n".join(sections)


def read_system_prompt(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def load_pdf(pdf_path):
    loader = PyPDFLoader(pdf_path)
    pages = loader.load_and_split()
    cv_text = ""
    for page in pages:
        cv_text += page.page_content + "\n\n"
    return cv_text    
#########################################################################################################        
# modéles 
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
model_groq = "llama-3.1-8b-instant" #"llama-3.3-70b-versatile"
def chat_groq() :
  llm = ChatGroq(model=model_groq) 
  return llm

GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
def chat_gemini():
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=GEMINI_API_KEY,
            temperature=0.7,
            max_output_tokens=1000
        )
        return llm
    except Exception as e:
        print(f"[DEBUG] Erreur lors de l'initialisation de Gemini : {e}")
        # Fallback sur Groq si Gemini n'est pas disponible
        return chat_groq()

      
        

