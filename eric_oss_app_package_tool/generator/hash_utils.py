import hashlib


def sha224(file_path):
    hash_sha224 = hashlib.sha224()
    return hash(file_path, hash_sha224)


def sha256(file_path):
    hash_sha256 = hashlib.sha256()
    return hash(file_path, hash_sha256)


def sha384(file_path):
    hash_sha384 = hashlib.sha384()
    return hash(file_path, hash_sha384)


def sha512(file_path):
    hash_sha512 = hashlib.sha512()
    return hash(file_path, hash_sha512)


def hash(file_path, hash_sha):
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha.update(chunk)
    return hash_sha.hexdigest()


HASH = {'sha-224': lambda file_path: sha224(file_path),
        'sha-256': lambda file_path: sha256(file_path),
        'sha-384': lambda file_path: sha384(file_path),
        'sha-512': lambda file_path: sha512(file_path)}

