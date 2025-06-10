from dotenv import load_dotenv
import sys
import os
import json
import requests
from datetime import datetime, timedelta
load_dotenv()
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
#############################################################

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from models.crew.crew_pool import interview_analyser
from models.config import read_system_prompt, chat_gemini, format_cv, chat_groq
from data.mongodb_candidats.cv_parsing_agents import load_profile_from_json
from data.cache_api_offres import job_offer_cache_manager, load_job_offer_from_api

# Configuration du modèle
try:
    print("[DEBUG] Tentative d'initialisation du modèle Gemini")
    llm = chat_groq()
    print("[DEBUG] Modèle Gemini initialisé avec succès")
except Exception as e:
    print(f"[DEBUG] Erreur lors de l'initialisation du modèle : {e}")

# Chargement du prompt
try:
    file_path = os.path.join(project_root, 'prompts', 'rag_prompt.txt')
    print(f"[DEBUG] Tentative de chargement du prompt depuis {file_path}")
    prompt_rh = read_system_prompt(file_path)
    print("[DEBUG] Prompt chargé avec succès")
except Exception as e:
    print(f"[DEBUG] Erreur lors du chargement du prompt : {e}")
    # Prompt par défaut si le fichier n'est pas trouvé
    prompt_rh = """Vous êtes un recruteur professionnel qui mène un entretien d'embauche.
    Poste : {poste}
    Entreprise : {entreprise}
    Description : {description}
    
    CV du candidat :
    {cv}
    
    Posez {questions} questions pertinentes pour évaluer les compétences et l'expérience du candidat.
    Adaptez vos questions en fonction du CV et du poste.
    Soyez professionnel mais amical."""
    print("[DEBUG] Utilisation du prompt par défaut")

nombre_de_questions = 2

# Variables globales
json_path = None
document_candidat = None
cv = None
id_offre_emploi = None

# URL de l'API locale
api = "http://localhost:8010/offre-emploi/"

def load_job_offer_from_api(api_url, job_id):
    """Charge les détails d'une offre d'emploi depuis l'API"""
    try:
        print(f"[DEBUG] Tentative de chargement de l'offre {job_id} depuis {api_url}")
        response = requests.get(f"{api_url}{job_id}")
        if response.status_code == 200:
            data = response.json()
            print(f"[DEBUG] Données reçues : {data}")
            return (
                data.get('entreprise', ''),
                data.get('poste', ''),
                data.get('description_poste', '')
            )
        else:
            print(f"[DEBUG] Erreur API : {response.status_code}")
            return None, None, None
    except Exception as e:
        print(f"[DEBUG] Erreur lors du chargement de l'offre : {e}")
        return None, None, None

class State(TypedDict):
    messages: Annotated[list, add_messages]
    question_count: int

def get_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", prompt_rh.format(
            entreprise=None,
            poste=None,
            description=None,
            cv=cv if cv else "",
            questions=nombre_de_questions
        )),
        MessagesPlaceholder(variable_name="messages"),
        ("human", "{input}")
    ])

