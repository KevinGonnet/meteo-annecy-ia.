import os
import json
import time
import requests
import re
from bs4 import BeautifulSoup
import google.generativeai as genai

# 1. INITIALISATION STRICTE DE L'IA
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# LA MASTERCLASS : On force l'API Gemini à parler nativement en JSON (Zéro risque de plantage)
generation_config = {"response_mime_type": "application/json"}
model = genai.GenerativeModel('gemini-2.5-pro', generation_config=generation_config)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
DB_FILE = "data.json"

def charger_memoire():
    """Lit le JSON généré la veille pour s'en souvenir."""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                pass
    return None

def trouver_dernier_topic(url_section, mots_cles):
    """
    Le 'Crawler' : Il va sur la page d'accueil de la section et lit les titres de haut en bas.
    Dès qu'il trouve un titre avec les mots clés (ex: 'centre-est', 'juillet'), il s'arrête.
    Puisque les forums classent du plus récent au plus ancien, il attrape toujours le bon topic !
    """
    print(f"Recherche dynamique sur {url_section}...")
    resp = requests.get(url_section, headers=HEADERS)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    liens = soup.find_all('a', href=re.compile(r'/f/topic/'))
    for lien in liens:
        titre = lien.text.lower()
        if all(mot.lower() in titre for mot in mots_cles):
            print(f"✅ Cible verrouillée : {titre.strip()}")
            return lien['href'].split('?')[0] # Enlève la pagination s'il y en a une dans le lien
    return None

def scraper_dernieres_pages(base_url, nb_pages_max=3):
    """
    L'Aspirateur Chirurgical : Pourquoi ne pas lire les 9 pages ? 
    Parce que dans un forum météo, ce qui a été dit il y a 5 jours est déjà obsolète.
    On cible uniquement les 2 ou 3 dernières pages, là où se trouve le VRAI consensus du jour.
    """
    resp = requests.get(base_url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    liens_pages = soup.find_all('a', href=re.compile(r'page=\d+'))
    max_page = 1
    for lien in liens_pages:
        match = re.search(r'page=(\d+)', lien['href'])
        if match:
            max_page = max(max_page, int(match.group(1)))
            
    start_page = max(1, max_page - nb_pages_max + 1)
    contenu_complet = ""
    
    for page in range(start_page, max_page + 1):
        url_page = base_url if page == 1 else f"{base_url}?page={page}"
        p_resp = requests.get(url_page, headers=HEADERS)
        p_soup = BeautifulSoup(p_resp.text, 'html.parser')
        
        # On extrait uniquement le texte des posts pour économiser des "tokens" d'IA
        posts = p_soup.find_all('div', attrs={'data-role': 'commentContent'})
        for post in posts:
            contenu_complet += post.text + "\n---\n"
        time.sleep(1) # Règle d'or du scraping : on respire entre deux pages
        
    return contenu_complet

def interroger_gemini(prompt_systeme, structure_attendue, contexte):
    """Envoie la requête avec le schéma JSON attendu."""
    prompt_complet = f"""
    {prompt_systeme}
    
    Tu DOIS impérativement utiliser cette structure JSON :
    {structure_attendue}
    
    Voici les pages du forum à analyser :
    {contexte}
    """
    response = model.generate_content(prompt_complet)
    return json.loads(response.text)

def main():
    memoire = charger_memoire()
    data_finale = {"mise_a_jour": time.strftime("%Y-%m-%d %H:%M")}
    
    # --- BLOC 1 : LE DIRECT (OBSERVATIONS) ---
    url_obs = trouver_dernier_topic("https://forums.infoclimat.fr/f/forum/15-le-temps-en-france/", ["suivi", "centre-est"])
    if url_obs:
        txt_obs = scraper_dernieres_pages(url_obs)
        prompt_obs = "Tu es météorologue. Résume les observations actuelles et le ressenti de la chaleur autour d'Annecy à partir du forum."
        schema_obs = '{"titre": "string", "temperature_actuelle_et_ressenti": "string", "indice_epuisement_sur_10": int, "nuit_tropicale": "string"}'
        data_finale["observations"] = interroger_gemini(prompt_obs, schema_obs, txt_obs)

    # --- BLOC 2 : COURT TERME (AVEC GESTION DE LA MÉMOIRE) ---
    url_j5 = trouver_dernier_topic("https://forums.infoclimat.fr/f/forum/13-prévisions-à-court-et-moyen-terme/", ["centre-est"])
    if url_j5:
        txt_j5 = scraper_dernieres_pages(url_j5)
        
        # Injection du Delta Analysis (La mémoire)
        rappel = memoire.get('previsions_j5', {}).get('resume', '') if memoire else ''
        contexte_memoire = f"Hier, ton résumé était : '{rappel}'. Si les modèles ont changé d'avis aujourd'hui, explique-le dans le champ 'changement_depuis_hier'."
        
        prompt_j5 = f"Analyse ces prévisions J+5. {contexte_memoire}"
        schema_j5 = '{"resume": "string", "changement_depuis_hier": "string", "date_fin_canicule_estimee": "string", "fiabilite_pourcentage": int}'
        data_finale["previsions_j5"] = interroger_gemini(prompt_j5, schema_j5, txt_j5)

    # --- BLOC 3 : LONG TERME ---
    url_lt = trouver_dernier_topic("https://forums.infoclimat.fr/f/forum/14-evolution-à-plus-long-terme/", ["prévisions"])
    if url_lt:
        txt_lt = scraper_dernieres_pages(url_lt, nb_pages_max=2)
        prompt_lt = "Analyse la tendance macro à plus de 7 jours. Cherche les signaux de changement de masse d'air."
        schema_lt = '{"tendance_generale": "string", "espoir_changement": "string"}'
        data_finale["tendances_longues"] = interroger_gemini(prompt_lt, schema_lt, txt_lt)

    # SAUVEGARDE EN LOCAL POUR GITHUB ACTIONS
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data_finale, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
  
