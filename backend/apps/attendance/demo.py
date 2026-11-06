"""Cartes et présences de démonstration (lot 10) : une carte pour neuf élèves sur dix et pour
tout le personnel, les passages à l'entrée des quinze derniers jours de classe (lundi au
vendredi, congés exclus, aujourd'hui compris), quelques retards, des absents — dont quelques
élèves souvent absents, pour l'alerte —, des corrections au journal et des justifications
(acceptées, refusées, en attente, dont une de l'enfant du parent de démonstration). Le jeton des
cartes n'est gardé nulle part : on les réimprime en les émettant de nouveau.

Rien au journal d'audit, comme le reste de la démonstration ; tout est remis comme au départ à
chaque `make demo`."""

import random
import secrets
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.accounts.models import Membership
from apps.accounts.roles import ATTENDANCE_CORRECT
from apps.attendance import cards, follow
from apps.attendance.models import (
    AbsenceJustification,
    AttendanceCorrection,
    AttendanceRecord,
    AttendanceSession,
    IdCard,
)
from apps.core.tenancy import use_school
from apps.schools import organisation
from apps.schools.attendance import late_after
from apps.schools.demo import DemoSpace
from apps.students.models import Family

DAYS = 15
CARD_SHARE, ABSENT_SHARE, LATE_SHARE, STAFF_PRESENT = 0.9, 0.04, 0.06, 0.92
# Élèves souvent absents (un sur trente), absents deux jours sur cinq.
OFTEN_ABSENT_SHARE, OFTEN_ABSENT = 1 / 30, 0.4
Status = AbsenceJustification.Status


def create_demo_attendance(spaces: list[DemoSpace]) -> None:
    for space in spaces:
        school = space.school
        with use_school(school), timezone.override(ZoneInfo(school.timezone)):
            _fill(school, random.Random(f"presences-{school.code}"))


def _clear() -> None:
    AttendanceCorrection.objects.all().delete()
    AbsenceJustification.objects.all().delete()
    AttendanceRecord.objects.all().delete()
    AttendanceSession.objects.all().delete()
    IdCard.objects.all().delete()


def _days(today: date) -> list[date]:
    """Les `DAYS` derniers jours de classe, du plus ancien à aujourd'hui."""
    year = organisation.current_year()
    off = follow.holidays(today - timedelta(days=60), today)
    found, day = [], today
    while len(found) < DAYS and (year is None or day >= year.starts_on):
        if day.weekday() < 5 and day not in off:
            found.append(day)
        day -= timedelta(days=1)
    return found[::-1]


def _card(holder: dict, until: date, actor) -> IdCard:
    token = secrets.token_hex(16)
    return IdCard(
        token_hash=cards.fingerprint(token),
        last4=token[-4:].upper(),
        valid_until=until,
        created_by=actor,
        **holder,
    )


def _fill(school, rng: random.Random) -> None:
    _clear()
    year = organisation.current_year()
    head = (
        Membership.objects.filter(
            school=school, is_active=True, roles__permissions__contains=[ATTENDANCE_CORRECT]
        )
        .select_related("user")
        .order_by("user__phone")
        .first()
    )
    if year is None or head is None:
        return
    actor = head.user
    enrollments = list(cards.current_enrollments().select_related("student").order_by("pk"))
    members = list(cards.staff().order_by("pk"))
    until = cards.valid_until(school, year)
    IdCard.objects.bulk_create(
        [
            _card({"student": item.student}, until, actor)
            for item in enrollments
            if rng.random() < CARD_SHARE
        ]
        + [_card({"member": member}, until, actor) for member in members]
    )
    card_of = {
        card.student_id or card.member_id: card for card in IdCard.objects.filter(revoked_at=None)
    }
    limit = late_after(school.settings)
    days = _days(timezone.localdate())
    often = {item.student_id for item in enrollments if rng.random() < OFTEN_ABSENT_SHARE}
    # Enfant du parent de démonstration : absent les deux derniers jours d'avant aujourd'hui.
    demo_family = Family.objects.filter(primary_user__isnull=False).order_by("created_at").first()
    demo_child = next(
        (
            item.student
            for item in enrollments
            if demo_family is not None and item.student.family_id == demo_family.pk
        ),
        None,
    )
    records, absences = [], []
    for day in days:
        session = AttendanceSession.objects.create(
            kind=AttendanceSession.Kind.ENTRANCE, date=day, created_by=actor
        )
        for item in enrollments:
            share = OFTEN_ABSENT if item.student_id in often else ABSENT_SHARE
            missing = rng.random() < share
            if demo_child is not None and item.student_id == demo_child.pk:
                missing = day in days[-3:-1]
            if missing:
                absences.append((day, session, item.student))
                continue
            card = card_of.get(item.student_id)
            records.append(_record(session, day, rng, limit, actor, card, student=item.student))
        for member in members:
            if rng.random() < STAFF_PRESENT:
                card = card_of.get(member.pk)
                records.append(_record(session, day, rng, limit, actor, card, member=member))
    AttendanceRecord.objects.bulk_create(records, batch_size=2000)
    _corrections(absences, actor, rng)
    _justifications(absences, actor, demo_child, days, rng)


