#!/usr/bin/env python3
"""Recherche d'auteurs/titres sur LibGen (miroirs libgen.li) sans DDoS-Guard.

But : trouver les md5 des fichiers, puis les télécharger avec
`anna_download.py <md5>` (le md5 LibGen == le md5 Anna's Archive).

Beaucoup de FAI bloquent la résolution DNS de libgen.is/.rs : on résout via
DoH (Cloudflare) puis on force l'IP avec `curl --resolve`.

Usage :
  anna_search.py author "Chapoutot" --author-match Johann --ext epub
  anna_search.py title "Libres d'obéir"
  anna_search.py author "Graeber" --json > resultats.json
  anna_search.py md5 "Graeber"            # juste les lignes md5

Options : --author-match <regex>, --filter <regex>, --ext epub,pdf, --limit N, --json
"""
import argparse
import json
import re
import subprocess
import sys
import unicodedata

MIRRORS = ["libgen.bz", "libgen.gl", "libgen.la"]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def resolve(host):
    """IP publique via DoH (le DNS local bloque ces domaines)."""
    try:
        out = subprocess.run(
            ["curl", "-s", "-m", "10", "-H", "accept: application/dns-json",
             f"https://cloudflare-dns.com/dns-query?name={host}&type=A"],
            capture_output=True, text=True, check=True).stdout
        ans = json.loads(out).get("Answer", [])
        ips = [a["data"] for a in ans if a.get("type") == 1]
        return ips[0] if ips else None
    except Exception:
        return None


def pick_mirror():
    for host in MIRRORS:
        ip = resolve(host)
        if not ip:
            continue
        code = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-m", "12", "--resolve", f"{host}:443:{ip}",
             "-A", UA, f"https://{host}/"], capture_output=True, text=True).stdout
        if code is not None:
            return host, ip
    return None, None


def curl(url, host, ip, timeout=40):
    r = subprocess.run(
        ["curl", "-s", "-m", str(timeout), "--resolve", f"{host}:443:{ip}", "-A", UA, url],
        capture_output=True, text=True)
    return r.stdout


def search(query, column="a", host="libgen.bz", ip=None):
    """column: a=auteur, t=titre"""
    args = ["curl", "-s", "-m", "40", "--resolve", f"{host}:443:{ip}", "-A", UA,
            "-G", "--data-urlencode", f"req={query}", "--data-urlencode", f"columns[]={column}",
            "--data-urlencode", "res=100", f"https://{host}/index.php"]
    html = subprocess.run(args, capture_output=True, text=True).stdout
    m = re.search(r"/json\.php\?object=f&ids=([^\"]+)", html)
    if not m:
        return []
    ids = m.group(1)
    files = json.loads(curl(f"https://{host}/json.php?object=f&ids={ids}", host, ip) or "{}")
    e_ids = sorted({str(v.get("e_id")) for f in files.values()
                    for v in (f.get("editions") or {}).values() if v.get("e_id")})
    eds = {}
    for i in range(0, len(e_ids), 80):
        chunk = ",".join(e_ids[i:i + 80])
        txt = curl(f"https://{host}/json.php?object=e&ids={chunk}", host, ip)
        try:
            eds.update(json.loads(txt))
        except Exception:
            pass
    rows = []
    for fid, f in files.items():
        for v in (f.get("editions") or {}).values():
            e = eds.get(str(v.get("e_id")))
            if not e:
                continue
            rows.append({
                "md5": f.get("md5"),
                "ext": f.get("extension"),
                "size_kb": round(int(f.get("filesize") or 0) / 1024),
                "title": e.get("title"),
                "author": e.get("author"),
                "year": e.get("year"),
                "publisher": e.get("publisher"),
                "file_id": fid,
                "source": f"{host}/file.php?id={fid}",
            })
    return rows


def norm(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", t.lower())).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["author", "title", "md5"])
    ap.add_argument("query")
    ap.add_argument("--author-match", help="regex à faire matcher dans le champ auteur (ex: Johann)")
    ap.add_argument("--filter", help="regex à faire matcher dans titre+auteur")
    ap.add_argument("--ext")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    host, ip = pick_mirror()
    if not host:
        sys.exit("❌ Aucun miroir LibGen joignable (DoH + resolve).")

    rows = search(a.query, "a" if a.mode == "author" else "t", host, ip)
    if a.author_match:
        rx = re.compile(a.author_match, re.I)
        rows = [r for r in rows if rx.search(r["author"] or "")]
    if a.filter:
        rx = re.compile(a.filter, re.I)
        rows = [r for r in rows if rx.search((r["title"] or "") + " " + (r["author"] or ""))]
    if a.ext:
        exts = {x.strip().lower() for x in a.ext.split(",")}
        rows = [r for r in rows if (r["ext"] or "").lower() in exts]

    if a.mode == "md5":
        seen = []
        for r in rows:
            if r["md5"] not in seen:
                seen.append(r["md5"])
        print("\n".join(seen[:a.limit]))
        return

    if a.json:
        print(json.dumps(rows[:a.limit], ensure_ascii=False, indent=1))
        return

    print(f"# {len(rows)} fichiers sur {host} pour '{a.query}'")
    for r in rows[:a.limit]:
        print("%-4s %-5s %-9s %s | %s" % (r["year"] or "?", r["ext"], r["md5"],
                                          (r["title"] or "")[:60], (r["author"] or "")[:30]))


if __name__ == "__main__":
    main()
