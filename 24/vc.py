import sys
import os
import time
import shutil
import stat
import pathlib


usage = """Simple(c) version control system. Usage:
python vc.py create <repo>  .   .   .   .   .   .   .   .   .   .   .   . Create empty repository at path.
python vc.py commit <repo> <file> <message> [num_revisions_to_keep] .   . Commit a file to repo. File must be new or locked.
                                                                          Use relative (to the workspace root) path for the file.
                                                                          If the file doesn't exist, it will be deleted from repo.
                                                                          File will be unlocked. Optionally, the max number of
                                                                          revisions to keep in the repo can be set.
python vc.py lock <repo> <file>     .   .   .   .   .   .   .   .   .   . Lock the file to enable changes.
python vc.py checkout <repo> [file [version_number]]    .   .   .   .   . Retrieve latest revisions of all files.
                                                                          If a file is specified, checkout only that file.
                                                                          If a version number is specified, checkout this version.
python vc.py log <repo> <file>      .   .   .   .   .   .   .   .   .   . Print version log of the file."""


class UsageError(Exception):
    pass


def load_log(file_repo_path):
    try:
        with open(os.path.join(file_repo_path, "log"), "r") as f:
            versions = []
            for line in f:
                fields = line.strip().split("\t")
                assert len(fields) == 2
                fields[1] = int(fields[1])
                versions.append(fields)
            
            return versions
    except Exception:
        raise RuntimeError("Repository is broken")


def make_readonly(filename):
    mode = os.stat(filename).st_mode
    ro_mask = 0o777 ^ (stat.S_IWRITE | stat.S_IWGRP | stat.S_IWOTH)
    os.chmod(filename, mode & ro_mask)


def make_writable(file):
    mode = os.stat(file).st_mode
    os.chmod(file, mode | stat.S_IWRITE)


def checkout(file_repo_path, file, need_version):
    versions = load_log(file_repo_path)
    latest_version = len(versions) - 1
    if need_version is None:
        need_version = latest_version

    assert need_version <= latest_version, f"wrong version requested. Latest version: {latest_version}"
    ver_file = os.path.join(file_repo_path, str(need_version))
    ver_time = versions[need_version][1]
    if not os.path.exists(file):
        if not os.path.exists(ver_file):
            print(f"[{file}] v. {need_version} is deleted from repository and does not exist in working copy")
        else:
            shutil.copy(ver_file, file)
            os.utime(file, (ver_time, ver_time))
            make_readonly(file)
            print(f"[{file}] v. {need_version} is checked out")
    else:
        mode = os.stat(file).st_mode
        if (mode & stat.S_IWRITE) and os.path.exists(os.path.join(file_repo_path, "lock")):
            print(f"[{file}] is locked. Skipping checkout")
            return

        if not os.path.exists(ver_file):
            print(f"[{file}] v. {need_version} is deleted from repository; deleting it from working copy")
            make_writable(file)
            os.remove(file)
        else:
            mod_time = os.path.getmtime(file)
            if mod_time == ver_time:
                print(f"[{file}] v. {need_version} is up to date")
            else:
                make_writable(file)
                os.remove(file)                
                shutil.copy(ver_file, file)
                os.utime(file, (ver_time, ver_time))
                make_readonly(file)
                print(f"[{file}] v. {need_version} is checked out")


def all_subfolders(folder):
    return [f.path for f in os.scandir(folder) if f.is_dir()]


def checkout_recursive(repo_folder, working_copy_path):
    repo_subs = all_subfolders(repo_folder)
    if not repo_subs:
        checkout(repo_folder, working_copy_path, None)
        return

    if not os.path.exists(working_copy_path):
        os.makedirs(working_copy_path)
    else:
        assert os.path.isdir(working_copy_path), f"[{working_copy_path}] is a folder in repository, but something else in working copy"

    for repo_sub in repo_subs:
        working_copy_sub = os.path.join(working_copy_path, os.path.basename(repo_sub))
        checkout_recursive(repo_sub, working_copy_sub)


