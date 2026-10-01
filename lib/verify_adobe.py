#!/usr/bin/env python3
"""Check that Adobe program files are exactly as Adobe signed them (Authenticode).

  verify_adobe.py FILE...          report each file
  verify_adobe.py --scan DIR...    check every signed PE file; exit 1 if any was modified

A file passes when its contents match the signed digest, the signature verifies with the
signer's key, the signer is Adobe, and the certificate chain ends at a trusted root.
"""
import glob
import hashlib
import os
import struct
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

HERE = os.path.dirname(os.path.abspath(__file__))
# Code-signing roots Adobe used that Mozilla's TLS bundle no longer carries (SHA-256).
PINNED_ROOTS = {
    '7431e5f4c3c1ce4690774f0b61e05440883ba9a01ed00ba6abd7806ed3b118cf',  # DigiCert High Assurance EV Root CA
}
OID_SPC_INDIRECT = bytes.fromhex('060a2b060104018237020104')
HASHES = {32: (hashlib.sha256, hashes.SHA256), 20: (hashlib.sha1, hashes.SHA1),
          48: (hashlib.sha384, hashes.SHA384)}
SIGNER_HASH_OIDS = {bytes.fromhex('608648016503040201'): (hashlib.sha256, hashes.SHA256),
                    bytes.fromhex('608648016503040202'): (hashlib.sha384, hashes.SHA384),
                    bytes.fromhex('2b0e03021a'): (hashlib.sha1, hashes.SHA1)}


def tlv(b, i):
    """Return (tag, content_start, end) of the DER element at offset i."""
    tag, n, j = b[i], b[i + 1], i + 2
    if n & 0x80:
        k = n & 0x7f
        n, j = int.from_bytes(b[j:j + k], 'big'), j + k
    return tag, j, j + n


def children(b, start, end):
    out, i = [], start
    while i < end:
        tag, s, e = tlv(b, i)
        out.append((tag, i, s, e))
        i = e
    return out


def pe_parts(data):
    if data[:2] != b'MZ':
        return None
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    if data[pe:pe + 4] != b'PE\0\0':
        return None
    opt = pe + 24
    magic = struct.unpack_from('<H', data, opt)[0]
    checksum, secdir = opt + 64, opt + (112 if magic == 0x20b else 96) + 32
    va, size = struct.unpack_from('<II', data, secdir)
    return checksum, secdir, va, size


def authenticode_digest(data, parts, hash_cls):
    checksum, secdir, va, size = parts
    h = hash_cls()
    h.update(data[:checksum]); h.update(data[checksum + 4:secdir])
    h.update(data[secdir + 8:va]); h.update(data[va + size:])
    return h.digest()


def load_roots():
    roots = []
    for path in ['/etc/ssl/certs/ca-certificates.crt'] + glob.glob(os.path.join(HERE, '..', 'share', 'roots', '*.pem')):
        try:
            with open(path, 'rb') as f:
                certs = x509.load_pem_x509_certificates(f.read())
        except (OSError, ValueError):
            continue
        pinned = 'share' in path
        roots += [c for c in certs if not pinned or c.fingerprint(hashes.SHA256()).hex() in PINNED_ROOTS]
    return roots


def chain_ok(leaf, pool, roots):
    cert, seen = leaf, set()
    for _ in range(6):
        for root in roots:
            if root.subject == cert.issuer:
                try:
                    cert.verify_directly_issued_by(root)
                    return True
                except Exception:
                    pass
        parent = next((c for c in pool if c.subject == cert.issuer and c.serial_number not in seen), None)
        if parent is None:
            return False
        try:
            cert.verify_directly_issued_by(parent)
        except Exception:
            return False
        seen.add(parent.serial_number)
        cert = parent
    return False


def verify(path, roots):
    with open(path, 'rb') as f:
        data = f.read()
    parts = pe_parts(data)
    if not parts:
        return 'not-pe'
    va, size = parts[2], parts[3]
    if not va or va + size > len(data):
        return 'unsigned'
    p7 = data[va + 8:va + size]
    try:
        _, s, e = tlv(p7, 0)                                   # ContentInfo
        _, s, e = tlv(p7, children(p7, s, e)[1][2])            # [0] -> SignedData
        sd = children(p7, s, e)
        eci = children(p7, sd[2][2], sd[2][3])                 # encapContentInfo
        if p7[eci[0][1]:eci[0][3]] != OID_SPC_INDIRECT:
            return 'unknown-signature'
        _, s, e = tlv(p7, eci[1][2])                           # SpcIndirectDataContent
        spc_inner = p7[s:e]
        spc = children(p7, s, e)
        dinfo = children(p7, spc[1][2], spc[1][3])
        signed_digest = p7[dinfo[1][2]:dinfo[1][3]]
        hash_fn, hash_alg = HASHES[len(signed_digest)]
        if authenticode_digest(data, parts, hash_fn) != signed_digest:
            return 'MODIFIED'
        certs_der = next(c for c in sd if p7[c[1]] == 0xa0)
        pool = [x509.load_der_x509_certificate(p7[c[1]:c[3]]) for c in children(p7, certs_der[2], certs_der[3])
                if p7[c[1]] == 0x30]
        signer = children(p7, sd[-1][2], sd[-1][3])[0]
        fields = children(p7, signer[2], signer[3])
        sid = children(p7, fields[1][2], fields[1][3])
        serial = int.from_bytes(p7[sid[1][2]:sid[1][3]], 'big', signed=True)
        attrs = next(c for c in fields if p7[c[1]] == 0xa0)
        attrs_der = b'\x31' + p7[attrs[1] + 1:attrs[3]]
        signature = next(p7[c[2]:c[3]] for c in fields if p7[c[1]] == 0x04)
        alg = p7[fields[2][2]:fields[2][3]]
        sig_fn, sig_alg = next((v for k, v in SIGNER_HASH_OIDS.items() if k in alg), (hash_fn, hash_alg))
        if sig_fn(spc_inner).digest() not in p7[attrs[2]:attrs[3]]:
            return 'BAD-SIGNATURE'
        leaf = next(c for c in pool if c.serial_number == serial)
        leaf.public_key().verify(signature, attrs_der, padding.PKCS1v15(), sig_alg())
    except Exception:
        return 'BAD-SIGNATURE'
    org = [a.value for a in leaf.subject.get_attributes_for_oid(x509.NameOID.ORGANIZATION_NAME)]
    if not any(o.startswith('Adobe') for o in org):
        return 'signed-not-adobe'
    return 'ok' if chain_ok(leaf, pool, roots) else 'BAD-CHAIN'


def main(argv):
    if not argv:
        sys.exit(__doc__)
    roots = load_roots()
    if argv[0] != '--scan':
        for path in argv:
            print(f'{verify(path, roots):18} {path}')
        return 0
    bad, counts = [], {}
    for top in argv[1:]:
        for d, _, files in os.walk(top):
            for name in files:
                if not name.lower().endswith(('.exe', '.dll', '.aex', '.prm', '.8bi', '.8bx', '.ocx', '.sys')):
                    continue
                result = verify(os.path.join(d, name), roots)
                counts[result] = counts.get(result, 0) + 1
                if result.isupper() or result == 'unknown-signature':
                    bad.append((result, os.path.join(d, name)))
    print(' '.join(f'{k}={v}' for k, v in sorted(counts.items())))
    for result, path in bad:
        print(f'{result:18} {path}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
