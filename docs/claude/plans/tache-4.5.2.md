# Tâche 4.5.2 — Traductions (I2)

**But** : textes du serveur en français (administration, messages d'erreur, PDF, Excel) ; anglais des deux applications relu ; le serveur répond dans la langue de l'interface.

**Constat** : `django.po` — 834 textes, 528 sans traduction, 19 « fuzzy » (devinés par gettext, souvent faux). Champs communs (`id`, `created_at`, `updated_at`, `created_by`, `school`) sans libellé traduisible : en anglais dans l'administration. La langue du serveur suit le navigateur (`Accept-Language`), pas celle choisie dans l'application : un navigateur en anglais reçoit Excel, PDF et messages en anglais avec une interface en français.

**Fichiers**
- `backend/locale/fr/LC_MESSAGES/django.po` / `.mo` : tout traduire, revoir les 19 « fuzzy ».
- `backend/apps/core/models.py` : `verbose_name=_()` sur les champs communs (+ migrations sans SQL, une par app).
- `backend/config/settings/base.py` : `LANGUAGE_COOKIE_NAME` explicite (contrat avec le front).
- `frontend/packages/i18n/src/index.ts` : cookie `django_language` posé au démarrage et au changement de langue → le serveur (API, `<a download>`, PDF) suit l'interface.
- `frontend/packages/i18n/src/locales/en.ts` : relecture (contrôles automatiques : anglais identique au français, accents, mots français ; puis lecture).

**Tests** : serveur — catalogue français complet (aucun vide ni « fuzzy ») et `.mo` compilé à jour ; front — cookie de langue posé (français par défaut, puis anglais).

**Risques** : migrations sur toutes les apps (libellés seulement, aucune requête SQL) ; ne pas traduire le schéma OpenAPI (`--lang en`).
