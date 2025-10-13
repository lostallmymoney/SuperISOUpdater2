from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, ec
from cryptography.exceptions import InvalidSignature
import base64

import mmap

def verify_opnsense_signature(pubkey_bytes, sig_bytes, img_file_path, logging_callback=None):
    """
    Memory-maps the file for signature verification, so the whole file is not loaded into RAM.
    img_file_path: Path or str to the image file.
    """
    pubkey = serialization.load_pem_public_key(pubkey_bytes)
    signature = base64.b64decode(sig_bytes.strip())
    try:
        with open(img_file_path, "rb") as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                image_bytes = mm[:]
                if isinstance(pubkey, ec.EllipticCurvePublicKey):
                    if logging_callback:
                        logging_callback("[verify_signature] Using EC public key for verification.")
                    pubkey.verify(signature, image_bytes, ec.ECDSA(hashes.SHA256()))
                    if logging_callback:
                        logging_callback("[verify_signature] EC signature verified successfully.")
                    return True
                from cryptography.hazmat.primitives.asymmetric import rsa
                if isinstance(pubkey, rsa.RSAPublicKey):
                    if logging_callback:
                        logging_callback("[verify_signature] Using RSA public key for verification.")
                    pubkey.verify(signature, image_bytes, padding.PKCS1v15(), hashes.SHA256())
                    if logging_callback:
                        logging_callback(f"[verify_signature] RSA signature verified successfully for {img_file_path}.")
                        return True
                if logging_callback:
                    logging_callback(f"[verify_signature] Unsupported public key type: {type(pubkey)}")
                return False
    except InvalidSignature:
        if logging_callback:
            logging_callback("[verify_signature] Invalid signature.")
        return False
    except Exception as e:
        if logging_callback:
            logging_callback(f"[verify_signature] Error: {e}")
        return False
