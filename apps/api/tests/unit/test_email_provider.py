from app.modules.email.provider import FakeEmailProvider


def test_fake_provider_records_magic_link():
    provider = FakeEmailProvider()
    provider.send_magic_link(
        to="user@example.com",
        link="https://devgate.test/verify?token=abc",
    )
    assert len(provider.sent) == 1
    assert provider.sent[0]["to"] == "user@example.com"
    assert provider.sent[0]["kind"] == "magic_link"
    assert "abc" in provider.sent[0]["link"]


def test_fake_provider_records_otp():
    provider = FakeEmailProvider()
    provider.send_otp(to="user@example.com", code="371829")
    assert provider.sent[-1]["kind"] == "otp"
    assert provider.sent[-1]["code"] == "371829"


def test_fake_provider_clear():
    provider = FakeEmailProvider()
    provider.send_otp(to="a@b.com", code="111111")
    provider.clear()
    assert provider.sent == []
