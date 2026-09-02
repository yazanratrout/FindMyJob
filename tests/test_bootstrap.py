from sqlmodel import Session, select

from findmyjob.db import get_engine
from findmyjob.models.config import AppSettings, Company
from findmyjob.models.enums import CompanyOrigin
from findmyjob.models.profile import Profile
from findmyjob.services.bootstrap import seed


def test_seed_creates_singletons_and_companies(db_session: Session):
    report = seed(db_session)
    db_session.commit()

    assert report.settings_created is True
    assert report.profile_created is True
    assert report.companies_added > 20

    assert db_session.exec(select(AppSettings)).one()
    assert db_session.exec(select(Profile)).one()
    assert len(db_session.exec(select(Company)).all()) == report.companies_added


def test_seed_is_idempotent(db_session: Session):
    seed(db_session)
    db_session.commit()

    with Session(get_engine()) as s2:
        report = seed(s2)
        s2.commit()

    assert report.settings_created is False
    assert report.profile_created is False
    assert report.companies_added == 0


def test_seed_refreshes_seed_companies_but_not_user_companies(db_session: Session):
    seed(db_session)
    user_co = Company(
        name="My Startup",
        normalized_name="my startup",
        origin=CompanyOrigin.USER,
        careers_url="https://example.com",
    )
    db_session.add(user_co)
    db_session.commit()

    with Session(get_engine()) as s2:
        seed(s2)
        s2.commit()
        still_there = s2.exec(select(Company).where(Company.normalized_name == "my startup")).one()
        assert still_there.origin == CompanyOrigin.USER


def test_default_settings_have_weights_and_sources(db_session: Session):
    seed(db_session)
    db_session.commit()
    settings = db_session.exec(select(AppSettings)).one()
    assert abs(sum(settings.weights.values()) - 100) < 1e-6
    assert settings.sources_enabled["ba"] is True  # seed leaves sources on
    assert settings.target_city == "München"