def _record(session, day, rng, limit, actor, card, **holder) -> AttendanceRecord:
    late = rng.random() < LATE_SHARE
    start = datetime.combine(day, limit if late else time(6, 45))
    seen = start + timedelta(minutes=rng.randint(1, 50))
    return AttendanceRecord(
        session=session,
        card=card,
        seen_at=timezone.make_aware(seen),
        method=AttendanceRecord.Method.QR if card else AttendanceRecord.Method.MANUAL,
        status=AttendanceRecord.Status.LATE if late else AttendanceRecord.Status.PRESENT,
        created_by=actor,
        **holder,
    )


def _corrections(absences: list, actor, rng: random.Random) -> None:
    """Trois absents des jours passés étaient en classe : carte oubliée."""
    past = [entry for entry in absences if entry[0] < timezone.localdate()]
    AttendanceCorrection.objects.bulk_create(
        [
            AttendanceCorrection(
                session=session,
                student=student,
                status=AttendanceCorrection.Status.PRESENT,
                previous_status=AttendanceCorrection.Status.ABSENT,
                reason="Présent en classe, carte oubliée",
                created_by=actor,
            )
            for _, session, student in rng.sample(past, min(3, len(past)))
        ]
    )


def _justifications(absences: list, actor, demo_child, days: list, rng: random.Random) -> None:
    """Trois mots apportés par les parents (acceptés), un certificat refusé, deux en attente
    envoyés depuis le Portail — dont celui de l'enfant du parent de démonstration, pour son
    avant-dernier jour d'absence (le dernier reste à justifier)."""
    corrected = set(AttendanceCorrection.objects.values_list("session_id", "student_id"))
    candidates = [
        (day, student)
        for day, session, student in absences
        if (session.pk, student.pk) not in corrected
        and student != demo_child
        and day < timezone.localdate()
    ]
    picked = rng.sample(candidates, min(6, len(candidates)))
    now = timezone.now()
    rows = []
    reasons = ["Malade (paludisme)", "Deuil dans la famille", "Rendez-vous à l'hôpital"]
    statuses = [Status.ACCEPTED] * 3 + [Status.REFUSED] + [Status.PENDING] * 2
    for index, (day, student) in enumerate(picked):
        status = statuses[index]
        rows.append(
            AbsenceJustification(
                student=student,
                starts_on=day,
                ends_on=day,
                reason=reasons[index % len(reasons)],
                source=AbsenceJustification.Source.SCHOOL
                if index < 3
                else AbsenceJustification.Source.PORTAL,
                status=status,
                decided_at=None if status == Status.PENDING else now,
                decided_by=None if status == Status.PENDING else actor,
                decision_note="Certificat illisible : merci de passer au secrétariat"
                if status == Status.REFUSED
                else "",
                created_by=actor,
            )
        )
    if demo_child is not None and len(days) >= 3:
        rows.append(
            AbsenceJustification(
                student=demo_child,
                starts_on=days[-3],
                ends_on=days[-3],
                reason="Fièvre, il est resté à la maison",
                source=AbsenceJustification.Source.PORTAL,
                created_by=demo_child.family.primary_user,
            )
        )
    AbsenceJustification.objects.bulk_create(rows)
