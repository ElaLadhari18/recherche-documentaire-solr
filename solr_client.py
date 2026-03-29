# solr_client.py
# Gère toute la communication avec Apache Solr via son API REST.
# Solr fonctionne comme un serveur web : on lui envoie des requêtes HTTP
# et il nous répond en JSON.

import requests
import json
import uuid

# ---------------------------------------------------------------
# Cache simple pour les suggestions (évite de requêter Solr à chaque frappe)
# On garde les résultats 60 secondes avant de re-interroger Solr.
# ---------------------------------------------------------------
import time
_cache_suggestions = {}   # { prefixe: (timestamp, liste_resultats) }
DUREE_CACHE = 60          # secondes

# ---------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------
SOLR_URL = "http://localhost:8983/solr"
COLLECTION = "documents"


def url_base():
    """Retourne l'URL de base de notre collection Solr."""
    return f"{SOLR_URL}/{COLLECTION}"


# ---------------------------------------------------------------
# 1. Indexation d'un document
# ---------------------------------------------------------------

def indexer_document(titre, contenu, type_fichier, chemin_fichier):
    """
    Envoie un document à Solr pour l'indexer.
    Solr analyse le contenu et le rend cherchable via un index inversé.

    Retourne (True, message) si succès, (False, erreur) sinon.
    """
    doc_id = str(uuid.uuid4())

    document = {
        "id": doc_id,
        "titre": titre,
        "contenu": contenu,
        "type": type_fichier,
        "chemin": chemin_fichier
    }

    try:
        reponse = requests.post(
            f"{url_base()}/update/json/docs",
            headers={"Content-Type": "application/json"},
            data=json.dumps(document),
            params={"commit": "true"},  # rend le document visible immédiatement
            timeout=10
        )

        if reponse.status_code == 200:
            return True, f"Document '{titre}' indexé avec succès (ID: {doc_id[:8]}...)"
        else:
            return False, f"Erreur Solr {reponse.status_code} : {reponse.text}"

    except requests.exceptions.ConnectionError:
        return False, "Impossible de se connecter à Solr. Vérifiez que Solr est lancé sur localhost:8983"
    except Exception as e:
        return False, f"Erreur inattendue : {e}"


# ---------------------------------------------------------------
# 2. Recherche dans les documents indexés
# ---------------------------------------------------------------

def rechercher(mot_cle, type_filtre=None, page=0, nb_resultats=10):
    """
    Cherche des documents dans Solr contenant le mot_cle donné.

    Paramètres :
    - mot_cle      : ce que l'utilisateur cherche
    - type_filtre  : filtre par type ("pdf", "docx", etc.) ou "Tous"
    - page         : numéro de page pour la pagination
    - nb_resultats : nombre de résultats par page

    Retourne (liste_de_résultats, total) ou ([], message_erreur).
    """
    params = {
        "q": f"contenu:{mot_cle} OR titre:{mot_cle}",  # cherche dans le titre ET le contenu
        "hl": "true",           # active la mise en surbrillance des extraits
        "hl.fl": "contenu",     # champ à surligner
        "hl.snippets": 2,       # nombre d'extraits retournés par document
        "hl.fragsize": 150,     # taille de chaque extrait en caractères
        "start": page * nb_resultats,
        "rows": nb_resultats,
        "wt": "json"
    }

    # Filtrage par type de fichier (fq = filter query dans Solr)
    if type_filtre and type_filtre != "Tous":
        params["fq"] = f"type:{type_filtre.lower()}"

    try:
        reponse = requests.get(f"{url_base()}/select", params=params, timeout=10)

        if reponse.status_code != 200:
            return [], f"Erreur Solr {reponse.status_code}"

        data = reponse.json()
        docs = data["response"]["docs"]
        total = data["response"]["numFound"]
        highlights = data.get("highlighting", {})

        resultats = []
        for doc in docs:
            doc_id = doc.get("id", "")
            extrait = ""
            # On récupère l'extrait surligné si disponible
            if doc_id in highlights and "contenu" in highlights[doc_id]:
                extrait = " ... ".join(highlights[doc_id]["contenu"])

            # Solr retourne parfois les champs sous forme de liste (champs multivalués).
            # On prend toujours le premier élément si c'est le cas.
            def val(champ, defaut=""):
                v = doc.get(champ, defaut)
                return v[0] if isinstance(v, list) else v

            resultats.append({
                "id": doc_id,
                "titre": val("titre", "Sans titre"),
                "type":  val("type",  "inconnu"),
                "chemin": val("chemin", ""),
                "extrait": extrait or "Pas d'extrait disponible"
            })

        return resultats, total

    except requests.exceptions.ConnectionError:
        return [], "Impossible de se connecter à Solr."
    except Exception as e:
        return [], f"Erreur : {e}"


# ---------------------------------------------------------------
# 3. Autocomplétion hybride (3 sources combinées)
# ---------------------------------------------------------------

