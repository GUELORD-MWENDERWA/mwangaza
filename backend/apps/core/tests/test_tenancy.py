"""Isolation des écoles au niveau des modèles.

Une école ne peut ni lire, ni modifier, ni supprimer, ni relier les données d'une autre, même par
erreur de code.
"""

import pytest

from apps.core.tenancy import CrossSchoolError, SchoolNotSetError, get_current_school, use_school
from tests.sample.models import Comment, Note

pytestmark = pytest.mark.django_db


@pytest.fixture
def note_a(school):
    with use_school(school):
        return Note.objects.create(text="note de l'école A")


@pytest.fixture
def note_b(other_school):
    with use_school(other_school):
        return Note.objects.create(text="note de l'école B")


# École courante


def test_use_school_sets_and_restores_current_school(school, other_school):
    assert get_current_school() is None
    with use_school(school):
        assert get_current_school() == school
        with use_school(other_school):
            assert get_current_school() == other_school
        assert get_current_school() == school
    assert get_current_school() is None


def test_use_school_restores_after_an_error(school):
    with pytest.raises(RuntimeError), use_school(school):
        raise RuntimeError("erreur pendant le travail")

    assert get_current_school() is None


# Lecture


def test_reading_without_school_raises():
    with pytest.raises(SchoolNotSetError):
        Note.objects.all()


def test_reading_related_rows_without_school_raises(note_a):
    with pytest.raises(SchoolNotSetError):
        list(note_a.comments.all())


def test_school_sees_only_its_own_rows(school, other_school, note_a, note_b):
    with use_school(school):
        assert list(Note.objects.all()) == [note_a]
        assert Note.objects.count() == 1
    with use_school(other_school):
        assert list(Note.objects.all()) == [note_b]


def test_school_cannot_get_a_row_of_another_school(other_school, note_a):
    with use_school(other_school), pytest.raises(Note.DoesNotExist):
        Note.objects.get(pk=note_a.pk)


def test_related_rows_are_limited_to_current_school(school, other_school, note_a):
    with use_school(school):
        comment = Comment.objects.create(note=note_a, text="commentaire A")
        assert list(note_a.comments.all()) == [comment]
    with use_school(other_school):
        assert list(note_a.comments.all()) == []


def test_all_schools_manager_sees_every_school(note_a, note_b):
    assert set(Note.all_schools.all()) == {note_a, note_b}


# Création


def test_new_row_takes_the_current_school(school):
    with use_school(school):
        note = Note.objects.create(text="nouvelle")

    assert note.school == school


def test_creating_without_any_school_raises(db):
    with pytest.raises(SchoolNotSetError):
        Note(text="sans école").save()


def test_explicit_school_without_current_school_is_allowed(school):
    # Tâches de la plateforme (super-admin, données de démonstration) : l'école est donnée.
    note = Note(school=school, text="explicite")
    note.save()

    assert Note.all_schools.get(pk=note.pk).school == school


def test_school_cannot_create_a_row_for_another_school(school, other_school):
    with use_school(other_school), pytest.raises(CrossSchoolError):
        Note(school=school, text="intrusion").save()

    assert not Note.all_schools.filter(school=school).exists()


def test_bulk_create_fills_and_checks_the_school(school, other_school):
    with use_school(school):
        notes = Note.objects.bulk_create([Note(text="1"), Note(text="2")])
    assert {note.school for note in notes} == {school}

    with use_school(other_school), pytest.raises(CrossSchoolError):
        Note.objects.bulk_create([Note(text="3"), Note(school=school, text="intrusion")])
    assert Note.all_schools.count() == 2


def test_bulk_create_without_school_raises(db):
    with pytest.raises(SchoolNotSetError):
        Note.all_schools.bulk_create([Note(text="sans école")])


# Modification et suppression


def test_school_cannot_update_a_row_of_another_school(school, other_school, note_a):
    note = Note.all_schools.get(pk=note_a.pk)
    note.text = "modifiée par B"

    with use_school(other_school), pytest.raises(CrossSchoolError):
        note.save()
    with use_school(other_school):
        assert Note.objects.filter(pk=note_a.pk).update(text="modifiée par B") == 0

    assert Note.all_schools.get(pk=note_a.pk).text == "note de l'école A"


def test_school_can_update_its_own_row(school, note_a):
    with use_school(school):
        note = Note.objects.get(pk=note_a.pk)
        note.text = "corrigée"
        note.save()

    assert Note.all_schools.get(pk=note_a.pk).text == "corrigée"


def test_row_cannot_move_to_another_school(school, other_school, note_a):
    # Un transfert d'élève est une copie (Q10), jamais un déplacement.
    note = Note.all_schools.get(pk=note_a.pk)
    note.school = other_school

    with use_school(other_school), pytest.raises(CrossSchoolError):
        note.save()
    with pytest.raises(CrossSchoolError):
        note.save()

    assert Note.all_schools.get(pk=note_a.pk).school == school


def test_school_cannot_delete_a_row_of_another_school(other_school, note_a):
    with use_school(other_school), pytest.raises(CrossSchoolError):
        note_a.delete()
    with use_school(other_school):
        assert Note.objects.filter(pk=note_a.pk).delete()[0] == 0

    assert Note.all_schools.filter(pk=note_a.pk).exists()


def test_school_can_delete_its_own_row(school, note_a):
    with use_school(school):
        note_a.delete()

    assert not Note.all_schools.filter(pk=note_a.pk).exists()


# Liens entre lignes (clés étrangères)


def test_row_cannot_point_to_a_loaded_row_of_another_school(other_school, note_a):
    with use_school(other_school), pytest.raises(CrossSchoolError):
        Comment.objects.create(note=note_a, text="lien vers A")

    assert not Comment.all_schools.exists()


def test_row_cannot_point_to_a_row_of_another_school_by_id(other_school, note_a):
    with use_school(other_school), pytest.raises(CrossSchoolError):
        Comment.objects.create(note_id=note_a.pk, text="lien vers A par identifiant")

    assert not Comment.all_schools.exists()


def test_explicit_school_cannot_point_to_another_school(other_school, note_a):
    with pytest.raises(CrossSchoolError):
        Comment(school=other_school, note=note_a, text="lien vers A").save()


def test_bulk_create_checks_links(other_school, note_a):
    with use_school(other_school), pytest.raises(CrossSchoolError):
        Comment.objects.bulk_create([Comment(note_id=note_a.pk, text="lien vers A")])


def test_row_can_point_to_a_row_of_the_same_school(school, note_a):
    with use_school(school):
        by_object = Comment.objects.create(note=note_a, text="même école")
        by_id = Comment.objects.create(note_id=note_a.pk, text="même école, par identifiant")

    assert by_object.school == by_id.school == school


# Identifiants


def test_rows_get_a_uuid7_primary_key(note_a):
    assert note_a.pk.version == 7
    assert note_a.created_at is not None
    assert note_a.updated_at is not None
