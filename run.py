import argparse
from core.fetcher import fetch_and_store_jobs
from core.mailer import send_scheduled_emails
from core.db import get_stats

def main():
    parser = argparse.ArgumentParser(description="AI Job Mailer CLI")
    parser.add_argument("--fetch", action="store_true", help="Fetch and ingest new leads from RapidAPI")
    parser.add_argument("--send", action="store_true", help="Dispatch pending cold emails")
    parser.add_argument("--force", action="store_true", help="Bypass slot schedule restrictions when sending")
    parser.add_argument("--limit", type=int, default=None, help="Custom limit for email batch")
    parser.add_argument("--stats", action="store_true", help="Print lead stats")

    args = parser.parse_args()

    if args.stats:
        stats = get_stats()
        print(f"Total Leads: {stats['total']} | Pending: {stats['pending']} | Sent: {stats['sent']}")

    if args.fetch:
        fetch_and_store_jobs()

    if args.send:
        send_scheduled_emails(force=args.force, custom_limit=args.limit)

    if not (args.fetch or args.send or args.stats):
        parser.print_help()

if __name__ == "__main__":
    main()

