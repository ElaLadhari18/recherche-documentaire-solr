# main.py
# Point d'entrée de l'application.
# Interface graphique construite avec Tkinter (inclus par défaut dans Python).
#
# L'interface est divisée en trois onglets :
#   - Indexation  : ajouter des documents dans Solr
#   - Recherche   : chercher dans les documents indexés
#   - Historique  : consulter les recherches passées

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os

import extractor
import solr_client
import historique


# ---------------------------------------------------------------
# Classe principale de l'application
# ---------------------------------------------------------------

class ApplicationRecherche(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Système de Recherche Documentaire — Apache Solr")
        self.geometry("950x700")
        self.resizable(True, True)
        self.configure(bg="#f4f4f4")

        # Données partagées entre les méthodes
        self.resultats_actuels = []   # résultats de la dernière recherche
        self.fichiers_a_indexer = []  # fichiers sélectionnés par l'utilisateur

        # Vocabulaire de session : mots collectés pendant cette session
        # (titres indexés + mots extraits des fichiers)
        # Fonctionne même sans Solr et sans historique.
        self.vocabulaire_session = set()

        self._construire_interface()
        self._verifier_connexion_solr()

    # ==============================================================
    # STRUCTURE GLOBALE
    # ==============================================================

    def _construire_interface(self):
        """Construit la fenêtre principale avec le titre, le statut et les onglets."""

        # Bandeau titre
        cadre_titre = tk.Frame(self, bg="#1a1a2e", pady=10)
        cadre_titre.pack(fill="x")
        tk.Label(
            cadre_titre,
            text="🔍  Système de Recherche Documentaire — Apache Solr",
            font=("Georgia", 15, "bold"),
            fg="white", bg="#1a1a2e"
        ).pack()

        # Ligne de statut de connexion Solr
        self.label_statut = tk.Label(
            self,
            text="Vérification de la connexion à Solr...",
            font=("Helvetica", 9), fg="gray", bg="#f4f4f4"
        )
        self.label_statut.pack(anchor="w", padx=15, pady=2)

        # Onglets
        self.onglets = ttk.Notebook(self)
        self.onglets.pack(fill="both", expand=True, padx=10, pady=5)

        self._creer_onglet_indexation()
        self._creer_onglet_recherche()
        self._creer_onglet_historique()

        # Rechargement automatique de l'historique quand on clique sur l'onglet
        self.onglets.bind("<<NotebookTabChanged>>", self._onglet_change)

    # ==============================================================
    # ONGLET 1 — INDEXATION
    # ==============================================================

    def _creer_onglet_indexation(self):
        """Interface pour sélectionner et indexer des fichiers."""
        frame = ttk.Frame(self.onglets)
        self.onglets.add(frame, text="  📂  Indexation  ")

        tk.Label(
            frame,
            text="Sélectionnez des fichiers (PDF, Word, Excel, TXT) pour les indexer dans Solr.",
            font=("Helvetica", 10), fg="#444"
        ).pack(pady=(18, 5))

        # Bouton parcourir
        tk.Button(
            frame,
            text="Parcourir les fichiers...",
            command=self._choisir_fichiers,
            font=("Helvetica", 10, "bold"),
            bg="#16213e", fg="white",
            padx=15, pady=6, relief="flat", cursor="hand2"
        ).pack(pady=6)

        # Liste des fichiers sélectionnés
        tk.Label(frame, text="Fichiers sélectionnés :", font=("Helvetica", 9, "bold")).pack(anchor="w", padx=20)
        self.liste_fichiers_ui = tk.Listbox(frame, height=5, font=("Courier", 9), bg="white")
        self.liste_fichiers_ui.pack(fill="x", padx=20, pady=4)

        # Bouton lancer
        tk.Button(
            frame,
            text="▶  Lancer l'indexation",
            command=self._lancer_indexation,
            font=("Helvetica", 10, "bold"),
            bg="#0f3460", fg="white",
            padx=20, pady=8, relief="flat", cursor="hand2"
        ).pack(pady=8)

        # Journal d'indexation
        tk.Label(frame, text="Journal :", font=("Helvetica", 9, "bold")).pack(anchor="w", padx=20)
        self.log_indexation = scrolledtext.ScrolledText(
            frame, height=12,
            bg="#1e1e1e", fg="#d4d4d4",
            font=("Courier", 9),
            state="disabled", wrap="word"
        )
        self.log_indexation.pack(fill="both", expand=True, padx=20, pady=(0, 15))

    def _choisir_fichiers(self):
        """Ouvre une fenêtre de sélection de fichiers."""
        fichiers = filedialog.askopenfilenames(
            title="Choisir des documents à indexer",
            filetypes=[
                ("Formats supportés", "*.pdf *.docx *.xlsx *.txt"),
                ("PDF", "*.pdf"),
                ("Word", "*.docx"),
                ("Excel", "*.xlsx"),
                ("Texte", "*.txt"),
            ]
        )
        if fichiers:
            self.fichiers_a_indexer = list(fichiers)
            self.liste_fichiers_ui.delete(0, tk.END)
            for chemin in fichiers:
                self.liste_fichiers_ui.insert(tk.END, os.path.basename(chemin))

    def _lancer_indexation(self):
        """Lance l'indexation dans un thread séparé pour ne pas bloquer l'interface."""
        if not self.fichiers_a_indexer:
            messagebox.showwarning("Attention", "Veuillez d'abord sélectionner des fichiers.")
            return
        threading.Thread(target=self._indexer_fichiers, daemon=True).start()

    def _indexer_fichiers(self):
        """Traite chaque fichier : extraction du texte puis envoi à Solr."""
        for chemin in self.fichiers_a_indexer:
            nom = os.path.basename(chemin)
            extension = os.path.splitext(chemin)[1].lower().replace(".", "")

            self._log(f"\n→ {nom}")
            self._log(f"  Extraction du texte ({extension.upper()})...")

            contenu = extractor.extraire_texte(chemin)

            if not contenu:
                self._log("  ⚠ Aucun texte extrait. Fichier ignoré.")
                continue

            self._log(f"  ✓ {len(contenu.split())} mots extraits.")
            self._log("  Envoi à Solr...")

            succes, message = solr_client.indexer_document(nom, contenu, extension, chemin)
            self._log(f"  {'✅' if succes else '❌'} {message}")

            if succes:
                # Enrichissement du vocabulaire de session avec :
                # - le nom du fichier (sans extension)
                # - tous les mots significatifs du contenu (longueur >= 4)
                # Cela permet l'autocomplétion même sans historique et sans Solr Suggester.
                self.vocabulaire_session.add(os.path.splitext(nom)[0])
                mots = contenu.lower().split()
                for mot in mots:
                    mot_propre = mot.strip(".,;:!?\"'()[]{}«»")
                    if len(mot_propre) >= 4:
                        self.vocabulaire_session.add(mot_propre)

        self._log("\n─── Indexation terminée ───")

    def _log(self, texte):
        """Ajoute une ligne dans le journal (thread-safe via after())."""
        def ajouter():
            self.log_indexation.config(state="normal")
            self.log_indexation.insert(tk.END, texte + "\n")
            self.log_indexation.see(tk.END)
            self.log_indexation.config(state="disabled")
        self.after(0, ajouter)

    # ==============================================================
    # ONGLET 2 — RECHERCHE
    # ==============================================================

    def _creer_onglet_recherche(self):
        """Interface de recherche avec autocomplétion, filtre et prévisualisation."""
        frame = ttk.Frame(self.onglets)
        self.onglets.add(frame, text="  🔎  Recherche  ")

        # --- Barre de recherche ---
        cadre_barre = tk.Frame(frame, bg="#f4f4f4")
        cadre_barre.pack(fill="x", padx=20, pady=(15, 5))

        tk.Label(cadre_barre, text="Mot-clé :", font=("Helvetica", 10), bg="#f4f4f4").pack(side="left")

        # Champ de saisie — déclenche les suggestions à chaque frappe
        self.var_recherche = tk.StringVar()
        self.entree_recherche = ttk.Entry(
            cadre_barre, textvariable=self.var_recherche,
            font=("Helvetica", 12), width=30
        )
        self.entree_recherche.pack(side="left", padx=8)
        self.entree_recherche.bind("<KeyRelease>", self._maj_suggestions_hybride)
        self.entree_recherche.bind("<Return>", lambda e: self._lancer_recherche())

        # Filtre par type de fichier
        tk.Label(cadre_barre, text="Type :", font=("Helvetica", 10), bg="#f4f4f4").pack(side="left", padx=(10, 0))
        self.var_type = tk.StringVar(value="Tous")
        ttk.Combobox(
            cadre_barre,
            textvariable=self.var_type,
            values=["Tous", "pdf", "docx", "xlsx", "txt"],
            state="readonly", width=8
        ).pack(side="left", padx=5)

        # Bouton rechercher
        tk.Button(
            cadre_barre,
            text="Rechercher",
            command=self._lancer_recherche,
            font=("Helvetica", 10, "bold"),
            bg="#e94560", fg="white",
            padx=12, pady=4, relief="flat", cursor="hand2"
        ).pack(side="left", padx=10)

        # --- Liste déroulante d'autocomplétion ---
        # On utilise place() et non pack() pour la positionner exactement
        # sous le champ de saisie, comme un vrai dropdown.
        # Elle est placée dynamiquement dans _afficher_liste_suggestions().
        self.frame_recherche = frame  # on garde une ref au frame pour place()
        self.liste_suggestions = tk.Listbox(
            frame, height=5,
            bg="#fffde7", font=("Helvetica", 10),
            relief="solid", bd=1
        )
        # Pas de pack() ici — on utilise place() dynamiquement
        self.liste_suggestions.bind("<<ListboxSelect>>", self._choisir_suggestion)

        # Résumé du nombre de résultats
        self.label_nb_resultats = tk.Label(
            frame, text="", font=("Helvetica", 9, "italic"), fg="#555", bg="#f4f4f4"
        )
        self.label_nb_resultats.pack(anchor="w", padx=22, pady=(2, 0))

        # --- Panneau résultats (liste à gauche | prévisualisation à droite) ---
        paned = ttk.PanedWindow(frame, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=20, pady=10)

        # Liste des documents trouvés
        cadre_liste = ttk.LabelFrame(paned, text="Documents trouvés")
        paned.add(cadre_liste, weight=1)

        self.liste_resultats = tk.Listbox(cadre_liste, font=("Helvetica", 10), selectmode="single")
        barre = ttk.Scrollbar(cadre_liste, orient="vertical", command=self.liste_resultats.yview)
        self.liste_resultats.config(yscrollcommand=barre.set)
        barre.pack(side="right", fill="y")
        self.liste_resultats.pack(fill="both", expand=True)
        self.liste_resultats.bind("<<ListboxSelect>>", self._afficher_preview)

        # Zone de prévisualisation de l'extrait
        cadre_preview = ttk.LabelFrame(paned, text="Extrait du document")
        paned.add(cadre_preview, weight=2)

        self.zone_preview = scrolledtext.ScrolledText(
            cadre_preview, wrap="word",
            font=("Helvetica", 10), bg="#fafafa",
            state="disabled"
        )
        self.zone_preview.pack(fill="both", expand=True)

    # --- Autocomplétion hybride ---

    def _maj_suggestions_hybride(self, event):
        """
        Déclenchée à chaque frappe dans le champ de recherche.
        Lance la recherche de suggestions dans un thread séparé
        pour ne pas bloquer la frappe de l'utilisateur.

        Les suggestions viennent de 3 sources, par ordre de priorité :
          1. L'historique local  : recherches passées sauvegardées sur disque
          2. Le vocabulaire session : mots extraits des fichiers indexés ce run
          3. Solr (titres + Suggester FST) : si Solr est accessible
        """
        prefixe = self.var_recherche.get().strip()

        if len(prefixe) < 2:
            self.liste_suggestions.place_forget()
            return

        def chercher_suggestions():
            # Source 1 : historique local (immédiat, sans réseau)
            recents = historique.get_mots_cles_recents()
            s_historique = [m for m in recents if isinstance(m, str) and m.lower().startswith(prefixe.lower())]

            # Source 2 : vocabulaire de session (mots des docs indexés ce run)
            # Fonctionne TOUJOURS, même sans Solr et sans historique
            s_session = sorted([
                m for m in self.vocabulaire_session
                if isinstance(m, str) and m.lower().startswith(prefixe.lower())
            ])[:8]

            # Source 3 : Solr — titres indexés (wildcard) + Suggester FST
            brut_solr = solr_client.obtenir_suggestions_solr(prefixe)
            # On s'assure que chaque élément est bien une chaîne de caractères
            s_solr = [s for s in brut_solr if isinstance(s, str)]

            # Fusion sans doublons : historique d'abord, puis session, puis Solr
            toutes = list(dict.fromkeys(s_historique + s_session + s_solr))

            # Mise à jour de l'interface dans le thread principal
            self.after(0, lambda: self._afficher_liste_suggestions(toutes))

        threading.Thread(target=chercher_suggestions, daemon=True).start()

    def _afficher_liste_suggestions(self, liste):
        """
        Affiche la liste de suggestions directement sous le champ de saisie.
        On utilise place() avec les coordonnées absolues du champ pour
        positionner le dropdown exactement au bon endroit, comme un vrai menu.
        """
        if not liste:
            self.liste_suggestions.place_forget()
            return

        self.liste_suggestions.delete(0, tk.END)
        for suggestion in liste[:8]:
            self.liste_suggestions.insert(tk.END, suggestion)

        # On récupère la position absolue du champ de saisie dans la fenêtre
        self.entree_recherche.update_idletasks()  # s'assure que les coords sont calculées
        x = self.entree_recherche.winfo_x() + self.entree_recherche.master.winfo_x()
        y = self.entree_recherche.winfo_y() + self.entree_recherche.master.winfo_y() + self.entree_recherche.winfo_height()
        w = self.entree_recherche.winfo_width()

        # On positionne le dropdown juste sous le champ, même largeur
        self.liste_suggestions.place(
            in_=self.frame_recherche,
            x=x, y=y,
            width=w
        )
        self.liste_suggestions.lift()  # on s'assure qu'il est au-dessus des autres widgets

    def _choisir_suggestion(self, event):
        """Quand l'utilisateur clique sur une suggestion, on remplit le champ et on cherche."""
        selection = self.liste_suggestions.curselection()
        if selection:
            mot = self.liste_suggestions.get(selection[0])
            self.var_recherche.set(mot)
            self.liste_suggestions.place_forget()
            self._lancer_recherche()

    # --- Recherche ---

    def _lancer_recherche(self):
        """Lance la recherche dans un thread séparé."""
        mot = self.var_recherche.get().strip()
        if not mot:
            messagebox.showinfo("Info", "Entrez un mot-clé pour lancer la recherche.")
            return

        self.liste_suggestions.place_forget()
        self.label_nb_resultats.config(text="Recherche en cours...", fg="#555")

        type_filtre = self.var_type.get()

        def chercher():
            resultats, total = solr_client.rechercher(mot, type_filtre)
            self.after(0, lambda: self._afficher_resultats(resultats, total, mot, type_filtre))

        threading.Thread(target=chercher, daemon=True).start()

    def _afficher_resultats(self, resultats, total, mot, type_filtre):
        """Met à jour la liste des résultats après la recherche."""
        self.resultats_actuels = resultats
        self.liste_resultats.delete(0, tk.END)

        # Vider la prévisualisation
        self.zone_preview.config(state="normal")
        self.zone_preview.delete("1.0", tk.END)
        self.zone_preview.config(state="disabled")

        if isinstance(total, str):
            # total contient un message d'erreur
            self.label_nb_resultats.config(text=f"⚠ {total}", fg="red")
            return

        if total == 0:
            self.label_nb_resultats.config(text="Aucun résultat trouvé.", fg="#888")
            return

        self.label_nb_resultats.config(
            text=f"{total} document(s) trouvé(s) pour « {mot} »",
            fg="#1a1a2e"
        )

        icones = {"pdf": "📄", "docx": "📝", "xlsx": "📊", "txt": "📃"}
        for doc in resultats:
            icone = icones.get(doc["type"], "📁")
            self.liste_resultats.insert(tk.END, f"  {icone}  {doc['titre']}")

        # On sauvegarde dans l'historique
        historique.ajouter_recherche(mot, type_filtre, total)

    def _afficher_preview(self, event):
        """Affiche l'extrait du document sélectionné dans la zone de droite."""
        selection = self.liste_resultats.curselection()
        if not selection or selection[0] >= len(self.resultats_actuels):
            return

        doc = self.resultats_actuels[selection[0]]

        # Sécurité : Solr peut retourner des listes pour certains champs
        def s(val, defaut=""):
            if isinstance(val, list):
                return val[0] if val else defaut
            return val if val else defaut

        texte = f"Titre   : {s(doc['titre'], 'Sans titre')}\n"
        texte += f"Type    : {s(doc['type'], 'inconnu').upper()}\n"
        texte += f"Chemin  : {s(doc['chemin'])}\n"
        texte += f"\n{'─' * 50}\n\n"
        texte += "Extrait pertinent :\n\n"
        texte += s(doc["extrait"], "Pas d'extrait disponible")

        self.zone_preview.config(state="normal")
        self.zone_preview.delete("1.0", tk.END)
        self.zone_preview.insert(tk.END, texte)
        self.zone_preview.config(state="disabled")

    # ==============================================================
    # ONGLET 3 — HISTORIQUE
    # ==============================================================

    def _creer_onglet_historique(self):
        """Affiche l'historique des recherches dans un tableau."""
        frame = ttk.Frame(self.onglets)
        self.onglets.add(frame, text="  🕘  Historique  ")

        # Boutons d'action
        cadre_boutons = tk.Frame(frame)
        cadre_boutons.pack(fill="x", padx=20, pady=10)

        tk.Button(
            cadre_boutons, text="🔄  Actualiser",
            command=self._charger_historique,
            font=("Helvetica", 9), relief="flat", bg="#ddd",
            padx=10, pady=4, cursor="hand2"
        ).pack(side="left", padx=5)

        tk.Button(
            cadre_boutons, text="🗑  Effacer tout",
            command=self._effacer_historique,
            font=("Helvetica", 9), relief="flat", bg="#ffcccc",
            padx=10, pady=4, cursor="hand2"
        ).pack(side="left")

        # Tableau avec colonnes
        colonnes = ("date", "mot_cle", "type_filtre", "nb_resultats")
        self.tableau_historique = ttk.Treeview(frame, columns=colonnes, show="headings", height=20)
        self.tableau_historique.heading("date", text="Date")
        self.tableau_historique.heading("mot_cle", text="Mot-clé")
        self.tableau_historique.heading("type_filtre", text="Filtre")
        self.tableau_historique.heading("nb_resultats", text="Résultats")

        self.tableau_historique.column("date", width=130)
        self.tableau_historique.column("mot_cle", width=300)
        self.tableau_historique.column("type_filtre", width=100)
        self.tableau_historique.column("nb_resultats", width=90)

        barre = ttk.Scrollbar(frame, orient="vertical", command=self.tableau_historique.yview)
        self.tableau_historique.config(yscrollcommand=barre.set)
        barre.pack(side="right", fill="y")
        self.tableau_historique.pack(fill="both", expand=True, padx=20)

        self._charger_historique()

    def _charger_historique(self):
        """Charge et affiche toutes les entrées de l'historique."""
        self.tableau_historique.delete(*self.tableau_historique.get_children())
        for entree in reversed(historique.charger_historique()):
            self.tableau_historique.insert("", tk.END, values=(
                entree.get("date", ""),
                entree.get("mot_cle", ""),
                entree.get("type_filtre", "Tous"),
                entree.get("nb_resultats", 0)
            ))

    def _effacer_historique(self):
        """Demande confirmation puis efface tout l'historique."""
        if messagebox.askyesno("Confirmation", "Effacer tout l'historique ?"):
            historique.effacer_historique()
            self._charger_historique()

    def _onglet_change(self, event):
        """Recharge l'historique automatiquement quand on ouvre cet onglet."""
        nom = self.onglets.tab(self.onglets.select(), "text")
        if "Historique" in nom:
            self._charger_historique()

    # ==============================================================
    # CONNEXION SOLR
    # ==============================================================

    def _verifier_connexion_solr(self):
        """Vérifie la connexion Solr au démarrage dans un thread."""
        def verifier():
            ok, message = solr_client.tester_connexion()
            couleur = "#2e7d32" if ok else "#c62828"
            self.after(0, lambda: self.label_statut.config(text=f"Solr : {message}", fg=couleur))
        threading.Thread(target=verifier, daemon=True).start()


# ---------------------------------------------------------------
# Lancement
# ---------------------------------------------------------------

if __name__ == "__main__":
    app = ApplicationRecherche()
    app.mainloop()