from app.utils.crypto import decrypt_secret, encrypt_secret, mask_secret


def test_encrypt_roundtrip():
    ct = encrypt_secret("TEST_NOT_A_SECRET")
    assert ct != "TEST_NOT_A_SECRET"
    assert decrypt_secret(ct) == "TEST_NOT_A_SECRET"


def test_decrypt_none_and_garbage():
    assert decrypt_secret(None) is None
    assert decrypt_secret("not-a-token") is None


def test_mask():
    assert mask_secret("TEST_NOT_A_SECRET") == "TES****CRET"
    assert mask_secret("short") == "****"
    assert mask_secret("") == ""
