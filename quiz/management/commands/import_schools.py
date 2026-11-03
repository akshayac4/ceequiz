import openpyxl
from django.core.management.base import BaseCommand

from quiz.models import District, School


class Command(BaseCommand):
    help = "STUB — not used yet. Import the School master list from an Excel file once CEE provides it. Columns: name, district, udise_code."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to the School master list .xlsx file")

    def handle(self, *args, **options):
        wb = openpyxl.load_workbook(options["path"], data_only=True)
        ws = wb.active
        created = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            name, district_name, udise_code = (row + (None, None, None))[:3]
            if not name:
                continue
            district = District.objects.filter(name_en__iexact=str(district_name).strip()).first() if district_name else None
            School.objects.get_or_create(
                name=str(name).strip(),
                district=district,
                defaults={"udise_code": str(udise_code or "").strip()},
            )
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Imported {created} school(s)."))
