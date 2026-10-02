"""Session-relative paths; reject symlinks and Windows reparse points."""
import os
from pathlib import Path, PurePosixPath
from .audio import VoiceError


class Spool:
    def __init__(self, root):
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        if self.is_link(root):
            raise VoiceError('UNSAFE_SPOOL', 'Spool root must not be a link')
        self.root = root.resolve(strict=True)

    @staticmethod
    def is_link(path):
        if path.is_symlink():
            return True
        try:
            return bool(getattr(os.lstat(path), 'st_file_attributes', 0) & 0x400)
        except FileNotFoundError:
            return False

    def resolve(self, name, session, directory=False):
        if (not isinstance(name, str) or not name or len(name) > 512 or
                '\\' in name or ':' in name or '\x00' in name):
            raise VoiceError('UNSAFE_PATH', 'Require session-relative spool path')
        parts = name.split('/')
        if any(p in ('', '.', '..') for p in parts) or PurePosixPath(name).is_absolute():
            raise VoiceError('UNSAFE_PATH', 'Invalid spool path components')
        reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{prefix}{i}' for prefix in ('COM', 'LPT') for i in range(1, 10)}
        if any(p.endswith(('.', ' ')) or any(ord(c) < 32 for c in p) or
               p.split('.')[0].upper() in reserved for p in parts):
            raise VoiceError('UNSAFE_PATH', 'Ambiguous or reserved path component')
        if parts[0] != session or len(parts) < 2:
            raise VoiceError('CROSS_SESSION_PATH', 'Path must belong to this session')
        path = self.root
        for part in parts:
            path = path / part
            if self.is_link(path):
                raise VoiceError('UNSAFE_PATH', 'Links/reparse points are not allowed')
            if not path.resolve().is_relative_to(self.root):
                raise VoiceError('UNSAFE_PATH', 'Path escapes spool')
        if directory:
            if path.exists() and not path.is_dir():
                raise VoiceError('BAD_OUTPUT_DIR', 'Output path must be a directory')
        elif not path.is_file():
            raise VoiceError('FILE_NOT_FOUND', 'Input WAV not found')
        return path

    def make_directory(self, name, session):
        path = self.resolve(name, session, directory=True)
        path.mkdir(parents=True, exist_ok=True)
        return self.resolve(name, session, directory=True)

    def remove_owned_file(self, relative, session):
        # Never recursively delete directories or caller-owned input files.
        try:
            path = self.resolve(relative, session)
            path.unlink()
        except VoiceError as exc:
            if exc.code != 'FILE_NOT_FOUND':
                raise
