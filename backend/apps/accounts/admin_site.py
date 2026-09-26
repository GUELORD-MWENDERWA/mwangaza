"""Administration Django : réservée au super-admin, **avec la double authentification**.

Connexion en étapes, avec les mêmes fonctions que l'API (`login.py`) et la même limitation des
tentatives : numéro et mot de passe → code de l'application ou code de secours (jamais
d'« appareil de confiance » ici) → nouveau mot de passe si le mot de passe est provisoire →
activation de la double authentification à la première connexion (clé à saisir dans
l'application, 8 codes de secours affichés une fois). Un compte qui n'est pas super-admin est
refusé dès le mot de passe, avec la même réponse qu'un mauvais mot de passe.
"""

from django import forms
from django.contrib import admin
from django.contrib.auth import logout
from django.contrib.auth.forms import SetPasswordForm
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from rest_framework.exceptions import APIException

from apps.accounts import login, services, totp
from apps.accounts.login import MFA_SESSION_KEY, Step
from apps.core.errors import BusinessError

ADMIN_INVALID_CREDENTIALS = _(
    "Wrong phone number or password, or not a Mwangaza administration account."
)


class PasswordStepForm(forms.Form):
    phone = forms.CharField(
        label=_("Phone"),
        max_length=64,
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class CodeStepForm(forms.Form):
    code = forms.CharField(
        label=_("Code"),
        max_length=20,
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "one-time-code"}),
    )


_INTROS = {
    Step.PASSWORD: None,
    Step.TOTP: _("Enter the code of your authentication application, or a recovery code."),
    Step.NEW_PASSWORD: _("Your password is temporary: choose your own (10 characters or more)."),
    Step.TOTP_SETUP: _(
        "Two-factor authentication is required for the administration. In your authentication "
        "application (Google Authenticator, Aegis…), add an account with the key below, then "
        "enter the code it shows."
    ),
}


class PlatformAdminSite(admin.AdminSite):
    site_header = _("Mwangaza administration")
    site_title = _("Mwangaza administration")
    index_title = _("Platform")

    def has_permission(self, request) -> bool:
        """Super-admin actif, session passée par la double authentification."""
        return super().has_permission(request) and bool(request.session.get(MFA_SESSION_KEY))

    @method_decorator(never_cache)
    @method_decorator(csrf_protect)
    def login(self, request, extra_context=None):
        next_url = self._next_url(request)
        if request.user.is_authenticated:
            if self.has_permission(request):
                return redirect(next_url)
            # Connecté sans accès à l'administration (ou sans double authentification) : on
            # recommence la connexion.
            logout(request)
        step = login.current_step(request)
        form = self._form(request, step, request.POST if request.method == "POST" else None)
        context = {}
        if request.method == "POST" and form.is_valid():
            try:
                done = self._run(request, step, form, context)
            except BusinessError as exc:
                form.add_error(None, self._message(exc))
            except APIException as exc:  # trop d'essais ratés
                form.add_error(None, str(exc.detail))
            else:
                if done and not context.get("recovery_codes"):
                    return redirect(next_url)
                if not done:
                    return redirect(request.get_full_path())
        if step == Step.TOTP_SETUP and not context.get("recovery_codes"):
            context["secret"] = self._setup_key(request)
        return TemplateResponse(
            request,
            "admin/accounts/login.html",
            {
                **self.each_context(request),
                "title": _("Log in"),
                "app_path": request.get_full_path(),
                "next": next_url,
                "form": form,
                "intro": _INTROS[step],
                **context,
                **(extra_context or {}),
            },
        )

    def _next_url(self, request) -> str:
        next_url = request.POST.get("next") or request.GET.get("next")
        safe = next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        )
        return next_url if safe else reverse("admin:index", current_app=self.name)

    def _form(self, request, step: Step, data) -> forms.Form:
        if step == Step.PASSWORD:
            return PasswordStepForm(data)
        if step == Step.NEW_PASSWORD:
            return SetPasswordForm(login.pending_user(request), data)
        return CodeStepForm(data)

    def _message(self, exc: BusinessError) -> str:
        if exc.error == login.INVALID_CREDENTIALS:
            return str(ADMIN_INVALID_CREDENTIALS)
        return str(exc.error.detail)

    def _setup_key(self, request) -> str:
        try:
            secret = login.totp_setup_secret(request)
        except BusinessError:
            secret = totp.new_secret()
            login.start_totp_setup(request, secret)
        return " ".join(secret[i : i + 4] for i in range(0, len(secret), 4))

    def _run(self, request, step: Step, form, context: dict) -> bool:
        """Une étape de la connexion ; True quand le compte est connecté."""
        data = form.cleaned_data
        if step == Step.PASSWORD:
            return login.log_in(request, data["phone"], data["password"], admin_only=True) == (
                Step.DONE
            )
        user = login.expect(request, step)
        if step == Step.TOTP:
            with login.counting_failures(request, user):
                method = services.verify_second_factor(user, data["code"])
            return login.second_factor_passed(request, user, method) == Step.DONE
        if step == Step.NEW_PASSWORD:
            services.change_password(user, data["new_password1"])
            return login.advance(request, user) == Step.DONE
        # Activation : codes de secours affichés une seule fois, sur cette page.
        codes = services.enable_totp(user, login.totp_setup_secret(request), data["code"])
        login.end_totp_setup(request)
        context["recovery_codes"] = codes
        return login.second_factor_passed(request, user, "totp") == Step.DONE
