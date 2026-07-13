import os
import json
import time
import requests
import re
from bs4 import BeautifulSoup
import google.generativeai as genai

# --- CONFIGURATION GITHUB ACTIONS ---
# Le script va chercher la clé cachée dans les "Secrets" de ton dépôt GitHub
cle_api = os.environ.get("GEMINI_API_KEY")
if not cle_api:
    print("❌ ERREUR : La clé API est introuvable. Vérifie tes secrets GitHub.")
    exit(1)

genai.configure(api_key=cle_api)

# Définition du modèle Flash (rapide, gratuit, parfait pour le JSON)
model = genai.GenerativeModel('gemini-3.5-flash', generation_config={"response_mime_type": "application/json"})
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
DB_FILE = "data.json"

def scraper_dernieres_pages(base_url, nb_pages_max=2):
    nom_propre = base_url.split('/')[-2]
    print(f"\n📥 Aspiration de : {nom_propre}")
    resp = requests.get(base_url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Trouver le nombre de pages
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
    
    # Aspiration des dernières pages
    for page in range(start_page, max_page + 1):
        url = base_url if page == 1 else f"{base_url}?page={page}"
        p_resp = requests.get(url, headers=HEADERS)
        p_soup = BeautifulSoup(p_resp.text, 'html.parser')
        
        posts = p_soup.find_all('div', attrs={'data-role': 'commentContent'})
        for post in posts:
            contenu += post.text.strip() + "\n---\n"
        print(f"  -> Page {page}/{max_page} lue ({len(posts)} messages extraits)")
        time.sleep(1) # Pause polie pour le serveur
        
    return contenu

def interroger_gemini(prompt_systeme, schema, contexte):
    print("🧠 Analyse Gemini en cours...")
    prompt = f"{prompt_systeme}\n\nTu DOIS respecter ce format JSON :\n{schema}\n\nContexte brut du forum:\n{contexte[:15000]}"
    try:
        response = model.generate_content(prompt)
        # Nettoyage de sécurité au cas où l'IA ajoute des balises Markdown
        texte_propre = response.text.replace('```json', '').replace('
        
