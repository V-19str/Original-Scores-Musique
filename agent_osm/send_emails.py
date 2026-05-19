"""
send_emails.py — Prospection OSM avec A/B/C test de templates.
CSV prospects : prospects.csv  (colonnes: prenom, boite, email)
Templates     : email_template_a/b/c.txt  (SUBJECT: ligne 1, corps suite)
Logs envois   : envoyes.csv
"""
import csv
import os
import random
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

ROOT          = Path(__file__).parent.parent
TEMPLATES     = [ROOT / f"email_template_{v}.txt" for v in ("a", "b", "c")]
PROSPECTS_CSV = ROOT / "prospects.csv"
SENT_CSV      = ROOT / "envoyes.csv"
DELAY_S       = 5  # secondes entre envois


def load_template(path: Path) -> tuple[str, str]:
    """Retourne (sujet, corps) depuis un fichier template."""
    lines = path.read_text(encoding="utf-8").splitlines()
    subject, skip = "", 1
    if lines and lines[0].startswith("SUBJECT:"):
        subject = lines[0].removeprefix("SUBJECT:").strip()
        skip = 2 if len(lines) > 1 and not lines[1].strip() else 1
    return subject, "\n".join(lines[skip:])


def fill(text: str, prenom: str, boite: str) -> str:
    return text.replace("{prenom}", prenom).replace("{boite}", boite)


def already_sent() -> set[str]:
    if not SENT_CSV.exists():
        return set()
    with open(SENT_CSV, encoding="utf-8", newline="") as f:
        return {r["email"].strip() for r in csv.DictReader(f) if r.get("email")}


def log_sent(email: str, prenom: str, boite: str, tpl: str):
    header = not SENT_CSV.exists()
    with open(SENT_CSV, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["email", "prenom", "boite", "template"])
        if header:
            w.writeheader()
        w.writerow({"email": email, "prenom": prenom, "boite": boite, "template": tpl})


def send_email(smtp: smtplib.SMTP, sender_email: str, sender_name: str,
               to: str, subject: str, body: str):
    msg = MIMEMultipart("alternative")
    msg["From"]    = f"{sender_name} <{sender_email}>"
    msg["To"]      = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    smtp.sendmail(sender_email, to, msg.as_string())


def main():
    host     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port     = int(os.environ.get("SMTP_PORT", "587"))
    user     = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    sender   = os.environ.get("SENDER_EMAIL", user)
    name     = os.environ.get("SENDER_NAME", "Vladimir Streiff — OSM")

    if not user or not password:
        raise SystemExit("Erreur : SMTP_USER et SMTP_PASSWORD requis.")

    templates = [(p.name, *load_template(p)) for p in TEMPLATES]
    print(f"→ {len(templates)} templates chargés : {[t[0] for t in templates]}")

    with open(PROSPECTS_CSV, encoding="utf-8", newline="") as f:
        prospects = [r for r in csv.DictReader(f) if r.get("email", "").strip()]

    sent    = already_sent()
    to_send = [p for p in prospects if p["email"].strip() not in sent]
    print(f"→ {len(to_send)} prospects à contacter ({len(sent)} déjà envoyés).")

    if not to_send:
        print("Rien à envoyer.")
        return

    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        smtp.login(user, password)

        for i, p in enumerate(to_send, 1):
            email  = p["email"].strip()
            prenom = p.get("prenom", "").strip() or "Madame/Monsieur"
            boite  = p.get("boite",  "").strip() or "votre société"

            tpl_name, subj_tpl, body_tpl = random.choice(templates)
            subject = fill(subj_tpl, prenom, boite)
            body    = fill(body_tpl, prenom, boite)

            try:
                send_email(smtp, sender, name, email, subject, body)
                log_sent(email, prenom, boite, tpl_name)
                print(f"  [{i}/{len(to_send)}] ✓ {email}  [{tpl_name}]")
            except Exception as e:
                print(f"  [{i}/{len(to_send)}] ✗ {email} — {e}")

            if i < len(to_send):
                time.sleep(DELAY_S)

    print(f"\n✓ Terminé — {len(to_send)} emails traités.")


if __name__ == "__main__":
    main()
