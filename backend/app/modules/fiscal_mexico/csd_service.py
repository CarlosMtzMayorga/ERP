import re
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Tuple
from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.exceptions import InvalidSignature

from app.core.security import encrypt_csd_key, decrypt_csd_key


class CSDValidationError(Exception):
    """Excepción para errores de validación de certificados CSD del SAT."""
    pass


def extract_sat_serial_number(cert: x509.Certificate) -> str:
    """
    Extrae el número de serie oficial de 20 caracteres del certificado SAT.
    En certificados del SAT, el entero serial_number codifica una cadena ASCII de 20 dígitos.
    """
    serial_int = cert.serial_number
    hex_str = hex(serial_int)[2:]
    if len(hex_str) % 2 != 0:
        hex_str = "0" + hex_str
    try:
        decoded = bytes.fromhex(hex_str).decode("ascii")
        if len(decoded) == 20 and decoded.isalnum():
            return decoded
    except Exception:
        pass
    
    # Si no decodifica directo a 20 chars ascii, convertir entero con ceros a la izquierda
    return str(serial_int).zfill(20)


def extract_subject_rfc_and_name(cert: x509.Certificate) -> Tuple[str, str]:
    """
    Extrae el RFC del titular y la Razón Social / Nombre desde los atributos del Subject.
    OID 2.5.4.45 (x500UniqueIdentifier) generalmente contiene el RFC en certificados del SAT.
    """
    rfc = ""
    legal_name = ""

    # Extraer Common Name (Razón Social)
    common_names = cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
    if common_names:
        legal_name = str(common_names[0].value)

    # Extraer OID 2.5.4.45 (RFC)
    try:
        rfc_attrs = cert.subject.get_attributes_for_oid(x509.oid.ObjectIdentifier("2.5.4.45"))
        if rfc_attrs:
            rfc_candidate = str(rfc_attrs[0].value).strip()
            # El SAT a veces prefija con 'RFC ' o similar
            rfc_match = re.search(r"[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}", rfc_candidate, re.IGNORECASE)
            if rfc_match:
                rfc = rfc_match.group(0).upper()
            else:
                rfc = rfc_candidate.upper()
    except Exception:
        pass

    # Si no se encontró por OID, buscar en Organization Name o Serial Number
    if not rfc:
        for attr in cert.subject:
            val = str(attr.value)
            rfc_match = re.search(r"\b[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}\b", val, re.IGNORECASE)
            if rfc_match:
                rfc = rfc_match.group(0).upper()
                break

    return rfc, legal_name


