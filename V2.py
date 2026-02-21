import streamlit as st
import json
import os
import graphviz
import base64
from datetime import datetime
from github import Github  # Rappel : Pip install PyGithub en local
from streamlit_cropper import st_cropper
from PIL import Image
import io

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

def supprimer_image_github(file_name):
    """Supprime physiquement le fichier image sur GitHub"""
    try:
        repo = get_repo()
        contents = repo.get_contents(f"images/{file_name}")
        repo.delete_file(contents.path, f"Suppression de {file_name}", contents.sha)
        return True
    except Exception as e:
        st.error(f"Erreur lors de la suppression sur GitHub : {e}")
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
        if 'photo_profil' not in p: p['photo_profil'] = None
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
    
    # --- OPTION 1 : CHERCHER UNE POULE (INTERFACE STYLE V1) ---
    if menu == "Chercher une poule":
        nom_defaut = st.session_state.get('poule_selectionnee', "")
        nom_cherche = st.text_input("Rechercher une poule :", value=nom_defaut)
        
        if nom_cherche:
            for i, p in enumerate(st.session_state.basse_cour):
                if p["nom"].lower() == nom_cherche.lower():
                    # --- INITIALISATION DES CLÉS ---
                    if 'photo_profil' not in p: p['photo_profil'] = None
                    if 'photo_oeuf' not in p: p['photo_oeuf'] = None
                    
                    age_v = calculer_age_automatique(p.get('naissance', ''))
                    st.header(f"✨ FICHE DE {p['nom'].upper()}")
                    
                    # CSS pour forcer le format CARRE (Crop visuel)
                    st.markdown("""
                        <style>
                        .square-img {
                            aspect-ratio: 1 / 1;
                            object-fit: cover;
                            border-radius: 15px;
                            border: 2px solid #ddd;
                        }
                        </style>
                        """, unsafe_allow_html=True)

                    tab1, tab2, tab3 = st.tabs(["📄 Informations", "📸 Galerie Photos", "🌳 Généalogie"])

                    with tab1:
                        col_pic, col_data = st.columns([1, 2])
                        
                        # --- AFFICHAGE PROFIL & OEUF (Format Carré via CSS) ---
                        with col_pic:
                            if p.get('photo_profil'):
                                url_prof = f"https://raw.githubusercontent.com/{REPO_NAME}/main/images/{p['photo_profil']}"
                                st.markdown(f'<img src="{url_prof}" class="square-img" style="width:100%;">', unsafe_allow_html=True)
                            if p.get('photo_oeuf'):
                                url_oeuf = f"https://raw.githubusercontent.com/{REPO_NAME}/main/images/{p['photo_oeuf']}"
                                st.markdown(f'<br><img src="{url_oeuf}" class="square-img" style="width:100px;">', unsafe_allow_html=True)

                        with col_data:
                            st.write(f"**Sexe :** {p['sexe']} | **Âge :** {age_v if age_v is not None else '?'} an(s)")
                            st.info(f"**Notes :** {p.get('notes', '...')}")

                        # --- OUTIL DE RECADRAGE VISUEL (ADMIN) ---
                        if st.session_state.role == "admin":
                            with st.expander("🎯 Créer une photo de profil (Recadrage)"):
                                st.write("1. Cliquez sur une photo de la galerie :")
                                
                                # Grille de sélection visuelle
                                photos_dispos = p['photos']['Croissance']
                                if photos_dispos:
                                    cols_sel = st.columns(4)
                                    for idx, img_name in enumerate(photos_dispos):
                                        with cols_sel[idx % 4]:
                                            url_thumb = f"https://raw.githubusercontent.com/{REPO_NAME}/main/images/{img_name}"
                                            st.image(url_thumb, use_container_width=True)
                                            if st.button("Choisir", key=f"sel_{img_name}"):
                                                st.session_state.img_to_crop = img_name
                                                st.rerun()
                                    
                                    # Si une photo est sélectionnée, on ouvre le cropper
                                    if 'img_to_crop' in st.session_state:
                                        st.divider()
                                        st.write(f"2. Ajustez le carré sur **{st.session_state.img_to_crop}** :")
                                        
                                        # On récupère l'image depuis GitHub pour le cropper
                                        img_url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/images/{st.session_state.img_to_crop}"
                                        import requests
                                        img_data = requests.get(img_url).content
                                        img_pil = Image.open(io.BytesIO(img_data))
                                        
                                        # L'outil de recadrage
                                        cropped_img = st_cropper(img_pil, aspect_ratio=(1,1), box_color='#FF0000')
                                        
                                        if st.button("Valider ce cadrage"):
                                            # Conversion de l'image recadrée en bytes pour GitHub
                                            buf = io.BytesIO()
                                            cropped_img.save(buf, format="JPEG")
                                            new_profile_name = f"profile_{p['nom']}.jpg"
                                            
                                            if upload_image_github(buf.getvalue(), new_profile_name):
                                                p['photo_profil'] = new_profile_name
                                                sauvegarder_donnees_github(st.session_state.basse_cour)
                                                del st.session_state.img_to_crop
                                                st.success("Photo de profil mise à jour !")
                                                st.rerun()
                                else:
                                    st.warning("Ajoutez d'abord des photos dans la galerie.")

                        with col_data:
                            st.write(f"**Sexe :** {p['sexe']}")
                            st.write(f"**Âge :** {age_v if age_v is not None else '?'} an(s)")
                            st.write(f"**Date de naissance :** {p.get('naissance', 'Non renseignée')}")
                            st.info(f"**Notes :** \n{p.get('notes', '...')}")

                        # --- NOUVELLE FONCTION : CHOIX RAPIDE (ADMIN SEUL) ---
                        if st.session_state.role == "admin":
                            with st.expander("🎯 Définir les photos (Profil & Œuf)"):
                                c_sel1, c_sel2 = st.columns(2)
                                
                                # Sélecteur Profil (parmi l'album Croissance)
                                liste_croissance = [None] + p['photos']['Croissance']
                                current_prof_idx = liste_croissance.index(p['photo_profil']) if p['photo_profil'] in liste_croissance else 0
                                new_prof = c_sel1.selectbox("Photo de profil", liste_croissance, index=current_prof_idx)
                                
                                # Sélecteur Oeuf (parmi l'album Oeufs)
                                liste_oeufs = [None] + p['photos']['Oeufs']
                                current_oeuf_idx = liste_oeufs.index(p['photo_oeuf']) if p['photo_oeuf'] in liste_oeufs else 0
                                new_oeuf = c_sel2.selectbox("Photo de l'œuf", liste_oeufs, index=current_oeuf_idx)
                                
                                if st.button("Appliquer les sélections"):
                                    p['photo_profil'] = new_prof
                                    p['photo_oeuf'] = new_oeuf
                                    sauvegarder_donnees_github(st.session_state.basse_cour)
                                    st.success("Photos de profil mises à jour !")
                                    st.rerun()

                            # Bouton supprimer classique (en bas)
                            if st.button(f"🗑️ Supprimer définitivement {p['nom']}"):
                                st.session_state.basse_cour.pop(i)
                                sauvegarder_donnees_github(st.session_state.basse_cour)
                                st.rerun()

                    with tab2:
                        # --- GESTION DE LA GALERIE ---
                        st.subheader("📸 Album Croissance")
                        
                        # Upload
                        if st.session_state.role == "admin":
                            with st.expander("📤 Ajouter des photos"):
                                up_files = st.file_uploader("Fichiers", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
                                album_target = st.selectbox("Destination", ["Croissance", "Oeufs"])
                                if up_files and st.button("Envoyer"):
                                    for up_file in up_files:
                                        f_name = f"{p['nom']}_{album_target}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{up_file.name}"
                                        if upload_image_github(up_file.getvalue(), f_name):
                                            p['photos'][album_target].append(f_name)
                                    sauvegarder_donnees_github(st.session_state.basse_cour)
                                    st.rerun()

                        # Tri et Affichage
                        album_croissance = p['photos']['Croissance']
                        if album_croissance:
                            ordre = st.radio("Trier par :", ["Plus récent", "Plus ancien"], horizontal=True)
                            photos_triees = sorted(album_croissance, reverse=(ordre == "Plus récent"))
                            
                            # Affichage en grille (3 colonnes)
                            cols = st.columns(3)
                            for idx, img in enumerate(photos_triees):
                                with cols[idx % 3]:
                                    url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/images/{img}"
                                    st.image(url, use_container_width=True)
                                    if st.session_state.role == "admin":
                                        if st.button("🗑️", key=f"del_{img}"):
                                            if supprimer_image_github(img):
                                                p['photos']['Croissance'].remove(img)
                                                if p['photo_profil'] == img: p['photo_profil'] = None
                                                sauvegarder_donnees_github(st.session_state.basse_cour)
                                                st.rerun()
                        else:
                            st.write("Aucune photo dans cet album.")

                    with tab3:
                        # RETOUR DE LA GÉNÉALOGIE CLIQUABLE STYLE V1
                        st.subheader("Parents")
                        cp1, cp2 = st.columns(2)
                        noms_existants = [x['nom'].lower() for x in st.session_state.basse_cour]
                        
                        for label, cle, col in [("Mère", "mere", cp1), ("Père", "pere", cp2)]:
                            nom_parent = p.get(cle, "?")
                            with col:
                                if nom_parent and nom_parent != "?" and nom_parent.lower() in noms_existants:
                                    st.button(f"🔍 {nom_parent}", key=f"btn_{cle}_{p['nom']}", 
                                              on_click=naviguer_vers_poule_callback, args=(nom_parent,))
                                else:
                                    st.write(f"{label} : {nom_parent if nom_parent else '?'}")

                        st.divider()
                        st.subheader("Enfants")
                        enfants = [e["nom"] for e in st.session_state.basse_cour 
                                   if e.get("mere", "").lower() == p["nom"].lower() 
                                   or e.get("pere", "").lower() == p["nom"].lower()]
                        
                        if enfants:
                            for enfant in enfants:
                                st.button(f"🐣 {enfant}", key=f"btn_child_{enfant}", 
                                          on_click=naviguer_vers_poule_callback, args=(enfant,))
                        else:
                            st.write("Aucun enfant répertorié.")
                    break

    # --- OPTION 2 : LISTE COMPLÈTE (AVEC BACKUP ADMIN) ---
    elif menu == "Voir toute la liste":
        st.subheader("📋 Liste des résidents")
        for p in sorted(st.session_state.basse_cour, key=lambda x: x['nom'].lower()):
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{p['nom']}** ({p['sexe']})")
            c2.button("Voir", key=f"l_{p['nom']}", on_click=naviguer_vers_poule_callback, args=(p['nom'],))
        
        # SECTION BACKUP - RÉSERVÉE À L'ADMIN
        if st.session_state.role == "admin":
            st.divider()
            st.subheader("📦 Archivage et Sauvegarde")
            st.write("Téléchargez une copie de vos données actuelles sur votre ordinateur.")
            
            # Préparation du JSON pour le téléchargement
            json_string = json.dumps(st.session_state.basse_cour, indent=4, ensure_ascii=False)
            
            st.download_button(
                label="📥 Sauvegarder un backup JSON sur mon PC",
                data=json_string,
                file_name=f"backup_basse_cour_{datetime.now().strftime('%d_%m_%Y_%Hh%M')}.json",
                mime="application/json"
            )
    # --- OPTION 3 : ARBRE GÉNÉALOGIQUE (AVEC TÉLÉCHARGEMENT) ---
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
                dot.node(p['nom'], f"{p['nom']}\n({age if age is not None else '?'} ans)", 
                         style='filled', color=color, shape=shape)
                if p.get('mere', '').lower() in noms_ok: dot.edge(p['mere'], p['nom'])
                if p.get('pere', '').lower() in noms_ok: dot.edge(p['pere'], p['nom'])
            
            # Affichage du graphique
            st.graphviz_chart(dot)
            
            # GÉNÉRATION DU BOUTON DE TÉLÉCHARGEMENT
            try:
                png_data = dot.pipe(format='png')
                st.download_button(
                    label="🖼️ Télécharger l'arbre en image (PNG)",
                    data=png_data,
                    file_name=f"arbre_genealogique_{datetime.now().strftime('%d_%m_%Y')}.png",
                    mime="image/png"
                )
            except Exception as e:
                st.warning("Le téléchargement de l'image est indisponible sur ce navigateur.")

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