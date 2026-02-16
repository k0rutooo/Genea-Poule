import streamlit as st
import json
import os
import graphviz
import base64
from datetime import datetime
from github import Github  # Rappel : Pip install PyGithub en local

# --- 1. CONFIGURATION ET SECRETS ---
st.set_page_config(page_title="Généa-Poules Cloud", page_icon="🐔", layout="wide")

# Récupération sécurisée des accès
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    CODE_ADMIN = st.secrets["codes"]["admin"]
    CODE_VISITEUR = st.secrets["codes"]["visiteur"]
except Exception:
    st.error("⚠️ Erreur : Les Secrets ne sont pas configurés sur Streamlit Cloud.")
    st.stop()

FILE_PATH = "sauvegardes json/basse_cour_autosave.json"

# --- 2. FONCTIONS DE GESTION GITHUB ---

def get_repo():
    """Connecte l'application à ton dépôt GitHub"""
    g = Github(GITHUB_TOKEN)
    return g.get_repo(REPO_NAME)

def charger_donnees_github():
    """Télécharge le JSON depuis GitHub et le nettoie"""
    try:
        repo = get_repo()
        contents = repo.get_contents(FILE_PATH)
        data = base64.b64decode(contents.content).decode("utf-8")
        donnees = json.loads(data)
        return migrer_donnees(donnees)
    except Exception:
        return []

def sauvegarder_donnees_github(liste):
    """Enregistre le JSON sur GitHub (Commit automatique)"""
    repo = get_repo()
    contents = repo.get_contents(FILE_PATH)
    nouveau_contenu = json.dumps(liste, indent=4, ensure_ascii=False)
    repo.update_file(
        contents.path, 
        f"Mise à jour basse-cour : {datetime.now().strftime('%d/%m/%Y %H:%M')}", 
        nouveau_contenu, 
        contents.sha
    )

def upload_image_github(file_bytes, file_name):
    """Envoie physiquement le fichier image dans le dossier images/ de GitHub"""
    try:
        repo = get_repo()
        path = f"images/{file_name}"
        # On essaie de créer le fichier (ou de l'écraser s'il existe déjà)
        try:
            contents = repo.get_contents(path)
            repo.update_file(contents.path, f"MAJ image {file_name}", file_bytes, contents.sha)
        except Exception:
            repo.create_file(path, f"Upload image {file_name}", file_bytes)
        return True
    except Exception as e:
        st.error(f"Erreur lors de l'envoi de l'image : {e}")
        return False

# --- 3. LOGIQUE MÉTIER (Migration & Âge) ---

def migrer_donnees(liste):
    """Harmonise les données et supprime les vieux champs"""
    modifie = False
    for p in liste:
        # Nettoyage vieux champs
        if 'age' in p:
            del p['age']
            modifie = True
        # Harmonisation Sexe
        if p.get('sexe') in ["M", "m"]: p['sexe'] = "Coq"; modifie = True
        elif p.get('sexe') in ["F", "f"]: p['sexe'] = "Poule"; modifie = True
        # Harmonisation Photos
        if 'photos' not in p or isinstance(p.get('photos'), list):
            anciennes = p.get('photos', []) if isinstance(p.get('photos'), list) else []
            p['photos'] = {"Croissance": anciennes, "Oeufs": []}
            modifie = True
    return liste

def calculer_age_automatique(date_str):
    if not date_str or date_str == "Non renseignée": return None
    try:
        dn = datetime.strptime(date_str, "%d/%m/%Y").date()
        return round((datetime.now().date() - dn).days / 365.25, 1)
    except Exception: return None

# --- 4. INITIALISATION DE LA SESSION ---

if 'role' not in st.session_state:
    st.session_state.role = None

if 'basse_cour' not in st.session_state:
    st.session_state.basse_cour = charger_donnees_github()

# --- 5. PAGE DE CONNEXION ---

