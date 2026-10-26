#!/usr/bin/env python3
"""Téléchargement de livres depuis Anna's Archive via l'API membre (fast_download).

La clé membre contourne DDoS-Guard : c'est le chemin fiable quand le site est
inaccessible depuis un navigateur automatisé.

La clé se configure par ordre de priorité :
  1. variable d'environnement ANNAS_ARCHIVE_KEY
  2. ~/.config/annas-toolkit/annas_key.txt
  3. ./.annas_key (dans le dossier courant)

Usage :
  anna_download.py <md5|url> [--output DIR] [--drive FOLDER_ID] [--account EMAIL]

Exemples :
  anna_download.py f3d7b9c54d3b521e7de2afd13e62baed
  anna_download.py https://annas-archive.gl/md5/f3d7b9c5... -o ~/livres
  anna_download.py <md5> --drive 1AbC... --account moi@gmail.com
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MIRRORS = ["annas-archive.gl", "annas-archive.li", "annas-archive.in", "annas-archive.pm"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
KEY_PATHS = [
    Path.home() / ".config" / "annas-toolkit" / "annas_key.txt",
    Path(".annas_key"),
]
MAX_NAME_BYTES = 200  # ext4 : 255 octets max par nom de fichier


def get_key():
    key = os.environ.get("ANNAS_ARCHIVE_KEY", "").strip()
    if key:
        return key
    for p in KEY_PATHS:
        if p.exists():
            k = p.read_text().strip()
            if k:
                return k
    print("❌ Clé absente. Fais : export ANNAS_ARCHIVE_KEY=... "
          "ou écris-la dans ~/.config/annas-toolkit/annas_key.txt")
    return None


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        print(f"⚠️  Réseau : {e}")
        return None, b""


def get_base_url():
    for d in MIRRORS:
        code, _ = fetch(f"https://{d}/", timeout=8)
        if code == 200:
            return f"https://{d}"
    return f"https://{MIRRORS[0]}"


def safe_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    if len(name.encode("utf-8")) <= MAX_NAME_BYTES:
        return name
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    tail = ("." + ext) if ext else ""
    keep = MAX_NAME_BYTES - len(tail.encode("utf-8"))
    return stem.encode("utf-8")[-keep:].decode("utf-8", "ignore").lstrip(" _-") + tail


def download_book(md5, output_dir=None, path_index=0, domain_index=0):
    """Télécharge via l'API fast_download, avec repli automatique sur les domaines CDN."""
    key = get_key()
    if not key:
        return None

    base = get_base_url()
    domains = [domain_index] if domain_index else [0, 1, 2, 3]

    for di in domains:
        params = {"md5": md5, "key": key, "path_index": path_index, "domain_index": di}
        url = f"{base}/dyn/api/fast_download.json?{urllib.parse.urlencode(params)}"
        print(f"📡 API fast_download (domaine {di})…")
        code, body = fetch(url)
        if code != 200:
            print(f"   ⚠️  API HTTP {code}" + (" (quota journalier épuisé ?)" if code == 429 else ""))
            continue
        try:
            data = json.loads(body.decode("utf-8", "replace"))
        except Exception:
            print(f"   ❌ Réponse non-JSON : {body[:120]}")
            continue
        if data.get("error"):
            print(f"   ❌ API : {data['error']}")
            continue

        dl_url = data.get("download_url")
        if not dl_url:
            print("   ❌ Pas d'URL de téléchargement")
            continue

        left = data.get("account_fast_download_info", {}).get("downloads_left", "?")
        print(f"📊 Téléchargements restants aujourd'hui : {left}")

        filename = safe_filename(urllib.parse.unquote(dl_url.split("/")[-1].split("?")[0]))
        out_dir = Path(output_dir) if output_dir else Path.cwd()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename

        print(f"📥 Téléchargement (domaine {di})…")
        try:
            req = urllib.request.Request(dl_url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                if r.status != 200:
                    print(f"   ⚠️  HTTP {r.status}")
                    continue
                out_path.write_bytes(r.read())
        except Exception as e:
            print(f"   ⚠️  Erreur : {e}")
            if out_path.exists():
                out_path.unlink()
            continue

        if not out_path.exists() or out_path.stat().st_size == 0:
            print("   ⚠️  Fichier vide")
            continue

        size = out_path.stat().st_size
        print(f"✅ {size / 1024 / 1024:.1f} MB → {out_path}")
        return str(out_path)

    print("❌ Échec : aucun domaine CDN n'a fourni le fichier "
          "(fichier retiré, ou quota épuisé).")
    return None


def upload_drive(filepath, folder_id, account=None):
    """Upload via la CLI gog (Google Workspace). Optionnel."""
    gog = shutil.which("gog")
    if not gog:
        print("⚠️  CLI 'gog' introuvable — upload Drive ignoré.")
        return False
    cmd = [gog, "drive", "upload", filepath, "--parent", folder_id]
    if account:
        cmd += ["--account", account]
    print("☁️  Upload Google Drive…")
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode == 0:
        print("✅ Uploadé")
        for line in out.splitlines():
            if "drive.google.com" in line:
                print(f"🔗 {line.strip()}")
        return True
    print(f"⚠️  Échec upload : {out[-300:]}")
    return False


def main():
    ap = argparse.ArgumentParser(description="Télécharger un livre (Anna's Archive, API membre)")
    ap.add_argument("md5", help="md5 ou URL /md5/…")
    ap.add_argument("-o", "--output", help="Dossier de sortie")
    ap.add_argument("--drive", metavar="FOLDER_ID", help="Uploader vers ce dossier Google Drive")
    ap.add_argument("--account", help="Compte Google (pour gog)")
    ap.add_argument("--path-index", type=int, default=0)
    ap.add_argument("--domain-index", type=int, default=0)
    a = ap.parse_args()

    md5 = a.md5
    m = re.search(r"/md5/([a-f0-9]{32})", md5)
    if m:
        md5 = m.group(1)
        print(f"📌 md5 extrait : {md5}")

    path = download_book(md5, a.output, a.path_index, a.domain_index)
    if path and a.drive:
        upload_drive(path, a.drive, a.account)
    elif path:
        print("💡 Pour uploader : --drive <FOLDER_ID> --account toi@gmail.com")


if __name__ == "__main__":
    main()
