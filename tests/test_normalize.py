from findmyjob.normalize import normalize_company_name, normalize_title, slugify


def test_normalize_company_name_strips_legal_suffix_and_accents():
    assert normalize_company_name("Celonis SE") == "celonis"
    assert normalize_company_name("Müller & Co. GmbH") == "mueller and co"
    assert normalize_company_name("FlixBus GmbH") == "flixbus"


def test_normalize_company_name_is_stable():
    a = normalize_company_name("  BMW  Group AG ")
    b = normalize_company_name("BMW Group")
    assert a == b == "bmw group"


def test_normalize_title_removes_gender_markers():
    assert normalize_title("Werkstudent (m/w/d) Data Science") == "werkstudent data science"
    assert normalize_title("Working Student - Backend (f/m/x)") == "working student backend"


def test_slugify():
    assert slugify("Isar Aerospace GmbH") == "isar-aerospace-gmbh"