if st.session_state.role is None:
    st.title("🔐 Accès à la Basse-Cour")
    code = st.text_input("Entrez votre code d'accès :", type="password")
    if st.button("Se connecter"):
        if code == CODE_ADMIN:
            st.session_state.role = "admin"
            st.rerun()
        elif code == CODE_VISITEUR:
            st.session_state.role = "visiteur"
            st.rerun()
        else:
            st.error("Code incorrect.")
    st.stop()

# --- 6. BARRE LATÉRALE ET NAVIGATION ---

st.sidebar.title(f"🐔 Profil : {st.session_state.role.upper()}")

nav_options = ["Chercher une poule", "Voir toute la liste", "Arbre Généalogique", "Statistiques"]
if st.session_state.role == "admin":
    nav_options.append("Ajouter un membre")

menu = st.sidebar.radio("Navigation", nav_options, key="menu_selection")

if st.sidebar.button("Se déconnecter"):
    st.session_state.role = None
    st.rerun()

# Callback pour naviguer entre les fiches
def naviguer_vers_poule_callback(nom):
    st.session_state.poule_selectionnee = nom
    st.session_state.menu_selection = "Chercher une poule"

# --- 7. CONTENEUR PRINCIPAL (Fix Ghost UI) ---

main_zone = st.empty()