def obtenir_suggestions_solr(prefixe):
    """
    Retourne des suggestions d'autocomplétion depuis Solr.
    Combine deux approches :

    Source A — Recherche dans le contenu via terme générique (q=prefixe*) :
        On cherche tous les documents dont le contenu OU le titre contient
        un mot commençant par le préfixe. On extrait ensuite les mots
        correspondants directement depuis les résultats.
        Fonctionne sans aucune configuration spéciale dans Solr.

    Source B — Suggester FST (si configuré dans solrconfig.xml) :
        Le Suggester de Solr utilise un Finite State Transducer pour
        proposer des complétions ultra-rapides depuis un dictionnaire
        précompilé. On force le rebuild à chaque appel pour avoir
        les données à jour.
    """
    if len(prefixe) < 2:
        return []

    resultats = []

    # --- Source A : recherche générique avec wildcard dans le contenu ---
    # On cherche les documents qui contiennent un terme commençant par le préfixe.
    # On utilise le paramètre "terms" de Solr pour extraire les vrais termes de l'index.
    try:
        reponse = requests.get(
            f"{url_base()}/select",
            params={
                "q":  f"contenu:{prefixe}*",
                "fl": "titre",       # on récupère les titres des documents trouvés
                "rows": 10,
                "wt": "json"
            },
            timeout=1.5
        )
        if reponse.status_code == 200:
            docs = reponse.json()["response"]["docs"]
            for doc in docs:
                titre = doc.get("titre", "")
                if isinstance(titre, str) and titre.strip():
                    # On ajoute le titre entier comme suggestion
                    if titre not in resultats:
                        resultats.append(titre)
                    # On ajoute aussi chaque mot du titre qui commence par le préfixe
                    for mot in titre.split():
                        mot_propre = mot.strip('.,;:!?()[]')
                        if mot_propre.lower().startswith(prefixe.lower()) and mot_propre not in resultats:
                            resultats.append(mot_propre)
    except Exception:
        pass

    # --- Source B : Terms Component de Solr ---
    # Interroge directement l'index inversé pour trouver tous les termes
    # qui commencent par le préfixe. Très précis car on lit l'index réel.
    prefixe_lower = prefixe.lower()
    maintenant = time.time()

    # On vérifie si on a déjà une réponse récente pour ce préfixe en cache
    if prefixe_lower in _cache_suggestions:
        ts, cached = _cache_suggestions[prefixe_lower]
        if maintenant - ts < DUREE_CACHE:
            # Cache valide : on utilise les résultats sans appel réseau
            for terme in cached:
                if terme not in resultats:
                    resultats.append(terme)
        else:
            del _cache_suggestions[prefixe_lower]  # cache expiré

    if prefixe_lower not in _cache_suggestions:
        # Pas en cache : on interroge Solr
        try:
            reponse = requests.get(
                f"{url_base()}/terms",
                params={
                    "terms": "true",
                    "terms.fl": "contenu",
                    "terms.prefix": prefixe_lower,
                    "terms.limit": 8,
                    "terms.mincount": 1,
                    "wt": "json"
                },
                timeout=2   # on coupe à 2s max pour ne pas bloquer l'interface
            )
            if reponse.status_code == 200:
                data = reponse.json()
                termes_index = data.get("terms", {}).get("contenu", [])
                # Solr retourne une liste alternée : [terme, count, terme, count, ...]
                nouveaux = []
                for i in range(0, len(termes_index) - 1, 2):
                    terme = termes_index[i]
                    if isinstance(terme, str):
                        nouveaux.append(terme)
                        if terme not in resultats:
                            resultats.append(terme)
                # On sauvegarde en cache pour les prochaines frappes
                _cache_suggestions[prefixe_lower] = (maintenant, nouveaux)
        except Exception:
            pass  # Terms component non disponible ou timeout, la source A suffit

    # --- Source C : Suggester FST (optionnel, si configuré) ---
    try:
        reponse = requests.get(
            f"{url_base()}/suggest",
            params={
                "suggest": "true",
                "suggest.build": "true",     # force la reconstruction du FST
                "suggest.dictionary": "mySuggester",
                "suggest.q": prefixe,
                "wt": "json"
            },
            timeout=1
        )
        if reponse.status_code == 200:
            data = reponse.json()
            suggestions_data = (
                data.get("suggest", {})
                    .get("mySuggester", {})
                    .get(prefixe, {})
            )
            for s in suggestions_data.get("suggestions", []):
                terme = s.get("term", "")
                if isinstance(terme, str) and terme and terme not in resultats:
                    resultats.append(terme)
    except Exception:
        pass  # Suggester non configuré, les sources A et B suffisent

    return resultats[:8]


# ---------------------------------------------------------------
# 4. Vérification de la connexion à Solr
# ---------------------------------------------------------------

def tester_connexion():
    """
    Vérifie si Solr est accessible et si notre collection existe.
    Appelé au démarrage de l'application.
    Retourne (True, message) ou (False, erreur).
    """
    try:
        reponse = requests.get(
            f"{url_base()}/admin/ping",
            params={"wt": "json"},
            timeout=5
        )
        if reponse.status_code == 200:
            return True, "Connexion à Solr établie avec succès ✓"
        else:
            return False, f"Solr répond mais avec une erreur ({reponse.status_code}). La collection '{COLLECTION}' existe-t-elle ?"
    except requests.exceptions.ConnectionError:
        return False, "Solr n'est pas accessible. Lancez Solr avec : bin/solr start"
    except Exception as e:
        return False, f"Erreur : {e}"