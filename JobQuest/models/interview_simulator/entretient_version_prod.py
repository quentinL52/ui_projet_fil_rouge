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

from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from models.crew.crew_pool import interview_analyser
from models.config import read_system_prompt, chat_gemini, format_cv


llm = chat_gemini()

file_path = r'prompts\rag_prompt.txt'
prompt_rh = read_system_prompt(file_path)

nombre_de_questions = 1

#############################################################
# Lecture du profil depuis le fichier JSON temporaire
def load_profile_from_json(json_path):
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

# Chemin du fichier JSON temporaire (à remplacer par le chemin réel)
json_path = "data/cv_profile.json"
document_candidat = load_profile_from_json(json_path)
cv = format_cv(document_candidat)

#############################################################
# offre d'emploi
from data.cache_api_offres import job_offer_cache_manager, load_job_offer_from_api 
api = "https://data-api-484784520438.europe-west1.run.app/offre-emploi/" 
id_offre_emploi = "61d2b892-867b-41f5-b69a-592d90cd51ac"

#############################################################

class State(TypedDict):
    messages: Annotated[list, add_messages]
    question_count: int

prompt = ChatPromptTemplate.from_messages([
    ("system", prompt_rh.format(
        entreprise=None,
        poste=None,
        description=None,
        cv=cv,
        questions=nombre_de_questions
    )),
    MessagesPlaceholder(variable_name="messages"),
    ("human", "{input}")
])

def chatbot(state: State) -> State:
    messages = state["messages"]
    question_count = state.get("question_count", 0)
    entreprise, poste, description = load_job_offer_from_api(api,id_offre_emploi)
    if entreprise and poste and description:
        formatted_prompt = prompt.format_messages(
            messages=messages,
            input=messages[-1].content if messages else "Bonjour"
        )
        formatted_prompt[0] = AIMessage(content=prompt_rh.format(
            entreprise=entreprise,
            poste=poste,
            description=description,
            cv=cv,
            questions=nombre_de_questions
        ))
        response = llm.invoke(formatted_prompt)
        return {"messages": messages + [response], "question_count": question_count + 1, "next": "continue"}
    else:
        response = AIMessage(content="Désolé, je n'ai pas pu récupérer les détails de l'offre d'emploi. L'entretien ne peut pas continuer.")
        return {"messages": messages + [response], "question_count": question_count + 1, "next": "end"}

def should_end_chat(state: State):
    messages = state.get("messages", [])
    if not messages:
        return False
    for msg in reversed(messages):
        role = None
        content = ""
        if isinstance(msg, dict):
            msg_type = msg.get("type", "")
            if msg_type == 'ai':
                role = 'assistant'
            content = msg.get("content", "").lower()
        elif isinstance(msg, AIMessage):
            role = 'assistant'
            content = msg.content.lower()
        if role == 'assistant':
            contains_keyword = "nous allons maintenant passer a l'analyse" in content
            return contains_keyword
    return False

def run_crew_ai_node(state):
    chat_history = state["messages"]
    result = interview_analyser(chat_history)
    return {}

graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
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

config = {"configurable": {"thread_id": 1}}
graph = graph_builder.compile(checkpointer=MemorySaver())

def stream_graph_updates(user_input):
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
            stream_graph_updates(user_input)
        except KeyboardInterrupt:
            print("\nAssistant : À bientôt !")
            break