with main_zone.container():
    
    # --- OPTION 1 : RECHERCHE ET FICHE ---
    if menu == "Chercher une poule":
        nom_defaut = st.session_state.get('poule_selectionnee', "")
        nom_cherche = st.text_input("Rechercher une poule :", value=nom_defaut)
        
        if nom_cherche:
            for i, p in enumerate(st.session_state.basse_cour):
                if p["nom"].lower() == nom_cherche.lower():
                    age_v = calculer_age_automatique(p.get('naissance', ''))
                    st.header(f"✨ FICHE DE {p['nom'].upper()}")
                    t1, t2, t3 = st.tabs(["📄 Informations", "📸 Photos", "🌳 Lignée"])

                    with t1:
                        st.write(f"**Sexe :** {p['sexe']} | **Âge :** {age_v if age_v is not None else '?'} an(s)")
                        st.info(f"**Notes :** {p.get('notes', '...')}")
                        
                        if st.session_state.role == "admin":
                            if st.button(f"🗑️ Supprimer {p['nom']}"):
                                st.session_state.basse_cour.pop(i)
                                sauvegarder_donnees_github(st.session_state.basse_cour)
                                st.rerun()

                    with t2:
                        photos = p.get('photos', {"Croissance": [], "Oeufs": []})
                        if st.session_state.role == "admin":
                            with st.expander("📤 Envoyer une photo depuis cet appareil"):
                                up_file = st.file_uploader("Choisir un fichier", type=['jpg', 'jpeg', 'png'])
                                album = st.selectbox("Album", ["Croissance", "Oeufs"])
                                if up_file and st.button("Lancer l'envoi"):
                                    f_name = f"{p['nom']}_{album}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                                    if upload_image_github(up_file.getvalue(), f_name):
                                        photos[album].append(f_name)
                                        sauvegarder_donnees_github(st.session_state.basse_cour)
                                        st.success("Image sauvegardée sur GitHub !")
                                        st.rerun()

                        c1, c2 = st.columns(2)
                        for cat, col in zip(["Croissance", "Oeufs"], [c1, c2]):
                            with col:
                                st.subheader(cat)
                                for img in photos[cat]:
                                    url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/images/{img}"
                                    st.image(url, use_container_width=True)

                    with t3:
                        st.write(f"**Mère :** {p.get('mere', '?')} | **Père :** {p.get('pere', '?')}")
                        enf = [e["nom"] for e in st.session_state.basse_cour if e["mere"].lower() == p["nom"].lower() or e["pere"].lower() == p["nom"].lower()]
                        if enf: st.write(f"**Enfants :** {', '.join(enf)}")
                    break

    # --- OPTION 2 : LISTE COMPLÈTE ---
    elif menu == "Voir toute la liste":
        st.subheader("📋 Liste des résidents")
        for p in sorted(st.session_state.basse_cour, key=lambda x: x['nom'].lower()):
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{p['nom']}** ({p['sexe']})")
            c2.button("Voir", key=f"l_{p['nom']}", on_click=naviguer_vers_poule_callback, args=(p['nom'],))

    # --- OPTION 3 : ARBRE GÉNÉALOGIQUE ---
    elif menu == "Arbre Généalogique":
        st.header("🌳 Arbre de la Basse-Cour")
        with st.spinner("Construction du graphique..."):
            dot = graphviz.Digraph(format='png')
            dot.attr(rankdir='TB', size='10')
            noms_ok = [x['nom'].lower() for x in st.session_state.basse_cour]
            for p in st.session_state.basse_cour:
                age = calculer_age_automatique(p.get('naissance', ''))
                color = "lightblue" if p['sexe'] == "Coq" else "lightpink"
                shape = "box" if p['sexe'] == "Coq" else "ellipse"
                dot.node(p['nom'], f"{p['nom']}\n({age if age is not None else '?'} ans)", style='filled', color=color, shape=shape)
                if p.get('mere', '').lower() in noms_ok: dot.edge(p['mere'], p['nom'])
                if p.get('pere', '').lower() in noms_ok: dot.edge(p['pere'], p['nom'])
            st.graphviz_chart(dot)

    # --- OPTION 4 : STATISTIQUES ---
    elif menu == "Statistiques":
        st.header("📊 Statistiques de l'élevage")
        total = len(st.session_state.basse_cour)
        
        if total > 0:
            poules = [p for p in st.session_state.basse_cour if p.get('sexe') == "Poule"]
            coqs = [p for p in st.session_state.basse_cour if p.get('sexe') == "Coq"]
            ages = [calculer_age_automatique(p.get('naissance', '')) for p in st.session_state.basse_cour]
            ages_valides = [a for a in ages if isinstance(a, (int, float))]
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Total individus", total)
            m2.metric("Poules", len(poules), f"{round(len(poules)/total*100)}%")
            m3.metric("Coqs", len(coqs), f"{round(len(coqs)/total*100)}%")
            
            st.divider()
            col_age1, col_age2 = st.columns(2)
            if ages_valides:
                moyenne = round(sum(ages_valides) / len(ages_valides), 1)
                doyenne = sorted(st.session_state.basse_cour, key=lambda x: calculer_age_automatique(x.get('naissance', '')) or 0)[-1]
                
                col_age1.subheader("⏳ Âges")
                col_age1.write(f"**Âge moyen :** {moyenne} an(s)")
                col_age1.write(f"**La doyenne :** {doyenne['nom']} ({calculer_age_automatique(doyenne.get('naissance', ''))} ans)")
            
            col_age2.subheader("🐣 Dernier arrivé")
            if st.session_state.basse_cour:
                dernier = st.session_state.basse_cour[-1]
                col_age2.write(f"**Nom :** {dernier['nom']}")
                col_age2.write(f"**Date :** {dernier.get('naissance', '?')}")
        else:
            st.info("Ajoutez des membres pour voir les statistiques.")
            
    # --- OPTION 5 : AJOUTER (ADMIN SEUL) ---
    elif menu == "Ajouter un membre":
        st.subheader("🐣 Nouveau membre")
        with st.form("ajout_poule"):
            n = st.text_input("Nom")
            s = st.selectbox("Sexe", ["Poule", "Coq"])
            d = st.text_input("Naissance (JJ/MM/AAAA)")
            m = st.text_input("Mère")
            pe = st.text_input("Père")
            if st.form_submit_button("Créer la fiche"):
                if n and not any(p['nom'].lower() == n.lower() for p in st.session_state.basse_cour):
                    st.session_state.basse_cour.append({"nom":n, "sexe":s, "naissance":d, "mere":m, "pere":pe, "photos":{"Croissance":[], "Oeufs":[]}})
                    sauvegarder_donnees_github(st.session_state.basse_cour)
                    st.success(f"Fiche de {n} créée et sauvegardée !")
                    st.rerun()