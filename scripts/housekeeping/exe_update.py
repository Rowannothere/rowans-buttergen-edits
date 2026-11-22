"""BUTTERGEN: the update button of the Windows exe. Downloads the newest build from GitHub, checks it,
and lets the new exe swap itself in after the game closes. Saves are in another folder.

The finishing part runs before the game loads (init.py), so only import the standard library up here."""
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from configparser import ConfigParser

REPO = "Tropicaluwu/Buttergen"
EXE = "Buttergen.exe"
INTERNAL = "_internal"
ZIP_FOLDER = "Buttergen"
ASSET = "Buttergen_Win64.zip"
DEV_TAG = "dev-latest"
API = "https://api.github.com"
DOWNLOADS = f"https://github.com/{REPO}/releases/download/"

FINISH_ARG = "--finish-update"
FAILED_ARG = "--update-failed"
UPDATED_ARG = "--updated"

# what the game folder holds that an update replaces. Nothing else in there is touched
PARTS = (INTERNAL, EXE)
OLD, NEW = ".old", ".new"
# how long the new exe waits for the old game to close
SWAP_SECONDS = 60
# the new version makes this file at the main menu. If it closes with an error first (also after
# sitting on an error window), it's swapped back
STARTED = "started"
WATCH_SECONDS = 600

DOWNLOADING, CHECKING, READY, FAILED, LOCKED, CANCELED = (
    "downloading", "checking", "ready", "failed", "locked", "canceled")


def can_update() -> bool:
    """only the Windows exe updates itself"""
    return bool(getattr(sys, "frozen", False)) and platform.system() == "Windows"


def game_folder() -> str:
    return os.path.dirname(os.path.abspath(sys.executable))


def update_folder() -> str:
    from scripts.housekeeping.datadir import get_data_dir

    return os.path.join(os.path.abspath(get_data_dir()), "update")


def failed_last_time() -> bool:
    return FAILED_ARG in sys.argv


def version_tuple(version):
    return tuple(int(part) for part in re.findall(r"\d+", str(version)))


# finding the newest build

def find_build(channel) -> dict | None:
    """the newest build of this channel: version, url, size and sha256. None while there's no zip yet"""
    import requests

    path = f"tags/{DEV_TAG}" if channel == "dev" else "latest"
    response = requests.get(f"{API}/repos/{REPO}/releases/{path}", timeout=10)
    response.raise_for_status()
    return build_from_release(response.json(), channel)


def build_from_release(release, channel) -> dict | None:
    # the dev build's version is in its title, its tag never changes
    title = release.get("name") if channel == "dev" else release.get("tag_name")
    version = re.search(r"v\d[\w.\-]*", title or "")
    asset = next((a for a in release.get("assets", []) if a.get("name") == ASSET), None)
    if not version or not asset or asset.get("state") != "uploaded":
        return None
    digest = asset.get("digest") or ""
    url = asset.get("browser_download_url") or ""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest) or not url.startswith(DOWNLOADS):
        return None
    return {"version": version.group(0), "url": url, "size": asset["size"],
            "sha256": digest.split(":")[1]}


# downloading and checking

class UpdateError(Exception):
    pass


class Canceled(Exception):
    pass


def folder_locked(folder) -> bool:
    """True if Windows won't let the game change its own folder"""
    test = os.path.join(folder, "update_test")
    try:
        os.makedirs(test, exist_ok=True)
        os.rename(test, test + OLD)
        os.rmdir(test + OLD)
        return False
    except OSError:
        shutil.rmtree(test, ignore_errors=True)
        return True


def read_version(folder):
    """(version, channel) of an unzipped game folder"""
    ini = ConfigParser()
    ini.read(os.path.join(folder, INTERNAL, "version.ini"), encoding="utf-8")
    return ini.get("DEFAULT", "version_number"), ini.get("DEFAULT", "update_channel", fallback="stable")