def chatbot(state: State, id_offre_emploi) -> State:
    global cv, document_candidat
    
    # Mettre à jour le CV si le json_path a changé
    if json_path:
        try:
            document_candidat = load_profile_from_json(json_path)
            if document_candidat:
                cv = format_cv(document_candidat)
                print(f"[DEBUG] CV chargé avec succès : {cv[:100]}...")
        except Exception as e:
            print(f"[DEBUG] Erreur lors du chargement du CV : {e}")
    
    messages = state["messages"]
    question_count = state.get("question_count", 0)
    
    # Essayer d'abord de récupérer depuis le cache
    cached_data = job_offer_cache_manager.get(id_offre_emploi)
    if cached_data:
        print(f"[DEBUG] Données récupérées du cache : {cached_data}")
        entreprise = cached_data.get("entreprise")
        poste = cached_data.get("poste")
        description = cached_data.get("description")
    else:
        # Si pas en cache, récupérer depuis l'API
        print(f"[DEBUG] Tentative de récupération depuis l'API pour l'offre {id_offre_emploi}")
        entreprise, poste, description = load_job_offer_from_api(api, id_offre_emploi)
        if entreprise and poste and description:
            # Mettre en cache les données
            cache_data = {
                "entreprise": entreprise,
                "poste": poste,
                "description": description
            }
            job_offer_cache_manager.set(id_offre_emploi, cache_data)
            print(f"[DEBUG] Données mises en cache : {cache_data}")
    
    if not cv:
        print("[DEBUG] CV non disponible")
        return {
            "messages": messages + [{"role": "assistant", "content": "Veuillez d'abord déposer votre CV pour commencer l'entretien."}],
            "question_count": question_count + 1,
            "next": "end"
        }
    
    if entreprise and poste and description:
        try:
            # Créer le prompt avec les données de l'offre
            system_message = prompt_rh.format(
                entreprise=entreprise,
                poste=poste,
                description=description,
                cv=cv,
                questions=nombre_de_questions
            )
            print(f"[DEBUG] Prompt système créé avec succès")
            
            # Convertir les messages en format AIMessage/HumanMessage
            formatted_messages = []
            for msg in messages:
                if msg["role"] == "user":
                    formatted_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    formatted_messages.append(AIMessage(content=msg["content"]))
            
            # Ajouter le message système au début
            formatted_messages.insert(0, AIMessage(content=system_message))
            
            # Obtenir la réponse du modèle
            response = llm.invoke(formatted_messages)
            print(f"[DEBUG] Réponse du modèle générée avec succès")
            
            # Convertir la réponse en format dictionnaire
            return {
                "messages": messages + [{"role": "assistant", "content": response.content}],
                "question_count": question_count + 1,
                "next": "continue"
            }
        except Exception as e:
            print(f"[DEBUG] Erreur lors du formatage des messages : {e}")
            return {
                "messages": messages + [{"role": "assistant", "content": "Désolé, une erreur est survenue lors de la génération de la réponse."}],
                "question_count": question_count + 1,
                "next": "end"
            }
    else:
        print(f"[DEBUG] Données de l'offre manquantes : entreprise={entreprise}, poste={poste}, description={description}")
        return {
            "messages": messages + [{"role": "assistant", "content": "Désolé, je n'ai pas pu récupérer les détails de l'offre d'emploi. L'entretien ne peut pas continuer."}],
            "question_count": question_count + 1,
            "next": "end"
        }

def should_end_chat(state: State) -> bool:
    return state.get("next", "continue") == "end"

def add_messages(messages: list) -> list:
    return messages

def run_crew_ai_node(state):
    chat_history = state["messages"]
    result = interview_analyser(chat_history)
    return {}

def create_graph(id_offre_emploi):
    graph_builder = StateGraph(State)
    graph_builder.add_node("chatbot", lambda state: chatbot(state, id_offre_emploi))
    graph_builder.add_node("run_crew_ai", run_crew_ai_node)
    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_conditional_edges(
        "chatbot",
        should_end_chat,
        {
            True: "run_crew_ai",
            False: END,
        }
    )
    graph_builder.add_edge("run_crew_ai", END)
    return graph_builder.compile(checkpointer=MemorySaver())

def stream_graph_updates(user_input, id_offre_emploi):
    config = {"configurable": {"thread_id": 1}}
    graph = create_graph(id_offre_emploi)
    events = graph.stream(
        {"messages": [{"role": "user", "content": user_input}]},
        config,
        stream_mode="values",
    )
    for event in events:
        if "messages" in event and event["messages"]:
            message = event["messages"][-1]
            if isinstance(message, AIMessage):
                print(f"Assistant: {message.content}")

if __name__ == "__main__":
    id_offre_emploi = input("Entrez l'ID de l'offre d'emploi : ")
    config = {"configurable": {"thread_id": 1}}
    graph = create_graph(id_offre_emploi)
    initial_input = "Bonjour"
    events = graph.stream(
        {"messages": [{"role": "user", "content": initial_input}]},
        config,
        stream_mode="values",
    )
    for event in events:
        if "messages" in event and event["messages"]:
            message = event["messages"][-1]
            if isinstance(message, AIMessage):
                print(f"Assistant: {message.content}")
    while True:
        try:
            user_input = input("Vous : ")
            if user_input.lower() in ["au revoir", "a bientot"]:
                print("Assistant : Au revoir !")
                break
            stream_graph_updates(user_input, id_offre_emploi)
        except KeyboardInterrupt:
            print("\nAssistant : À bientôt !")
            break