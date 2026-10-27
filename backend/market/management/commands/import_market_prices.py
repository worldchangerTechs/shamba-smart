import csv
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date

from accounts.models import Ward
from farms.models import Crop
from market.models import MarketPrice


REQUIRED_COLUMNS = {"crop", "market_name", "ward", "price_per_kg", "date"}


class Command(BaseCommand):
    help = "Import daily market prices from a UTF-8 CSV file."

    def add_arguments(self, parser):
        parser.add_argument("csv_file", help="CSV with crop, market_name, ward, price_per_kg, date.")

    @transaction.atomic
    def handle(self, *args, **options):
        csv_path = options["csv_file"]
        try:
            source = open(csv_path, encoding="utf-8-sig", newline="")
        except OSError as exc:
            raise CommandError(f"Cannot open CSV file {csv_path}: {exc}") from exc

        created = 0
        updated = 0
        with source:
            reader = csv.DictReader(source)
            if not reader.fieldnames:
                raise CommandError("CSV is empty or has no header row.")
            columns = {column.strip() for column in reader.fieldnames if column}
            missing = REQUIRED_COLUMNS - columns
            if missing:
                raise CommandError(
                    "CSV is missing required columns: " + ", ".join(sorted(missing))
                )

            for row_number, row in enumerate(reader, start=2):
                normalized = {
                    (key or "").strip(): (value or "").strip()
                    for key, value in row.items()
                }
                try:
                    crop = Crop.objects.get(name__iexact=normalized["crop"])
                    ward = Ward.objects.get(name__iexact=normalized["ward"])
                    price = Decimal(normalized["price_per_kg"])
                    price_date = parse_date(normalized["date"])
                    if not price.is_finite() or price < 0:
                        raise ValueError("price_per_kg must be finite and non-negative")
                    if price.as_tuple().exponent < -2 or price >= Decimal("100000000"):
                        raise ValueError(
                            "price_per_kg must fit a non-negative 10-digit value with at most 2 decimal places"
                        )
                    if price_date is None:
                        raise ValueError("date must use YYYY-MM-DD")
                    market_name = normalized["market_name"]
                    if not market_name:
                        raise ValueError("market_name cannot be empty")
                    sample = normalized.get("is_sample_data", "false").casefold()
                    if sample not in {"true", "false", "1", "0", "yes", "no"}:
                        raise ValueError("is_sample_data must be true or false")
                except Crop.DoesNotExist as exc:
                    raise CommandError(
                        f"CSV row {row_number}: unknown crop {normalized.get('crop')!r}."
                    ) from exc
                except Ward.DoesNotExist as exc:
                    raise CommandError(
                        f"CSV row {row_number}: unknown ward {normalized.get('ward')!r}."
                    ) from exc
                except (InvalidOperation, KeyError, ValueError) as exc:
                    raise CommandError(f"CSV row {row_number}: {exc}.") from exc

                record, was_created = MarketPrice.objects.update_or_create(
                    crop=crop,
                    market_name=market_name,
                    ward=ward,
                    date=price_date,
                    defaults={
                        "price_per_kg": price,
                        "is_sample_data": sample in {"true", "1", "yes"},
                    },
                )
                created += int(was_created)
                updated += int(not was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported market prices: {created} created, {updated} updated."
            )
        )