class Updater(threading.Thread):
    """downloads, checks and unzips a build in the background. The window reads stage and percent"""

    def __init__(self, build, channel, current):
        super().__init__(daemon=True)
        self.build, self.channel, self.current = build, channel, current
        self.folder = update_folder()
        self.staged = os.path.join(self.folder, ZIP_FOLDER)
        self.stage = DOWNLOADING
        self.percent = 0
        self.error = None
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            if _cleaner is not None:
                _cleaner.join()
            if folder_locked(game_folder()):
                self.stage = LOCKED
                return
            shutil.rmtree(self.folder, ignore_errors=True)
            os.makedirs(self.folder, exist_ok=True)
            path = os.path.join(self.folder, ASSET)
            self._download(path)
            self.stage = CHECKING
            self._check_and_unzip(path)
            self._stop_if_canceled()
            self.stage = READY
        except Canceled:
            shutil.rmtree(self.folder, ignore_errors=True)
            self.stage = CANCELED
        except Exception as error:  # no internet, a broken zip, a full disk...
            print(f"Update failed: {error!r}")
            self.error = error
            shutil.rmtree(self.folder, ignore_errors=True)
            self.stage = FAILED

    def _stop_if_canceled(self):
        if self._cancel:
            raise Canceled

    def _download(self, path):
        import requests

        done = 0
        sha = hashlib.sha256()
        with requests.get(self.build["url"], stream=True, timeout=30) as response:
            response.raise_for_status()
            with open(path, "wb") as write_file:
                for chunk in response.iter_content(1024 * 256):
                    self._stop_if_canceled()
                    done += len(chunk)
                    if done > self.build["size"]:
                        raise UpdateError("the download is bigger than it should be")
                    sha.update(chunk)
                    write_file.write(chunk)
                    self.percent = int(done * 100 / self.build["size"])
        if done != self.build["size"]:
            raise UpdateError("the download isn't complete")
        if sha.hexdigest() != self.build["sha256"]:
            raise UpdateError("the download doesn't match the one on GitHub")

    def _check_and_unzip(self, path):
        with zipfile.ZipFile(path) as zip_file:
            for name in zip_file.namelist():
                parts = name.replace("\\", "/").split("/")
                if parts[0] != ZIP_FOLDER or ".." in parts:
                    raise UpdateError(f"unexpected file in the zip: {name}")
            for info in zip_file.infolist():
                self._stop_if_canceled()
                zip_file.extract(info, self.folder)
        os.remove(path)
        if not os.path.isfile(os.path.join(self.staged, EXE)):
            raise UpdateError("the zip has no game in it")
        version, channel = read_version(self.staged)
        if channel != self.channel:
            raise UpdateError(f"this is a {channel} build")
        if version_tuple(version) <= version_tuple(self.current):
            raise UpdateError(f"{version} isn't newer than {self.current}")

    def start_finishing(self):
        """starts the new exe, which swaps itself in once this game has closed"""
        launch(os.path.join(self.staged, EXE), self.folder, [FINISH_ARG, game_folder()])


def launch(exe, cwd, args):
    # the started exe is its own program, not part of this one
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    flags = 0
    if platform.system() == "Windows":
        import ctypes

        ctypes.windll.kernel32.SetDllDirectoryW(None)
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen([exe, *args], cwd=cwd, env=env, creationflags=flags, close_fds=True)


# finishing (runs in the new exe, from the update folder)

def remove(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)


def put_new_next_to_old(staged, game):
    for part in PARTS:
        remove(os.path.join(game, part + NEW))
        remove(os.path.join(game, part + OLD))
        source, target = os.path.join(staged, part), os.path.join(game, part + NEW)
        if os.path.isdir(source):
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def _rename(source, target, until):
    """Windows refuses while the old game is still closing, so it's tried again for a while"""
    while True:
        try:
            os.rename(source, target)
            return
        except OSError:
            if time.time() > until:
                raise
            time.sleep(0.25)


def swap(game, seconds=SWAP_SECONDS):
    until = time.time() + seconds
    for part in PARTS:
        path = os.path.join(game, part)
        _rename(path, path + OLD, until)
        _rename(path + NEW, path, until)