try:
    if len(sys.argv) < 3:
        raise UsageError()

    command = sys.argv[1]
    repo_folder = sys.argv[2]
    if command == "create":
        if len(sys.argv) != 3:
            raise UsageError()

        os.mkdir(repo_folder)
        print(f"New empty repository [{repo_folder}] has been created.")
    elif command == "commit":
        if not (5 <= len(sys.argv) <= 6):
            raise UsageError

        assert os.path.exists(repo_folder) and os.path.isdir(repo_folder), "missing/wrong repository folder"
        file, message = sys.argv[3:5]
        assert not os.path.exists(file) or os.path.isfile(file), f"not a regular file: [{file}]"
        num_revisions_to_keep = -1
        if len(sys.argv) == 6:
            num_revisions_to_keep = int(sys.argv[5])
            assert num_revisions_to_keep > 0, "wrong number of revisions to keep"

        file_repo_path = os.path.join(repo_folder, file)
        lock_file = os.path.join(file_repo_path, "lock")
        if not os.path.exists(file_repo_path):
            if not os.path.exists(file):
                raise RuntimeError(f"[{file}] does not exist in working copy and in repository")

            if num_revisions_to_keep == -1:
                num_revisions_to_keep = 10

            print(f"Adding {file} to the repository, keeping {num_revisions_to_keep} latest revisions")
            os.makedirs(file_repo_path)
            with open(os.path.join(file_repo_path, "keep"), "w") as f:
                f.write(f"{num_revisions_to_keep}")

            version_num = 0
        else:
            versions = load_log(file_repo_path)
            version_num = len(versions)
            if os.path.exists(os.path.join(file_repo_path, str(version_num - 1))) and not os.path.exists(lock_file):
                raise RuntimeError("File is not locked")

            print(f"New version of [{file}]: {version_num}")
            with open(os.path.join(file_repo_path, "keep"), "r") as f:
                prev_num_revisions_to_keep = int(f.read())

            if num_revisions_to_keep != -1 and prev_num_revisions_to_keep != num_revisions_to_keep:
                print(f"Changing number of revisions to keep from {prev_num_revisions_to_keep} to {num_revisions_to_keep}")
                with open(os.path.join(file_repo_path, "keep"), "w") as f:
                    f.write(f"{num_revisions_to_keep}")
            else:
                num_revisions_to_keep = prev_num_revisions_to_keep

        commit_time = int(time.time())
        with open(os.path.join(file_repo_path, "log"), "a") as f:
            message = message.replace("\t", "    ").replace("\n", "  ")
            f.write(f"{message}\t{commit_time}\n")

        if os.path.exists(file):
            shutil.copy(file, os.path.join(file_repo_path, str(version_num)))
            os.utime(file, (commit_time, commit_time))
            make_readonly(file)

        removed_old_versions = 0
        for ver_to_remove in range(version_num - num_revisions_to_keep, -1, -1):
            ver_file = os.path.join(file_repo_path, str(ver_to_remove))
            if os.path.exists(ver_file):
                os.remove(ver_file)
                removed_old_versions += 1

        if removed_old_versions > 0:
            print(f"Removed {removed_old_versions} old revisions")
        
        if os.path.exists(lock_file):
            os.remove(lock_file)
    elif command == "lock":
        if len(sys.argv) != 4:
            raise UsageError()        

        assert os.path.exists(repo_folder) and os.path.isdir(repo_folder), "missing/wrong repository folder"
        file = sys.argv[3]        
        file_repo_path = os.path.join(repo_folder, file)
        assert os.path.exists(file_repo_path), f"not in repository: [{file}]"
        lock_file = os.path.join(file_repo_path, "lock")
        if os.path.exists(lock_file):
            raise RuntimeError("file is already locked")

        with open(lock_file, "w"):
            pass
        
        if os.path.exists(file):
            make_writable(file)

        print(f"[{file}] is locked. You can change it now, then commit the new version.")
    elif command == "checkout":
        if not (3 <= len(sys.argv) <= 5):
            raise UsageError

        assert os.path.exists(repo_folder) and os.path.isdir(repo_folder), "missing/wrong repository folder"
        if len(sys.argv) == 3:
            print("Checking out the latest version of the whole repository into current folder")
            checkout_recursive(repo_folder, ".")
        else:
            file = sys.argv[3]
            file_repo_path = os.path.join(repo_folder, file)
            assert os.path.exists(file_repo_path), f"not in repository: [{file}]"
            need_version = None if len(sys.argv) < 5 else int(sys.argv[4])
            assert need_version is None or need_version >= 0, "wrong version number requested"
            checkout(file_repo_path, file, need_version)
    elif command == "log":
        if len(sys.argv) != 4:
            raise UsageError

        assert os.path.exists(repo_folder) and os.path.isdir(repo_folder), "missing/wrong repository folder"
        file = sys.argv[3]        
        file_repo_path = os.path.join(repo_folder, file)
        assert os.path.exists(file_repo_path), f"not in repository: [{file}]"    
        versions = load_log(file_repo_path)
        print("Saved? Ver. Timestamp           Message")
        for i, (message, timestamp) in reversed(list(enumerate(versions))):
            line = ""
            if os.path.exists(os.path.join(file_repo_path, str(i))):
                line += "+      "
            else:
                line += "-      "

            line += str(i).ljust(5) + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp)).ljust(20) + message
            print(line)
    else:
        print(f"Unknown command: {command}")
        raise UsageError
except UsageError:
    print(usage)
    exit(1)
except Exception as e:
    print(f"Error: {e}")
    exit(1)
