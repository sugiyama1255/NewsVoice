import time

from django.conf import settings
from django.core.management.base import BaseCommand

from newsvoice.models import ProcessingJob
from newsvoice.services.jobs import claim_next_job, process_job


class Command(BaseCommand):
    help = "Process queued NewsVoice background jobs."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process one queued job and exit.")
        parser.add_argument("--sleep", type=float, default=2.0, help="Seconds to wait when the queue is empty.")
        parser.add_argument(
            "--failure-sleep",
            type=float,
            default=None,
            help="Seconds to wait after a failed news fetch job.",
        )

    def handle(self, *args, **options):
        run_once = options["once"]
        sleep_seconds = options["sleep"]
        failure_sleep_seconds = options["failure_sleep"]
        if failure_sleep_seconds is None:
            failure_sleep_seconds = getattr(settings, "NEWSVOICE_NEWS_FETCH_FAILURE_COOLDOWN_SECONDS", 60)

        while True:
            job = claim_next_job()
            if job:
                processed_job = process_job(job)
                if (
                    not run_once
                    and processed_job.job_type == ProcessingJob.TYPE_NEWS_FETCH
                    and processed_job.status == ProcessingJob.STATUS_FAILED
                    and failure_sleep_seconds > 0
                ):
                    self.stdout.write(
                        f"News fetch failed. Waiting {failure_sleep_seconds:.0f}s before the next job."
                    )
                    time.sleep(failure_sleep_seconds)
            elif run_once:
                self.stdout.write("No queued jobs.")
                return
            else:
                time.sleep(sleep_seconds)

            if run_once:
                return
