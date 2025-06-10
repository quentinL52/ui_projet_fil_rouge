structure du projet :
/data :
    /mongodb_candidats
          - cv_parsing_agents.py : class qui va appeler le crew d'agents, afin de parser le CV                                  
                                (chaque agent a pour tache d'extraire une partie precise)
                                les données sont ensuite compilé en un fichier JSON, qui est est indexé dans la collection mongoDB,
                                elle encapsule aussi des fonctions de nettoyage et de structure du fichier.
          - mongo_utils.py : class qui regroupe les differentes etapes d'interaction avec mongodb (requete par id, insertion du document)
    /cache_api_offres.py : class qui a but mission la requete api de la base des offres, afin de les stocké en cache.

/models : 
    /crew
          - agents.py : parametrage des diferents agents utiles au projet
          - crew_pool.py : les differents crew d'agents (assemblage des agents et tasks)
          - tasks.py : listes des differentes taches attribué aux agents
    /interview simulator 
          - entretient_version_prod
- config 
  gestion de l'url de connection de la base de données ainsi que les differents prompts utilisé par le modéle (simulateur)
- interview simulator 
  utilise langchain et llama 3 pour fonctionner, connection a la base de données des offres en selectionnant la premiére a ce stade 

/prompt
  contient le prompt pour le modéle 

/notebook
notebook de travail ainsi qu'un notebook des differentes block pour mage afin d'extraire les données 

/interface
  interface streamlit simpliste qui fait tourner le simulateur d'entretient

API nécéssaire pour faire tourner les modéles :
-GROQ 
-openai

données utilisé par les modéles :
l'extraction des données se fait par le biais d'un pipeline (disponible dans mes autres projets) qui utilise mage.ai pour scrapper des
des données et les stocker dans un bucket minio entre chaque etape de traitement.
les données sont ensuite stocké sur postgres, et les informations utiles sont ensuite transformé en embeddings qui sont stocké dans postgreml.
par defaut un jeux de données avec des embedding est disponible dans le repo