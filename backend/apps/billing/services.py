"""Offres, contrats et conditions générales (CTR.1, ABO.1). Toute écriture est au journal : de la
plateforme pour ce que fait la console, de l'école pour ce qui la touche (règle 5)."""

from datetime import date

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts import modules as module_catalog
from apps.audit import services as audit
from apps.audit.actions import Action, PlatformAction
from apps.billing.models import Contract, Counter, LegalAcceptance, LegalDocument, Plan
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import use_all_schools, use_school
from apps.schools.models import School
from apps.schools.services import save_school

CONTRACT_NOT_DRAFT = ApiError(
    "contract_not_draft",
    _("Only a draft contract can change; make an amendment instead."),
    409,
)
CONTRACT_ACTIVE_EXISTS = ApiError(
    "contract_active_exists", _("This school already has an active contract."), 409
)
SIGNATURE_MISSING = ApiError(
    "contract_signature_missing", _("Give the signed copy or the signer's name."), 400
)
VERSION_PUBLISHED = ApiError(
    "legal_version_published", _("A published version never changes: publish a new one."), 409
)
NOT_PUBLISHED = ApiError("legal_not_published", _("This version is not published."), 409)


def next_number(key: str, prefix: str) -> str:
    """`CT-2026-0007` : la ligne de la suite est verrouillée le temps de prendre le numéro."""
    counter, _created = Counter.objects.select_for_update().get_or_create(key=key)
    counter.value += 1
    counter.save(update_fields=["value"])
    return f"{prefix}-{counter.value:04d}"


def _plan_values(plan: Plan) -> dict:
    return {
        "code": plan.code,
        "modules": plan.modules,
        "price_per_student": plan.price_per_student,
        "currency": plan.currency,
        "period": plan.period,
        "active": plan.active,
    }


def save_plan(*, actor, plan: Plan | None = None, **values) -> Plan:
    """Crée ou change une offre. Les contrats déjà signés gardent leur copie du prix."""
    creating = plan is None
    with transaction.atomic():
        before = {} if creating else _plan_values(plan)
        plan = plan or Plan(created_by=actor)
        for key, value in values.items():
            setattr(plan, key, value)
        plan.modules = module_catalog.resolve(plan.modules)
        plan.full_clean()
        plan.save()
        before, after = audit.changes(before, _plan_values(plan))
        audit.record_platform(
            PlatformAction.PLAN_SAVED, plan, actor=actor, before=before or None, after=after
        )
    return plan


def draft_contract(
    *, actor, school: School, plan: Plan, start_date: date, end_date: date, **options
) -> Contract:
    """Contrat en brouillon, copiant les conditions du plan (prix et durée modifiables avant la
    signature, par `options`)."""
    with transaction.atomic(), use_school(school):
        contract = Contract(
            school=school,
            created_by=actor,
            number=next_number(f"contract-{start_date.year}", f"CT-{start_date.year}"),
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            modules=options.pop("modules", plan.modules),
            price_per_student=options.pop("price_per_student", plan.price_per_student),
            currency=plan.currency,
            period=plan.period,
            **options,
        )
        contract.full_clean()
        contract.save()
        audit.record_platform(
            PlatformAction.CONTRACT_CREATED,
            contract,
            actor=actor,
            after={"school": school.code, "plan": plan.code, "start": str(start_date)},
        )
    return contract


