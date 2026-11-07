from radar_online.tokens import generate_secret, hash_secret


def test_generated_secrets_are_long_url_safe_and_unique():
    secrets = {generate_secret() for _ in range(50)}

    assert len(secrets) == 50
    assert all(len(s) >= 43 and s.replace("-", "").replace("_", "").isalnum() for s in secrets)


def test_hashing_is_stable_and_never_returns_the_secret():
    secret = generate_secret()

    assert hash_secret(secret) == hash_secret(secret)
    assert hash_secret(secret) != secret
    assert len(hash_secret(secret)) == 64


def test_different_secrets_hash_differently():
    assert hash_secret(generate_secret()) != hash_secret(generate_secret())
