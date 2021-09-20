import argparse
import secrets
import string
from collections import Counter
import hashlib
import getpass

import keyring
import xerox
from Crypto.Cipher import AES
from tqdm import trange, tqdm


storage_bytes = 256
key_bits = 256
default_password_abc = " ".join([string.ascii_lowercase, string.ascii_uppercase, string.digits, "_@#$.!+-="])
default_password_len = 15
tag1 = "a919bf9b298b14a1893b71954520a7fa1bdc2c67903979bd0db9824039bd71506d91648bfd3083708ebb85261c82824544fa508ad90990b503e474d20c1889b4"
tag2 = "c97ab2ad0555b0d0f2613f4b144cd9ec9116be3cc377aca9b9754094be91c7431f0c10363284a11566219a467f579772d1e16654a62b12e77dabd25ad3842865"
default_storage_key = bytearray.fromhex("601a6d376f80a6a7fc2a0f0bf17fce76303b37069c8830eca622406d38361499")


parser = argparse.ArgumentParser(description='Password manager. Generates passwords and, optionally, stores them in the system keyring.',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

subparsers = parser.add_subparsers(help='a command. Add -h for command help', dest="command")
parser_gen = subparsers.add_parser('gen', help='generate a random password. Do not store it', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser_gen.add_argument('--nchars', metavar="N", type=int, default=default_password_len, help='number of characters for generated password')
parser_gen.add_argument("--alphabet", metavar="CHARS", type=str, default=default_password_abc,
                    help="alphabet for password generation. Enclose in quotes. Separate required groups (like uppercase and lowercase letters) with spaces")

parser_gen.add_argument("--print", action="store_true", help="show the password on the screen instead of copying it into clipboard")

parser_store = subparsers.add_parser('store', help='generate (or enter) and store a password', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser_store.add_argument("key", metavar="KEY", type=str, help="the key (e.g., website name) under which the password will be stored")
parser_store.add_argument("--secret", action="store_true", help="use a secret storage. You will be asked for the storage password")
parser_store.add_argument("--hidden", action="store_true", help="hide this key from the list of stored keys returned by 'list' command")
parser_store.add_argument("--input", action="store_true", help="input a password for storage from keyboard instead of generating it")
parser_store.add_argument('--nchars', metavar="N", type=int, default=default_password_len, help='number of characters for generated password')
parser_store.add_argument("--alphabet", metavar="CHARS", type=str, default=default_password_abc,
                    help="alphabet for password generation. Enclose in quotes. Separate required groups (like uppercase and lowercase letters) with spaces")

parser_store.add_argument("--output", action="store_true", help="output the generated password")
parser_store.add_argument("--print", action="store_true", help="show the password on the screen instead of copying it into clipboard")

parser_get = subparsers.add_parser('get', help='retrieve a stored password', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser_get.add_argument("key", metavar="KEY", type=str, help="the key (e.g., website name) under which the password was stored")
parser_get.add_argument("--secret", action="store_true", help="use a secret storage. You will be asked for the storage password")
parser_get.add_argument("--print", action="store_true", help="show the password on the screen instead of copying it into clipboard")

parser_list = subparsers.add_parser('list', help='list visible keys for which passwords are stored', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser_list.add_argument("--secret", action="store_true", help="use a secret storage. You will be asked for the storage password")

parser_nuke = subparsers.add_parser('nuke', help='delete all storages', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser_backup = subparsers.add_parser('backup', help='save all storages into an encrypted file', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser_backup.add_argument("file", metavar="FILE", type=str, help="backup file name")

parser_restore = subparsers.add_parser('restore', help='restore storages from a backup file (nukes current storage)', 
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser_restore.add_argument("file", metavar="FILE", type=str, help="backup file name")

args = parser.parse_args()


def gen_password():
    abcs = list(map(frozenset, args.alphabet.split(" ")))
    abc = list(frozenset.union(*abcs))
    char_part = {}
    for i, chars in enumerate(abcs):
        for c in chars:
            char_part[c] = i

    assert args.nchars >= 1, "wrong password length selected"
    assert args.nchars >= len(abcs) * 2, "requested password length is too short for the chosen alphabet"
    while True:
        candidate = ''.join(secrets.choice(abc) for _ in range(args.nchars))
        part_counts = Counter(char_part[c] for c in candidate)
        if all(part_counts[p] >= 2 for p in range(len(abcs))):
            return candidate


def output(pw):
    if args.print:
        print(pw)
    else:
        xerox.copy(pw)
        print("Your password is copied to the clipboard")


def key_from_password(pw: str, salt: bytes):
    return hashlib.scrypt(pw.encode("utf8"), salt=salt, dklen=key_bits // 8, n=2 ** 20, r = 8, p = 1, maxmem=2 * 10 ** 9)


def random_key():
    return secrets.token_bytes(key_bits // 8)


def add_keys_to_index(keys):
    assert all(len(k) == 128 for k in keys)
    try:
        existing_keys = keyring.get_password(tag1, tag2)
        assert existing_keys is not None
    except:
        existing_keys = ""

    existing_keys_list = [existing_keys[i:i + 128] for i in range(0, len(existing_keys), 128)]
    existing_keys_list.extend(keys)
    existing_keys_list.sort()
    keyring.set_password(tag1, tag2, "".join(existing_keys_list))


def store(key, value):
    assert len(key) == 128
    keyring.set_password(tag1, key, value)
    add_keys_to_index([key])


def store_padded(tag, info: bytes):
    assert len(info) <= storage_bytes, "storage capacity exceeded (password or key too long?)"
    if len(info) < storage_bytes:
        info += secrets.token_bytes(storage_bytes - len(info))

    store(tag, info.hex())


def get_padded(tag, size_bytes):
    return bytearray.fromhex(keyring.get_password(tag1, tag))[:size_bytes]


def store_encrypted(tag, info, key):
    info_len = len(info).to_bytes(4, byteorder="little")
    padding_len = storage_bytes - len(info) - 36
    if padding_len > 0:
        message = info_len + info + secrets.token_bytes(padding_len)
    else:
        message = info_len + info

    store_padded(tag, encrypt(message, key))


def get_encrypted(tag, key):
    cipher_data = get_padded(tag, storage_bytes)
    message = decrypt(cipher_data, key)
    payload_len = int.from_bytes(message[:4], byteorder="little")
    assert payload_len >= 0
    assert len(message) >= 4 + payload_len
    return message[4:4 + payload_len]


def encrypt(message, key):
    cipher = AES.new(key, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(message)
    return cipher.nonce + tag + ciphertext


def decrypt(cipher_data, key):
    nonce = cipher_data[:16]
    tag = cipher_data[16:32]
    ciphertext = cipher_data[32:]
    cipher = AES.new(key, AES.MODE_EAX, nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)


def keyed_hash(data, key):
    h = hashlib.blake2b(key=key, digest_size=64)
    h.update(data)
    return h.hexdigest()


def store_encrypted_by_key(storage_key, data_to_store, encryption_key):
    store_encrypted(keyed_hash(storage_key, encryption_key), data_to_store, encryption_key)


def get_encrypted_by_key(storage_key, encryption_key):
    try:
        return get_encrypted(keyed_hash(storage_key, encryption_key), encryption_key)
    except:
        raise RuntimeError("Storage is damaged")


def init_storage(storage_key):
    master_key = random_key()
    store_encrypted_by_key(b"master_key", master_key, storage_key)
    store_encrypted_by_key(b"num_visible_keys", (0).to_bytes(4, byteorder="little"), master_key)
    store_encrypted_by_key(b"salt", secrets.token_bytes(16), master_key)


def add_password(key: str, password: str, master_key, visible):
    salt = get_encrypted_by_key(b"salt", master_key)
    key_derived = key_from_password(key, salt)
    already_present = False
    try:
        get_encrypted_by_key(key_derived, master_key)
        already_present = True
        print("A password is already present for this key. Replacing it")
    except:
        pass

    store_encrypted_by_key(key_derived, password.encode("utf8"), master_key)
    if visible and not already_present:
        num_visible_keys = int.from_bytes(get_encrypted_by_key(b"num_visible_keys", master_key), byteorder="little")
        store_encrypted_by_key(f"key#{num_visible_keys}".encode("utf8"), key.encode("utf8"), master_key)
        store_encrypted_by_key(b"num_visible_keys", (num_visible_keys + 1).to_bytes(4, byteorder="little"), master_key)


def list_keys(master_key):
    print("Visible keys in this storage:")
    num_visible_keys = int.from_bytes(get_encrypted_by_key(b"num_visible_keys", master_key), byteorder="little")
    for i in range(num_visible_keys):
        try:
            key = get_encrypted_by_key(f"key#{i}".encode("utf8"), master_key).decode("utf8")
            print(key)
        except:
            pass


def get_password(key: str, master_key):
    salt = get_encrypted_by_key(b"salt", master_key)
    key_derived = key_from_password(key, salt)
    try:
        return get_encrypted_by_key(key_derived, master_key).decode("utf8")
    except:
        raise RuntimeError("Password for this key not found")


def retrieve_master_key(read_only=False):
    try:
        default_key = get_encrypted_by_key(b"master_key", default_storage_key)
    except:
        if read_only:
            raise RuntimeError("Storage not initialized")

        print("Initializing storage for first use")
        init_storage(default_storage_key)
        default_key = get_encrypted_by_key(b"master_key", default_storage_key)
        num_random_pairs = 30 + secrets.randbelow(30)
        random_keys = []
        for _ in trange(num_random_pairs):
            rnd_key = secrets.token_hex(64)
            keyring.set_password(tag1, rnd_key, secrets.token_hex(storage_bytes))
            random_keys.append(rnd_key)

        add_keys_to_index(random_keys)

    if not args.secret:
        print("Using default, not password protected storage. The passwords are visible to other programs ran by user")
        return default_key

    storage_password = getpass.getpass("Enter storage password: ")
    salt = get_encrypted_by_key(b"salt", default_key)
    storage_key = key_from_password(storage_password, salt)
    try:
        return get_encrypted_by_key(b"master_key", storage_key)
    except:
        if read_only:
            raise RuntimeError("Secret storage with this password was not found")

        answer = input("Secret storage with this password was not found. Would you like to create it? [y/n]: ")
        if answer == "" or answer.lower()[0] != "y":
            exit(1)

        storage_password2 = getpass.getpass("Confirm new storage password: ")
        if storage_password != storage_password2:
            print("Storage passwords differ")
            exit(1)

        init_storage(storage_key)
        return get_encrypted_by_key(b"master_key", storage_key)
    

try:
    if args.command == "gen":
        output(gen_password())
    elif args.command == "store":
        master_key = retrieve_master_key()
        if args.input:
            password = getpass.getpass("Enter password to store for the given key: ")
        else:
            password = gen_password()
            print("Random password was generated")

        add_password(args.key, password, master_key, not args.hidden)
        print("Password stored")
        if args.output and not args.input:
            output(password)
    elif args.command == "get":
        master_key = retrieve_master_key(read_only=True)
        password = get_password(args.key, master_key)
        output(password)
    elif args.command == "list":
        master_key = retrieve_master_key(read_only=True)
        list_keys(master_key)
    elif args.command == "nuke":
        code = ''.join(secrets.choice(string.ascii_letters) for _ in range(6))
        print(f"This will delete all storages (default and secret). Recovery will not be possible. Enter the code {' '.join(list(code))} (without spaces) to confirm")
        confirmation = input("Nuclear code: ")
        assert confirmation == code, "Nuclear strike not confirmed"
        print("Nuclear strike confirmed")
        init_storage(default_storage_key)
        print("Storages erased")
    elif args.command == "backup":
        password = getpass.getpass("Create a password for the backup: ")
        password_confirmation = getpass.getpass("Confirm the password for the backup: ")
        assert password == password_confirmation, "Backup password not confirmed"

        filename = args.file
        with open(filename, "wb") as f:
            try:
                stored_keys = keyring.get_password(tag1, tag2)
                assert stored_keys is not None
            except:
                raise RuntimeError("Storage not initialized")

            assert len(stored_keys) % 128 == 0, "Storage is damaged"
            existing_keys_list = [stored_keys[i:i + 128] for i in range(0, len(stored_keys), 128)]
            data = {}
            for key in tqdm(existing_keys_list, desc="retrieving storage"):
                try:
                    data[key] = keyring.get_password(tag1, key)
                except:
                    print("Warning: could not retrieve a part of stored data")
            
            data = "\n".join(f"{key}\t{value}" for key, value in data.items())
            salt = secrets.token_bytes(16)
            encryption_key = key_from_password(password, salt)
            encrypted_data = encrypt(data.encode("utf8"), encryption_key)
            f.write(salt)
            f.write(encrypted_data)
    elif args.command == "restore":
        print("Restoring a backup will delete the current storage. Recovery will not be possible. Type 'Yes.' without quotes to continue")
        confirmation = input("Confirm restore? ")
        assert confirmation == "Yes.", "Restore is not confirmed"
        with open(args.file, "rb") as f:
            salt = f.read(16)
            encrypted_data = f.read()

        password = getpass.getpass("Enter the backup file password: ")
        encryption_key = key_from_password(password, salt)
        data = decrypt(encrypted_data, encryption_key).decode("utf8")
        data = dict(kv.split("\t") for kv in data.split("\n"))
        for key, value in tqdm(data.items(), total=len(data), desc="restoring backup"):
            keyring.set_password(tag1, key, value)

        keyring.set_password(tag1, tag2, "")
        add_keys_to_index(data.keys())
    else:
        parser.print_help()

except xerox.base.XclipNotFound:
    print("Please install xclip")
    exit(1)
except Exception as e:
    print(f"Error: {e}")
    exit(1)
finally:
    pass
