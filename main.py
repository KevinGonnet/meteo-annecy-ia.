import os
import json
import time
import requests
import re
from bs4 import BeautifulSoup
import google.generativeai as genai

# --- CONFIGURATION GITHUB ACTIONS ---
cle_api = os.environ.get("GEMINI_API_KEY")
if not cle_api:
    print("❌ ERREUR : La clé API est introuvable. Vérifie tes secrets GitHub.")
    exit(1)

genai.configure(api_key=cle_api)

# Définition du modèle Flash
model = genai.GenerativeModel('gemini-3.5-flash', generation_config={"response_mime_type": "application/json"})
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
DB_FILE = "data.json"

def scraper_dernieres_pages(base_url, nb_pages_max=2):
    nom_propre = base_url.split('/')[-2]
    print(f"\n📥 Aspiration de : {nom_propre}")
    resp = requests.get(base_url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    max_page = 1
    for lien in soup.find_all('a'):
        href = lien.get('href', '')
        if 'page=' in href:
            try:
                num = int(re.search(r'page=(\d+)', href).group(1))
                max_page = max(max_page, num)
            except: pass
            
    start_page = max(1, max_page - nb_pages_max + 1)
    contenu = ""
    
    for page in range(start_page, max_page + 1):
        url = base_url if page == 1 else f"{base_url}?page={page}"
        p_resp = requests.get(url, headers=HEADERS)
        p_soup = BeautifulSoup(p_resp.text, 'html.parser')
        
        posts = p_soup.find_all('div', attrs={'data-role': 'commentContent'})
        for post in posts:
            contenu += post.text.strip() + "\n---\n"
        print(f"  -> Page {page}/{max_page} lue ({len(posts)} messages extraits)")
        time.sleep(1)
        
    return contenu

def interroger_gemini(prompt_systeme, schema, contexte):
    print("🧠 Analyse Gemini en cours...")
    prompt = f"{prompt_systeme}\n\nTu DOIS respecter ce format JSON :\n{schema}\n\nContexte brut du forum:\n{contexte[:15000]}"
    try:
        response = model.generate_content(prompt)
        
        # L'ASTUCE ANTI-BUG : On construit les backticks mathématiquement pour ne pas casser l'éditeur GitHub
        balise_json = '`' * 3 + 'json'
        balise_fin = '`' * 3
        texte_propre = response.text.replace(balise_json, '').replace(balise_fin, '').strip()
        
        return json.loads(texte_propre)
    except Exception as e:
        print(f"⚠️ Erreur lors de l'analyse IA : {e}")
        return None

def main():
    data_finale = {"mise_a_jour": time.strftime("%Y-%m-%d %H:%M")}
    
    print("🚀 DÉMARRAGE DU SCRIPT MVP (VERSION GITHUB)...")
    
    url_obs = "https://forums.infoclimat.fr/f/topic/61175-suivi-du-temps-dans-le-centre-est-juillet-2026/"
    url_j5  = "https://forums.infoclimat.fr/f/topic/61192-pr%C3%A9visions-centre-est-2026/"
    url_lt  = "https://forums.infoclimat.fr/f/topic/61198-du-13-au-19-juillet-2026-pr%C3%A9visions-m%C3%A9t%C3%A9o-semaine-29/"

    txt_obs = scraper_dernieres_pages(url_obs)
    prompt1 = "Tu es météorologue. Fais un point de situation concret sur la chaleur actuelle autour d'Annecy et du Centre-Est à partir des relevés des membres."
    schema1 = '{"titre": "string", "temperature_actuelle_et_ressenti": "string", "indice_epuisement_sur_10": int, "nuit_tropicale": "string"}'
    data_finale["observations"] = interroger_gemini(prompt1, schema1, txt_obs)

    txt_j5 = scraper_dernieres_pages(url_j5)
    prompt2 = "Analyse les prévisions météo à court terme. Y a-t-il un consensus des experts ou une incertitude sur la fin de la canicule ?"
    schema2 = '{"resume": "string", "changement_depuis_hier": "string", "date_fin_canicule_estimee": "string", "fiabilite_pourcentage": int}'
    data_finale["previsions_j5"] = interroger_gemini(prompt2, schema2, txt_j5)

    txt_lt = scraper_dernieres_pages(url_lt)
    prompt3 = "Analyse la tendance macro à plus de 7 jours. Y a-t-il un signal macro de fin de blocage anticyclonique ou de changement de masse d'air ?"
    schema3 = '{"tendance_generale": "string", "espoir_changement": "string"}'
    data_finale["tendances_longues"] = interroger_gemini(prompt3, schema3, txt_lt)

    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data_finale, f, ensure_ascii=False, indent=4)
        
    print("\n✅ DATA.JSON GÉNÉRÉ AVEC SUCCÈS ! LE SITE WEB VA POUVOIR S'AFFICHER.")

if __name__ == "__main__":
    main()
    
