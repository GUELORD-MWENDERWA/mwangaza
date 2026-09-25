# Modèle de données

Conventions : toutes les clés primaires sont des UUID v7 (`id`). Tous les modèles ont `created_at`, `updated_at`, `created_by`. **[T]** = hérite de `TenantModel` (champ `school`). **[G]** = global. **[I]** = immuable après création.

## 1. Plateforme et comptes

**School [G]** — `code` (sous-domaine, unique), `name`, `official_name`, `logo`, `primary_color`, `timezone` (défaut `Africa/Lubumbashi`, Goma est en UTC+2), `enabled_currencies` (ex : `["USD","CDF"]`), `default_currency`, `matricule_format`, `status` (`trial`, `active`, `suspended`), `trial_ends_at`, `plan`, `network` (FK optionnelle vers `SchoolNetwork`), `settings` (JSON : règles configurables).

**SchoolNetwork [G]** — promoteur ou coordination : `name`, `kind` (`promoter`, `religious_coordination`).

**User [G]** — `phone` (unique, format E.164, identifiant principal), `email` (optionnel, unique), `first_name`, `last_name`, `middle_name` (post-nom), `password`, `language`, `is_platform_admin`, `totp_enabled`.

**Membership [G]** — `user`, `school`, `roles` (M2M `Role`), `is_active`. Unique (`user`, `school`).

**Role [T]** — `name`, `code`, `is_system` (rôles prédéfinis non supprimables), `permissions` (liste de codes). Les rôles système sont copiés à la création de l'école.

