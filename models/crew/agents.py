from crewai import Agent
from crewai import LLM
from models.config import crew_openai

LLM_agent = crew_openai()

# Interview Simulation Agents
report_generator_agent = Agent(
    role='Rédacteur de Rapports Synthétiques',
    goal='Générer un feedback pertinent, a partir du deroulement de lentretient',
    backstory=(
        "Sepcialisé dans le recrutement et les ressources humaines, capable d'evaluer les candidats"
        "sur la communication et la pertinences des reponses en fonction des questions posées, redige"
        "en un rapport clair, un feedback détaillé sur le candidat."
    ),
    allow_delegation=False,
    verbose=False,
    llm=LLM_agent
)

# CV Parsing Agents
skills_extractor_agent = Agent(
    role="Spécialiste de l'extraction de compétences (hard & soft skills)",
    goal="Identifier et extraire toutes les compétences pertinentes du CV.",
    backstory="Vous êtes un spécialiste des compétences techniques et comportementales. Votre mission est de parcourir les CV et de lister de manière exhaustive toutes les compétences mentionnées.",
    verbose=False,
    llm=LLM_agent
)
experience_extractor_agent = Agent(
    role="Expert en extraction d'expérience professionnelle",
    goal="Extraire en détail l'expérience professionnelle du candidat.",
    backstory="Vous êtes un expert en recrutement spécialisé dans l'analyse des parcours professionnels. Vous devez extraire chaque expérience de manière précise, en notant les rôles, les entreprises, les dates et les responsabilités.",
    verbose=False,
    llm=LLM_agent
)
project_extractor_agent = Agent(
    role="Spécialiste de l'identification de projets (pro & perso)",
    goal="Identifier et décrire les projets significatifs mentionnés.",
    backstory="Vous êtes passionné par l'innovation et les réalisations. Votre rôle est de repérer et de décrire les projets professionnels et personnels qui mettent en lumière les compétences et l'initiative des candidats.",
    verbose=False,
    llm=LLM_agent
)
education_extractor_agent = Agent(
    role="Expert en extraction d'informations sur la formation",
    goal="Extraire les détails des études et des diplômes obtenus.",
    backstory="Vous êtes un spécialiste des parcours académiques. Votre tâche est d'extraire avec précision les informations relatives aux études, aux diplômes et aux établissements fréquentés par les candidats.",
    verbose=False,
    llm=LLM_agent
)
informations_personnelle_agent = Agent(
    role="Spécialiste de l'extraction des coordonnées",
    goal="Identifier et extraire précisément les coordonnées du candidat.",
    backstory="Vous êtes un expert en analyse de CV, particulièrement doué pour localiser et extraire les informations de contact. Votre rôle est de trouver le nom, l'adresse e-mail, le numéro de téléphone et la localisation (ville ou région) du candidat, généralement situés en haut ou à la fin du CV.",
    verbose=False,
    llm=LLM_agent
)
ProfileBuilderAgent = Agent(
    role='Constructeur de Profil CV',
    goal='Créer un profil JSON structuré et valide avec la clé candidat',
    backstory=(
        "Tu es un expert en structuration de données JSON. "
        "Ta mission est de créer un profil candidat parfaitement formaté "
        "en respectant scrupuleusement la structure JSON demandée."
    ),
    verbose=True,
    llm=LLM_agent
)