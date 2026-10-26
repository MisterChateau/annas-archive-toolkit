# annas-archive-toolkit

Deux petits scripts pour **chercher** et **télécharger** des livres depuis
Anna's Archive / Library Genesis — sans navigateur, sans captcha, et en
contournant les blocages habituels (DDoS-Guard, DNS filtré par le FAI).

- `anna_search.py` — cherche par auteur ou titre et renvoie les `md5`
- `anna_download.py` — télécharge un `md5` via l'API membre (et peut pousser vers Google Drive)

100 % bibliothèque standard Python (3.8+), aucune dépendance à installer.
`curl` est utilisé en interne par la recherche.

---

## Pourquoi deux scripts ?

Chercher et télécharger sont deux problèmes différents :

| Problème | Solution |
|---|---|
| Le site Anna's Archive est protégé par DDoS-Guard (403 / « checking your browser ») | l'API **membre** `dyn/api/fast_download.json` passe sans challenge |
| Les domaines `libgen.is` / `libgen.rs` ne résolvent plus (blocage FAI) | miroirs **libgen.li** (`.bz`, `.gl`, `.la`), résolus via **DNS-over-HTTPS** puis `curl --resolve` |
| La recherche HTML d'Anna's Archive est bloquée elle aussi | la recherche passe par **LibGen** — et le `md5` LibGen est **identique** au `md5` Anna's Archive |

D'où le flux : `anna_search.py` (LibGen) → `md5` → `anna_download.py` (API Anna's Archive).

---

## Installation

```bash
git clone https://github.com/<toi>/annas-archive-toolkit.git
cd annas-archive-toolkit
chmod +x anna_search.py anna_download.py
```

### Clé membre Anna's Archive

L'API de téléchargement exige une clé de membre — c'est un **abonnement
mensuel** (pas un paiement unique). Paliers officiels :

| Palier | Prix | Fast downloads |
|---|---|---|
| Brilliant Bookworm | 3–7 $/mois | 25 / jour |
| Lucky Librarian | 4–10 $/mois | 50 / jour |
| paliers supérieurs | — | davantage |

Le prix exact dépend du pouvoir d'achat du pays. Les paliers se cumulent.
La clé se trouve sur la page *Donate* du site officiel (`annas-archive.org`,
miroirs `.gl` / `.li` / `.se`).

⚠️ Méfie-toi des domaines qui vendent une « lifetime premium membership »
(`annas-archive.sh` et compagnie) : ce ne sont pas les sites officiels.

Deux façons de fournir la clé :

```bash
# variable d'environnement
export ANNAS_ARCHIVE_KEY='ta_cle'

# ou fichier protégé (recommandé)
mkdir -p ~/.config/annas-toolkit
echo 'ta_cle' > ~/.config/annas-toolkit/annas_key.txt
chmod 600 ~/.config/annas-toolkit/annas_key.txt
```

---

## Chercher

```bash
# par auteur
./anna_search.py author "Chapoutot"

# filtrer les homonymes (indispensable : il y a des « Chapoutot » en cardiologie…)
./anna_search.py author "Chapoutot" --author-match "Johann"

# par titre
./anna_search.py title "Libres d'obéir"

# ne garder que certains formats
./anna_search.py author "Graeber" --author-match "David" --ext epub

# sortie JSON (pour scripter)
./anna_search.py author "Graeber" --json > graeber.json

# juste les md5, un par ligne
./anna_search.py author "Graeber" --author-match "David" > md5s.txt
```

Sortie typique :

```
# 23 fichiers sur libgen.bz pour 'Kergoat'
2015 pdf   c96930f4a9a002e1466def886bc8323b Consubstantialité vs intersectionnalité? | Galerand, Elsa;Kergoat, Danièle
2010 pdf   baf66cbdceea9a663a65ffb93eae5b9c Le rapport social de sexe… | Kergoat, Danièle
```

Options : `--author-match REGEX`, `--filter REGEX`, `--ext epub,pdf`, `--limit N`, `--json`.

---

## Télécharger

```bash
# dans le dossier courant
./anna_download.py c96930f4a9a002e1466def886bc8323b

# dans un dossier précis
./anna_download.py c96930f4… -o ~/livres

# on peut coller une URL complète, le md5 est extrait
./anna_download.py https://annas-archive.gl/md5/c96930f4…

# upload Google Drive (nécessite la CLI gog : https://github.com/steipete/gog)
./anna_download.py c96930f4… --drive <FOLDER_ID> --account moi@gmail.com
```

Le script essaie automatiquement les 4 domaines CDN en cas d'échec, nettoie les
fichiers partiels, et tronque les noms de fichiers trop longs (limite ext4 :
255 octets — un nom Anna's Archive peut facilement la dépasser).

### Tout télécharger d'un auteur

```bash
./anna_search.py author "Norman Ajari" --json \
  | python3 -c "import sys,json;[print(b['md5']) for b in json.load(sys.stdin)]" \
  | while read md5; do ./anna_download.py "$md5" -o ~/livres; sleep 2; done
```

---

## Limites connues

- **Quota** : 25 téléchargements/jour avec le palier d'entrée (~3-7 $/mois).
  Abonnement **mensuel**, pas à vie. `HTTP 429` sur tous les domaines = quota épuisé.
- **Couverture** : on ne trouve que ce qui est indexé par LibGen. Un livre très
  récent, un auto-édition ou un texte jamais scanné restera introuvable.
- **Fichiers fantômes** : certains `md5` existent en base mais le fichier a été
  retiré des CDN → `aucun domaine CDN n'a pu fournir le fichier`.
- **Pas de pagination** sur les miroirs : la recherche renvoie d'un coup tous les
  identifiants de fichiers correspondants (parfois plusieurs centaines).
- **Langue** : LibGen n'expose pas la langue dans son JSON d'édition — filtrez
  sur le titre ou l'éditeur.

---

## Dépannage

| Symptôme | Cause / solution |
|---|---|
| `HTTP 403` sur annas-archive | DDoS-Guard : normal, ne pas scraper — utiliser `anna_download.py` |
| Aucun miroir LibGen joignable | le FAI bloque aussi le DoH ; changer de réseau ou passer par un VPN |
| `HTTP 429` partout | quota journalier épuisé |
| `File name too long` | corrigé : le nom est tronqué à 200 octets |
| `API : invalid key` | clé absente ou erronée |

---

## Note légale

Ces scripts ne font qu'automatiser des requêtes vers des services tiers.
Le téléchargement d'œuvres protégées n'est légal que dans le cadre prévu par
la loi de ton pays (copie privée, exception pédagogique, œuvres libres…).
À utiliser en connaissance de cause, sous ta responsabilité.

## Licence

MIT — voir [LICENSE](LICENSE).