def put_old_back(game, seconds=10):
    until = time.time() + seconds
    for part in PARTS:
        path = os.path.join(game, part)
        if os.path.exists(path + OLD):
            if os.path.exists(path):
                _rename(path, path + NEW, until)
            _rename(path + OLD, path, until)
    for part in PARTS:
        try:
            remove(os.path.join(game, part + NEW))
        except OSError:
            pass


def crashed(process, started, seconds) -> bool:
    """True if it closed with an error before it got to the main menu"""
    until = time.time() + seconds
    while time.time() < until:
        if os.path.exists(started):
            return False
        code = process.poll()
        if code is not None:
            return code != 0
        time.sleep(0.25)
    return False


def finish(staged, game, log=print) -> bool:
    exe = os.path.join(game, EXE)
    try:
        if not os.path.isfile(exe) or not os.path.isdir(os.path.join(game, INTERNAL)):
            raise UpdateError(f"no game in {game}")
        put_new_next_to_old(staged, game)
        swap(game)
        started = os.path.join(os.path.dirname(staged), STARTED)
        process = launch(exe, game, [UPDATED_ARG, started])
        if crashed(process, started, WATCH_SECONDS):
            raise UpdateError(f"the new version closed with error {process.returncode}")
        log("updated")
        return True
    except Exception as error:  # whatever it was, the old version comes back
        log(f"failed: {error!r}")
        try:
            put_old_back(game)
            launch(exe, game, [FAILED_ARG])
            log("the old version is back")
        except Exception as second_error:  # pylint: disable=broad-except
            log(f"putting the old version back failed: {second_error!r}")
        return False


def finish_from_args():
    """init.py calls this first thing when the exe was started to finish an update"""
    game = sys.argv[sys.argv.index(FINISH_ARG) + 1]
    staged = game_folder()
    os.chdir(os.path.dirname(staged))

    def log(line):
        # next to the game's other logs, the update folder gets deleted
        logs = os.path.join(os.path.dirname(os.path.dirname(staged)), "logs")
        os.makedirs(logs, exist_ok=True)
        with open(os.path.join(logs, "update.log"), "a", encoding="utf-8") as write_file:
            write_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")

    finish(staged, os.path.abspath(game), log)


# after an update

def clean_up(game=None, folder=None, seconds=45):
    """deletes the old version and the download. The finishing exe may still be open for a moment"""
    game, folder = game or game_folder(), folder or update_folder()
    finish_cut_short(game)
    until = time.time() + seconds
    trash = folder + OLD
    while os.path.isdir(folder):
        try:
            shutil.rmtree(trash, ignore_errors=True)
            os.rename(folder, trash)
        except OSError:
            if time.time() > until:
                break
            time.sleep(1)
    shutil.rmtree(trash, ignore_errors=True)
    for part in PARTS:
        for end in (OLD, NEW):
            try:
                remove(os.path.join(game, part + end))
            except OSError:
                pass


def finish_cut_short(game):
    """the PC turned off between the two swaps: the new files are in, the exe isn't yet"""
    exe, internal = os.path.join(game, EXE), os.path.join(game, INTERNAL)
    if (os.path.isdir(internal + OLD) and not os.path.exists(internal + NEW)
            and os.path.exists(exe + NEW) and not os.path.exists(exe + OLD)):
        # Windows lets a running exe be renamed, the next start uses the new one
        try:
            os.rename(exe, exe + OLD)
            os.rename(exe + NEW, exe)
        except OSError:
            pass


_cleaner = None


def tell_started():
    """the new version got to the main menu, so the finishing exe can close"""
    if UPDATED_ARG not in sys.argv:
        return
    path = os.path.join(update_folder(), STARTED)
    sys.argv.remove(UPDATED_ARG)
    try:
        with open(path, "w", encoding="utf-8") as write_file:
            write_file.write("ok")
    except OSError:
        pass


def start_clean_up():
    global _cleaner
    if can_update() and _cleaner is None:
        tell_started()
        _cleaner = threading.Thread(target=clean_up, daemon=True)
        _cleaner.start()
