import pytest
import datetime
import uuid
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.modules.fiscal_mexico.csd_service import (
    validate_and_process_csd,
    CSDValidationError,
    get_decrypted_private_key
)


def generate_test_csd(passphrase: str = "TestPass123!", rfc: str = "EME200101XYZ"):
    """Generates an in-memory X.509 cert and PKCS#8 DER private key for testing."""
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()

    subject = x509.Name([
        x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "EMPRESA MODELO SA DE CV"),
        x509.NameAttribute(x509.oid.ObjectIdentifier("2.5.4.45"), rfc),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(pub)
        .serial_number(int.from_bytes(b"30001000000500001234", "big"))
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(priv, hashes.SHA256())
    )

    cer_bytes = cert.public_bytes(serialization.Encoding.DER)
    key_bytes = priv.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(passphrase.encode("utf-8"))
    )
    return cer_bytes, key_bytes, priv


def test_csd_validation_success():
    passphrase = "SecretPassword123!"
    cer_bytes, key_bytes, _ = generate_test_csd(passphrase=passphrase, rfc="EME200101XYZ")

    res = validate_and_process_csd(
        cer_bytes=cer_bytes,
        key_bytes=key_bytes,
        passphrase=passphrase,
        expected_rfc="EME200101XYZ"
    )

    assert res["rfc"] == "EME200101XYZ"
    assert res["certificate_number"] == "30001000000500001234"
    assert res["status"] == "active"
    assert res["days_remaining"] > 300
    assert "encrypted_private_key" in res
    assert "encrypted_passphrase" in res

    # Verify decryption
    decrypted_key = get_decrypted_private_key(res["encrypted_private_key"])
    assert isinstance(decrypted_key, rsa.RSAPrivateKey)


def test_csd_invalid_password():
    cer_bytes, key_bytes, _ = generate_test_csd(passphrase="CorrectPassword123")

    with pytest.raises(CSDValidationError) as exc:
        validate_and_process_csd(
            cer_bytes=cer_bytes,
            key_bytes=key_bytes,
            passphrase="WrongPassword!",
            expected_rfc="EME200101XYZ"
        )
    assert "Contraseña incorrecta" in str(exc.value)


def test_csd_mismatched_keypair():
    # Generate two different keypairs
    cer_bytes_1, _, _ = generate_test_csd(passphrase="Pass1", rfc="EME200101XYZ")
    _, key_bytes_2, _ = generate_test_csd(passphrase="Pass2", rfc="EME200101XYZ")

    with pytest.raises(CSDValidationError) as exc:
        validate_and_process_csd(
            cer_bytes=cer_bytes_1,
            key_bytes=key_bytes_2,
            passphrase="Pass2",
            expected_rfc="EME200101XYZ"
        )
    assert "Inconsistencia criptográfica" in str(exc.value)


def test_csd_rfc_mismatch():
    cer_bytes, key_bytes, _ = generate_test_csd(passphrase="Pass1", rfc="XAXX010101000")

    with pytest.raises(CSDValidationError) as exc:
        validate_and_process_csd(
            cer_bytes=cer_bytes,
            key_bytes=key_bytes,
            passphrase="Pass1",
            expected_rfc="EME200101XYZ"
        )
    assert "no coincide con el RFC de la empresa" in str(exc.value)