def validate_and_process_csd(
    cer_bytes: bytes,
    key_bytes: bytes,
    passphrase: str,
    expected_rfc: str = None
) -> Dict[str, Any]:
    """
    Procesa, valida criptográficamente y extrae metadata de un par CSD (.cer y .key).
    
    1. Carga el certificado X.509 (.cer en formato DER o PEM).
    2. Carga y desencripta la llave privada (.key PKCS#8 en formato DER).
    3. Valida correspondencia matemática entre llave pública del certificado y llave privada.
    4. Prueba de firma y verificación digital en memoria (SHA-256 with RSA).
    5. Extrae RFC, Razón Social, No. Serie y Vigencia.
    6. Cifra simétricamente (AES-256) la llave privada y contraseña para resguardo seguro.
    """
    if not cer_bytes:
        raise CSDValidationError("El archivo de certificado (.cer) está vacío.")
    if not key_bytes:
        raise CSDValidationError("El archivo de llave privada (.key) está vacío.")
    if not passphrase:
        raise CSDValidationError("Debe proporcionar la contraseña de la llave privada.")

    # 1. Cargar Certificado (.cer)
    try:
        cert = x509.load_der_x509_certificate(cer_bytes)
    except Exception:
        try:
            cert = x509.load_pem_x509_certificate(cer_bytes)
        except Exception as e:
            raise CSDValidationError(f"Formato de certificado (.cer) inválido o corrupto: {str(e)}")

    # 2. Cargar Llave Privada (.key) con la contraseña
    try:
        private_key = serialization.load_der_private_key(
            key_bytes,
            password=passphrase.encode("utf-8")
        )
    except (ValueError, TypeError) as e:
        raise CSDValidationError(
            "Contraseña incorrecta o la llave privada (.key) no coincide con el formato esperado del SAT."
        )
    except Exception as e:
        raise CSDValidationError(f"Error al procesar la llave privada (.key): {str(e)}")

    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise CSDValidationError("El SAT requiere certificados con criptografía asimétrica RSA.")

    # 3. Validar correspondencia matemática entre llave pública y privada
    cert_pub_key = cert.public_key()
    if not isinstance(cert_pub_key, rsa.RSAPublicKey):
        raise CSDValidationError("La llave pública del certificado no es de tipo RSA.")

    cert_numbers = cert_pub_key.public_numbers()
    key_numbers = private_key.public_key().public_numbers()

    if cert_numbers.n != key_numbers.n or cert_numbers.e != key_numbers.e:
        raise CSDValidationError(
            "Inconsistencia criptográfica: La llave privada (.key) NO corresponde a este certificado (.cer)."
        )

    # 4. Prueba de firma y verificación en memoria (Sanity Check Digital)
    test_message = b"SAT_CFDI_CSD_INTEGRITY_CHECK_ERP_SAAS"
    signature = private_key.sign(
        test_message,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    try:
        cert_pub_key.verify(
            signature,
            test_message,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
    except InvalidSignature:
        raise CSDValidationError("Falla en la prueba de firma digital con el par de llaves.")

    # 5. Extracción de metadata y vigencia
    serial_number = extract_sat_serial_number(cert)
    rfc, legal_name = extract_subject_rfc_and_name(cert)

    # Validar RFC contra empresa si se especificó
    if expected_rfc and rfc and rfc.upper() != expected_rfc.upper():
        raise CSDValidationError(
            f"El RFC del certificado ({rfc}) no coincide con el RFC de la empresa configurada ({expected_rfc})."
        )

    # Fechas de vigencia (UTC)
    try:
        valid_from = cert.not_valid_before_utc
        valid_to = cert.not_valid_after_utc
    except AttributeError:
        valid_from = cert.not_valid_before.replace(tzinfo=timezone.utc)
        valid_to = cert.not_valid_after.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    if now > valid_to:
        status_label = "expired"  # Vencido
    elif (valid_to - now).days <= 30:
        status_label = "expiring_soon"  # Próximo a vencer (<30 días)
    elif now < valid_from:
        status_label = "not_yet_valid"
    else:
        status_label = "active"  # Vigente

    # 6. Cifrado simétrico AES-256 para almacenamiento en reposo
    pem_cert = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    
    # Guardamos la llave privada en formato PEM sin cifrado previo, para cifrarla con AES-256
    pem_key_unencrypted = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    encrypted_key = encrypt_csd_key(pem_key_unencrypted)
    encrypted_passphrase = encrypt_csd_key(passphrase.encode("utf-8"))

    return {
        "rfc": rfc or (expected_rfc or "SIN_RFC"),
        "legal_name": legal_name,
        "certificate_number": serial_number,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "status": status_label,
        "days_remaining": (valid_to - now).days,
        "certificate_pem": pem_cert,
        "encrypted_private_key": encrypted_key,
        "encrypted_passphrase": encrypted_passphrase,
    }


def get_decrypted_private_key(encrypted_private_key_str: str) -> rsa.RSAPrivateKey:
    """
    Desencripta en memoria la llave privada CSD para timbrado o generación de sello digital.
    """
    raw_pem = decrypt_csd_key(encrypted_private_key_str)
    return serialization.load_pem_private_key(raw_pem, password=None)

