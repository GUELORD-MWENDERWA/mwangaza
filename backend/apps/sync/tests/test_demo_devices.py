"""Appareils de démonstration : le poste de chaque compte fictif qui en a un, sans doublon quand
`make demo` est rejoué."""

import pytest

from apps.accounts.demo import create_demo_accounts
from apps.core.tenancy import use_school
from apps.schools.demo import MAKE_DEMO_NUMBERS, DemoSpace
from apps.schools.models import School
from apps.sync.demo import create_demo_devices
from apps.sync.models import Device
from tests.factories import SchoolFactory

pytestmark = pytest.mark.django_db


def test_each_demo_account_with_a_device_gets_it_once():
    school = SchoolFactory(code="vitrine", environment=School.Environment.DEMO)
    space = DemoSpace(school, "itig", MAKE_DEMO_NUMBERS["itig"], "mot-de-passe-fictif")
    create_demo_accounts([space])

    create_demo_devices([space])
    create_demo_devices([space])

    with use_school(school):
        devices = Device.objects.order_by("user__phone").values_list("user__phone", "label")
        assert list(devices) == [
            ("+243000001005", "PC Caisse · Windows · Edge"),
            ("+243000001006", "PC Secrétariat · Windows"),
        ]