def activate_contract(
    contract: Contract, *, actor, signature: str, signer_name: str = "", signed_file=None
) -> Contract:
    """Signature : par dépôt du scan ou par acceptation en ligne. Le contrat devient immuable,
    termine celui qu'il remplace (avenant) et donne à l'école les modules du plan."""
    if signature == Contract.Signature.UPLOAD and not signed_file:
        raise BusinessError(SIGNATURE_MISSING)
    if signature == Contract.Signature.ONLINE and not signer_name.strip():
        raise BusinessError(SIGNATURE_MISSING)
    with transaction.atomic(), use_all_schools():
        contract = Contract.all_schools.select_for_update().get(pk=contract.pk)
        if contract.status != Contract.Status.DRAFT:
            raise BusinessError(CONTRACT_NOT_DRAFT)
        school = School.objects.select_for_update().get(pk=contract.school_id)
        active = Contract.all_schools.filter(school=school, status=Contract.Status.ACTIVE)
        if contract.replaces_id:
            active = active.exclude(pk=contract.replaces_id)
        if active.exists():
            raise BusinessError(CONTRACT_ACTIVE_EXISTS)
        if contract.replaces_id:
            Contract.all_schools.filter(pk=contract.replaces_id).update(
                status=Contract.Status.ENDED
            )
        contract.status = Contract.Status.ACTIVE
        contract.signature = signature
        contract.signer_name = signer_name.strip()
        contract.signed_at = timezone.now()
        if signed_file:
            contract.signed_file = signed_file
        contract.save()
        school.modules = module_catalog.resolve(contract.modules)
        save_school(school, actor=actor)
        audit.record_platform(
            PlatformAction.CONTRACT_ACTIVATED,
            contract,
            actor=actor,
            after={"school": school.code, "modules": contract.modules},
        )
        with use_school(school):
            audit.record(Action.CONTRACT_ACTIVATED, contract, actor=actor)
    return contract


def amend_contract(contract: Contract, *, actor, **changes) -> Contract:
    """Avenant : un nouveau brouillon lié (`replaces`) au contrat actif, qui le terminera à sa
    signature. Le contrat actif ne bouge pas."""
    if contract.status != Contract.Status.ACTIVE:
        raise BusinessError(CONTRACT_NOT_DRAFT)
    values = {
        "plan": contract.plan,
        "start_date": contract.start_date,
        "end_date": contract.end_date,
        "price_per_student": contract.price_per_student,
        "trial_days": contract.trial_days,
        "auto_renew": contract.auto_renew,
    }
    values.update(changes)
    school = School.objects.get(pk=contract.school_id)
    return draft_contract(actor=actor, school=school, replaces=contract, **values)


def publish_legal(*, actor, kind: str, title_fr, title_en, body_fr, body_en) -> LegalDocument:
    """Nouvelle version (numéro suivant) publiée tout de suite : une version ne se corrige pas.
    Les écoles la verront à leur prochaine connexion (`pending_for`)."""
    with transaction.atomic():
        last = (
            LegalDocument.objects.select_for_update().filter(kind=kind).order_by("-version").first()
        )
        document = LegalDocument.objects.create(
            created_by=actor,
            kind=kind,
            version=(last.version + 1) if last else 1,
            published_at=timezone.now(),
            title_fr=title_fr,
            title_en=title_en,
            body_fr=body_fr,
            body_en=body_en,
        )
        audit.record_platform(
            PlatformAction.LEGAL_PUBLISHED,
            document,
            actor=actor,
            after={"kind": kind, "version": document.version},
        )
    return document


def current_documents():
    """Dernière version publiée de chaque texte."""
    latest = {}
    for document in LegalDocument.objects.filter(published_at__isnull=False).order_by("version"):
        latest[document.kind] = document
    return list(latest.values())


def pending_for(school: School) -> list[LegalDocument]:
    """Versions actuelles que l'école n'a pas encore acceptées. Le registre des traitements est
    publié, pas à accepter."""
    accepted = set(
        LegalAcceptance.all_schools.filter(school=school).values_list("document_id", flat=True)
    )
    return [
        d
        for d in current_documents()
        if d.kind != LegalDocument.Kind.REGISTER and d.pk not in accepted
    ]


def accept(*, school: School, user, document: LegalDocument, ip: str | None) -> LegalAcceptance:
    """Acceptation par l'administrateur principal : une seule fois par version (rejouer ne crée
    rien)."""
    if document.published_at is None:
        raise BusinessError(NOT_PUBLISHED)
    with transaction.atomic(), use_school(school):
        acceptance, created = LegalAcceptance.objects.get_or_create(
            school=school,
            document=document,
            defaults={"user": user, "ip": ip, "created_by": user},
        )
        if created:
            audit.record(
                Action.LEGAL_ACCEPTED,
                acceptance,
                actor=user,
                after={"kind": document.kind, "version": document.version},
                label=str(document),
            )
    return acceptance
