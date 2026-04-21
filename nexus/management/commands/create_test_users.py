# nexus/management/commands/create_test_users.py
"""
Create a roster of planeswalker-themed test users.

Idempotent: existing users are updated with the profile fields below
instead of being recreated. Default password is applied to all users
(including existing ones) so test credentials stay predictable.

Usage:
    python manage.py create_test_users
    python manage.py create_test_users --password hunter2
    python manage.py create_test_users --dry-run
"""
from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from core.constants import MagicFormat


TEST_USERS = [
    {
        "username": "urza",
        "first_name": "Urza",
        "last_name": "Planeswalker",
        "email": "urza@blindeternities.test",
        "display_name": "Urza, Lord High Artificer",
        "bio": "Artificer of Dominaria. Builder of the Legacy Weapon.",
        "location": "Tolaria",
        "preferred_format": MagicFormat.MODERN,
    },
    {
        "username": "karn",
        "first_name": "Karn",
        "last_name": "Silver Golem",
        "email": "karn@blindeternities.test",
        "display_name": "Karn, Silver Golem",
        "bio": "Silver golem planeswalker. Creator of Argentum.",
        "location": "New Phyrexia",
        "preferred_format": MagicFormat.LEGACY,
    },
    {
        "username": "teferi",
        "first_name": "Teferi",
        "last_name": "Akosa",
        "email": "teferi@blindeternities.test",
        "display_name": "Teferi, Temporal Archmage",
        "bio": "Chronarch of Zhalfir. Master of time manipulation.",
        "location": "Zhalfir",
        "preferred_format": MagicFormat.STANDARD,
    },
    {
        "username": "nicol_bolas",
        "first_name": "Nicol",
        "last_name": "Bolas",
        "email": "nicol.bolas@blindeternities.test",
        "display_name": "Nicol Bolas, the Ravager",
        "bio": "Elder Dragon. God-Pharaoh. Plotting your demise.",
        "location": "Amonkhet",
        "preferred_format": MagicFormat.COMMANDER,
    },
    {
        "username": "freyalise",
        "first_name": "Freyalise",
        "last_name": "Llanowar",
        "email": "freyalise@blindeternities.test",
        "display_name": "Freyalise, Llanowar's Fury",
        "bio": "Elf druid planeswalker. Guardian of Skyshroud.",
        "location": "Llanowar",
        "preferred_format": MagicFormat.PIONEER,
    },
    {
        "username": "nahiri",
        "first_name": "Nahiri",
        "last_name": "Lithomancer",
        "email": "nahiri@blindeternities.test",
        "display_name": "Nahiri, the Lithomancer",
        "bio": "Kor lithomancer. Architect of the Eldrazi prison.",
        "location": "Zendikar",
        "preferred_format": MagicFormat.MODERN,
    },
    {
        "username": "sorin",
        "first_name": "Sorin",
        "last_name": "Markov",
        "email": "sorin@blindeternities.test",
        "display_name": "Sorin Markov",
        "bio": "Ancient vampire planeswalker of Innistrad.",
        "location": "Innistrad",
        "preferred_format": MagicFormat.VINTAGE,
    },
    {
        "username": "ugin",
        "first_name": "Ugin",
        "last_name": "Spirit Dragon",
        "email": "ugin@blindeternities.test",
        "display_name": "Ugin, the Spirit Dragon",
        "bio": "Spirit dragon planeswalker. Keeper of the Meditation Realm.",
        "location": "Meditation Realm",
        "preferred_format": MagicFormat.COMMANDER,
    },
    {
        "username": "toshiro",
        "first_name": "Toshiro",
        "last_name": "Umezawa",
        "email": "toshiro@blindeternities.test",
        "display_name": "Toshiro Umezawa",
        "bio": "Kamigawa samurai. Master of the dark instants.",
        "location": "Kamigawa",
        "preferred_format": MagicFormat.COMMANDER,
    },
]


class Command(BaseCommand):
    help = "Create planeswalker-themed test users with profiles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="testpass123",
            help="Password applied to every test user (default: testpass123).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing to the database.",
        )

    def handle(self, *args, **options):
        password = options["password"]
        dry_run = options["dry_run"]

        created, updated = [], []

        with transaction.atomic():
            for data in TEST_USERS:
                username = data["username"]
                user, was_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "first_name": data["first_name"],
                        "last_name": data["last_name"],
                        "email": data["email"],
                    },
                )
                if not was_created:
                    user.first_name = data["first_name"]
                    user.last_name = data["last_name"]
                    user.email = data["email"]

                user.set_password(password)
                user.save()

                profile = user.profile
                profile.display_name = data["display_name"]
                profile.bio = data["bio"]
                profile.location = data["location"]
                profile.preferred_format = data["preferred_format"]
                profile.is_public = True
                profile.save()

                EmailAddress.objects.update_or_create(
                    user=user,
                    email=data["email"],
                    defaults={"verified": True, "primary": True},
                )

                (created if was_created else updated).append(username)

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"Created {len(created)} user(s): {', '.join(created) or '—'}"
        ))
        self.stdout.write(self.style.WARNING(
            f"Updated {len(updated)} user(s): {', '.join(updated) or '—'}"
        ))
        self.stdout.write(f"Password for all test users: {password}")
        if dry_run:
            self.stdout.write(self.style.NOTICE("Dry run — rolled back."))