**Device [T]** — `user`, `kind` (`browser`, `reader`), `label`, `prefix` (unique dans l'école, ex : `C1`), `cash_register` (FK optionnelle), `last_seen_at`, `last_receipt_seq`, `revoked_at`.

**AuditLog [T]** **[I]** — `actor`, `device`, `action`, `entity_type`, `entity_id`, `before` (JSON), `after` (JSON), `ip`, `impersonated_by`.

## 2. Organisation scolaire

**AcademicYear [T]** — `name` (« 2026-2027 »), `starts_on`, `ends_on`, `is_current`, `status` (`open`, `closed`).

**Term [T]** — `academic_year`, `name` (P1, P2, Examen 1…), `kind` (`period`, `exam`, `semester`, `trimester`), `parent` (semestre parent), `order`, `starts_on`, `ends_on`.

**Level [T]** — `name` (« 3e »), `cycle` (`primary`, `basic`, `secondary_general`, `secondary_technical`, `higher`, `vocational`), `order`.

**Track [T]** — option : `name` (« Électricité »), `code`.

**ClassGroup [T]** — `academic_year`, `level`, `track` (optionnel), `section` (« A »), `name` calculé (« 3e Électricité A »), `capacity`, `homeroom_teacher` (FK `User`, optionnel).

## 3. Élèves et familles

**Student [G]** — identité qui suit l'élève entre écoles : `platform_id` (lisible, unique), `last_name`, `middle_name`, `first_name`, `sex`, `birth_date`, `birth_place`, `nationality`, `origin_province`, `origin_territory`, `address` (JSON : commune, quartier, avenue, numéro), `photo`, `photo_consent`, `previous_school`, `family`.
Champs V1.1 : `blood_group`, `allergies`, `special_needs`, `religion`, `official_id`.

**Family [G]** — `code` (code famille à 8 caractères, sans caractères ambigus), `primary_user` (FK `User`, rempli à l'activation), `activated_at`.

**Guardian [G]** — contact d'une famille : `family`, `full_name`, `relationship` (père, mère, tuteur…), `phone`, `email`, `is_primary`, `is_emergency_contact`.

**Enrollment [T]** — inscription d'un élève dans une école pour une année : `student`, `academic_year`, `class_group`, `matricule` (unique dans l'école), `status` (`active`, `transferred`, `dropped`, `excluded`, `graduated`), `enrolled_on`, `left_on`.

**StudentImport [T]** — `file`, `mapping` (JSON), `status`, `report` (JSON : erreurs par ligne), `created_count`.

Règles :
- Doublon potentiel : même `last_name` + `first_name` + `birth_date` → avertissement, pas de blocage.
- Le matricule est généré à la création de l'`Enrollment` selon `School.matricule_format`, séquence par école et par année.
- Un parent voit un élève si `student.family.primary_user == user`.

## 4. Finances

**Currency** — constantes (`USD` : 2 décimales, `CDF` : 0 décimale utile).

**ExchangeRate [T]** — `date`, `from_currency`, `to_currency`, `rate` (décimal, 6 chiffres après la virgule), `set_by`. Le taux du jour est le dernier saisi pour la date.

**FeeType [T]** — `name`, `category` (`tuition`, `registration`, `operating`, `ancillary`, `uniform`, `transport`, `canteen`, `extracurricular`, `official_exam`, `custom`), `currency`, `funds_teacher_bonus` (bool), `accounting_code` (compte SYSCOHADA, optionnel), `is_active`.

**FeeRule [T]** — barème : `academic_year`, `fee_type`, portée (`school`, `level`, `track`, `class_group` — un seul rempli ou aucun = toute l'école), `total_amount_minor`, `schedule_kind` (`installments`, `monthly`, `single`).

**InstallmentTemplate [T]** — tranches d'un barème : `fee_rule`, `label` (« 1re tranche »), `amount_minor`, `due_on`, `order`.

**StudentCharge [T]** — ce que doit un élève, créé automatiquement à partir des barèmes applicables quand il est inscrit (et recalculé si le barème change, tant qu'aucun paiement n'est affecté) : `enrollment`, `fee_type`, `label`, `amount_minor`, `currency`, `due_on`, `source` (`rule`, `custom`), `installment_template` (optionnel).

**Discount [T]** — `enrollment`, `fee_type` (optionnel = tous), `kind` (`amount`, `percent`), `value`, `reason_code` (`staff_child`, `sibling`, `scholarship`, `waiver`, `other`), `note`, `approved_by`.

**CashRegister [T]** — caisse : `name`, `code`, `is_active`.

**CashSession [T]** — ouverture d'une caisse par un caissier : `cash_register`, `cashier`, `device`, `opened_at`, `closed_at`.

**Payment [T]** **[I]** — `id` (UUID client), `op_id`, `enrollment`, `cash_session`, `device`, `cashier`, `received_amount_minor`, `received_currency`, `rate_used`, `paid_at` (heure de l'appareil), `synced_at`, `receipt_number` (unique dans l'école), `method` (`cash` en V1 ; `mobile_money`, `bank` plus tard), `note`.

**PaymentAllocation [T]** **[I]** — répartition d'un paiement : `payment`, `student_charge`, `amount_minor` (dans la devise de la charge).

**PaymentCancellation [T]** **[I]** — `payment` (unique), `reason`, `requested_by`, `approved_by`, `approved_at`, `receipt_number`.

**StudentCredit [T]** — surplus : `enrollment`, `amount_minor`, `currency`, `source_payment`, `used_by_payment` (optionnel).

**CashClosing [T]** **[I]** — `cash_session`, par devise : `expected_minor`, `counted_minor`, `difference_minor`, `note`, `closed_by`.

Règles :
- Reste dû d'une charge = `amount_minor` − réductions applicables − allocations de paiements non annulés.
- Répartition par défaut : charges non soldées triées par `due_on` puis `fee_type`. Le caissier peut modifier avant validation.
- Un paiement dans une devise différente de la charge : `allocation = received × rate_used`, arrondi à l'unité de la devise de la charge.
- En retard : `due_on` < aujourd'hui et reste dû > 0.
- Aucune suppression physique dans ce module.

## 5. Notifications et annonces

**Announcement [T]** — `title`, `body`, `audience` (`all_families`, `class_group`, `staff`), `class_group` (optionnel), `published_at`, `attachment`.

**PushSubscription [G]** — `user`, `endpoint`, `keys`, `user_agent`, `created_at`.

## 6. Synchronisation

**SyncOperation [T]** — `op_id` (unique), `device`, `type`, `payload`, `status` (`applied`, `rejected`), `result`, `received_at`.

**ChangeLog [T]** — `seq` (croissant par école), `entity_type`, `entity_id`, `operation` (`upsert`, `delete`), `changed_at`.

## 7. Paie — V1.1 (aperçu)

**Employee [T]** — `user` (optionnel), identité, `function`, `hired_on`, `secope_number`, `secope_status` (`mechanized`, `new_unit`, `unpaid`), `qualifications`.
**Contract [T]** — `employee`, `kind`, `starts_on`, `ends_on`, `base_salary_minor`, `currency`.
**PayrollPeriod [T]** — `month`, `status` (`draft`, `validated`, `paid`).
**PayrollLine [T]** — `period`, `employee`, `base_minor`, `bonuses` (JSON), `teacher_bonus_minor`, `advances_deducted_minor`, `other_deductions` (JSON), `net_minor`, `currency`.
**SalaryAdvance [T]** — `employee`, `amount_minor`, `granted_on`, `repayment_plan`.

## 8. Permissions V1.0

| Code | Directeur | Comptable | Caissier | Secrétaire | Promoteur |
|---|:-:|:-:|:-:|:-:|:-:|
| `school.configure` | ✔ | | | | |
| `roles.manage` | ✔ | | | | |
| `students.view` | ✔ | ✔ | ✔ | ✔ | ✔ |
| `students.edit` | ✔ | | | ✔ | |
| `students.import` | ✔ | | | ✔ | |
| `finance.configure_fees` | ✔ | ✔ | | | |
| `finance.set_exchange_rate` | ✔ | ✔ | | | |
| `finance.grant_discount` | ✔ | ✔ | | | |
| `finance.collect_payment` | | ✔ | ✔ | | |
| `finance.request_cancellation` | | ✔ | ✔ | | |
| `finance.approve_cancellation` | ✔ | ✔ | | | |
| `finance.close_register` | | ✔ | ✔ | | |
| `finance.view_reports` | ✔ | ✔ | | | ✔ |
| `announcements.publish` | ✔ | | | ✔ | |
| `audit.view` | ✔ | | | | ✔ |
