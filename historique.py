# historique.py
# Gère l'historique des recherches de l'utilisateur.
# On sauvegarde tout dans un fichier JSON simple sur le disque.

import json
import os
from datetime import datetime

FICHIER_HISTORIQUE = "historique.json"
MAX_ENTREES = 50  # On garde au maximum 50 recherches


def charger_historique():
    """
    Charge l'historique depuis le fichier JSON.
    Si le fichier n'existe pas encore, on retourne une liste vide.
    """
    if not os.path.exists(FICHIER_HISTORIQUE):
        return []
    try:
        with open(FICHIER_HISTORIQUE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # Si le fichier est corrompu, on repart de zéro
        return []


def sauvegarder_historique(historique):
    """Écrit la liste de l'historique dans le fichier JSON."""
    try:
        with open(FICHIER_HISTORIQUE, "w", encoding="utf-8") as f:
            json.dump(historique, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Avertissement : impossible de sauvegarder l'historique ({e})")


def ajouter_recherche(mot_cle, type_filtre, nb_resultats):
    """
    Ajoute une nouvelle entrée dans l'historique.
    On évite les doublons consécutifs (même recherche deux fois de suite).
    """
    historique = charger_historique()

    nouvelle_entree = {
        "mot_cle": mot_cle,
        "type_filtre": type_filtre,
        "nb_resultats": nb_resultats,
        "date": datetime.now().strftime("%d/%m/%Y %H:%M")
    }

    # On n'ajoute pas si c'est exactement la même recherche que la dernière
    if historique and historique[-1]["mot_cle"] == mot_cle and historique[-1]["type_filtre"] == type_filtre:
        return

    historique.append(nouvelle_entree)

    # On limite la taille de l'historique
    if len(historique) > MAX_ENTREES:
        historique = historique[-MAX_ENTREES:]  # On garde seulement les 50 dernières

    sauvegarder_historique(historique)


def effacer_historique():
    """Supprime tout l'historique."""
    if os.path.exists(FICHIER_HISTORIQUE):
        os.remove(FICHIER_HISTORIQUE)


def get_mots_cles_recents(limite=10):
    """
    Retourne les derniers mots-clés recherchés (sans doublons).
    Utile pour l'autocomplétion locale.
    """
    historique = charger_historique()
    vus = set()
    mots_uniques = []
    # On parcourt à l'envers pour avoir les plus récents en premier
    for entree in reversed(historique):
        mot = entree["mot_cle"]
        if mot not in vus:
            vus.add(mot)
            mots_uniques.append(mot)
        if len(mots_uniques) >= limite:
            break
    return mots_uniques
