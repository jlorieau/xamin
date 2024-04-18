"""Entry abstract base class and concrete Base classes TextEntry and BinaryEntry"""

import typing as t
import pickle
import inspect
from abc import ABC, abstractmethod
from pathlib import Path
from hashlib import sha256

from thatway import Setting
from loguru import logger

from ..utils.classes import all_subclasses

__all__ = ("Entry", "HintType", "MissingPath", "FileChanged")

# The types that a 'hint' can adopt
HintType = t.Union[t.Text, t.ByteString, None]

# Generic type annotation
T = t.TypeVar("T")


class EntryException(Exception):
    """Exception raised in processing entries."""


class MissingPath(EntryException):
    """Exception raised when trying to save/load a file but no path is specified"""


class FileChanged(EntryException):
    """Exception raised when an entry tries to save but the file it is saving to
    is newer."""


class Entry(ABC, t.Generic[T]):
    """A file entry in a project"""

    #: The path of the file
    path: t.Optional[Path] = None

    #: Settings to change the default behavior
    hint_size = Setting(2048, desc="Size (in bytes) of the hint to read from the file")

    text_encoding = Setting("utf-8", desc="Default text file encoding")

    #: Cached data
    _data: T

    #: The data hash at load/save time
    _loaded_hash: str = ""

    #: The mtime of the data loaded from a file
    _data_mtime = None

    #: The cached Entry subclasses
    _subclasses = None

    def __init__(self, path: t.Optional[Path] = None):
        self.path = path
        super().__init__()

    def __repr__(self):
        """The string representation for this class"""
        cls_name = self.__class__.__name__
        name = f"'{self.path}'" if self.path is not None else "None"
        return f"{cls_name}(path={name})"

    def __eq__(self, other):
        """Test the equivalence of two entries"""
        conditions = (
            self.__class__ == other.__class__,  # same class
            self.path == getattr(other, "path", None),  # same path
        )
        return all(conditions)

    def __getstate__(self) -> t.Dict:
        """Get a copy of the current state for serialization"""
        return {"path": self.path}

    def __setstate__(self, state):
        """Set the state for the entry based on the given state copy"""
        self.path = state.get("path", None)

    @classmethod
    def _generics_type(cls):
        """Retrieve the type 'T' of the Entry class or subclass"""
        return t.get_args(cls.__orig_bases__[0])

    @staticmethod
    def subclasses() -> t.List[t.Tuple[int, "Entry"]]:
        """Retrieve all subclasses of the Entry class as well as their class hierarchy
        level."""
        if Entry._subclasses is None:
            Entry._subclasses = [
                (c.depth(), c) for c in all_subclasses(Entry) if hasattr(c, "depth")
            ]
        return Entry._subclasses

    @classmethod
    def depth(cls):
        """Return the class hierarchy depth for this class"""
        parent_depths = [b.depth() for b in cls.__bases__ if hasattr(b, "depth")]
        return parent_depths[0] + 1 if parent_depths else 0

    @classmethod
    def get_hint(cls, path: Path) -> t.Union[HintType]:
        """Retrieve the hint bytes or text from the given path

        Parameters
        ----------
        path
            The path to get the hint from

        Returns
        -------
        hint
            - The first 'hint_size' bytes of the file given by the path.
            - If a text string (UTF-8) can be decoded, it will be returned.
            - Otherwise a byte string will be returned.
            - If the path doesn't point to a file or the file can't be read, the hint
              is None

        Examples
        --------
        >>> p = Path(__file__)  # this .py text file
        >>> hint = Entry.get_hint(p)
        >>> type(hint)
        <class 'str'>
        >>> import sys
        >>> e = Path(sys.executable)  # Get the python interpreter executable
        >>> hint = Entry.get_hint(e)
        >>> type(hint)
        <class 'bytes'>
        """
        # Read the first 'hint_size' bytes from the file
        try:
            with open(path, "rb") as f:
                bytes = f.read(cls.hint_size)
        except:
            return None

        # Try decoding the bytes to text
        try:
            return bytes.decode(cls.text_encoding)
        except:
            return bytes

    @classmethod
    @abstractmethod
    def is_type(cls, path: Path, hint: HintType = None) -> bool:
        """Return True if path can be parsed as this Entry's type.

        Parameters
        ----------
        path
            The path whose file should be tested whether it matches this type.
            This is only checked to retrieve a hint, if one isn't given.
        hint
            The optional hint from the path to be used in the determination.

        Returns
        -------
        is_type
            True, if the file can be loaded as this Entry's type
        """
        return False

    @classmethod
    def guess_type(
        cls, path: Path, hint: HintType = None
    ) -> t.Union[t.Type["Entry"], None]:
        """Try to guess the correct Entry class from the given path and (optional)
        hint.

        Paramters
        ---------
        path
            The path to the file whose contents should be guessed
        hint
            Information of type HintType that can be used to guide the guessing

        Returns
        -------
        entry_type
            The best entry class for the given arguments, or
            None if a best entry class could not be found.
        """
        # Must be a path type, if no hint is specified
        if isinstance(path, Path) or isinstance(path, str):
            path = Path(path)
        elif hint is None:
            # Can't figure out the type without a valid type or a valid hint
            return None

        # Get the hint, if it wasn't specified
        hint = hint if hint is not None else cls.get_hint(path)

        # Find the best class from those with the highest class hierarchy level
        # i.e. the more subclassed, the more specific is a type
        highest_hierarchy = 0
        best_cls = None

        for hierarchy, cls in cls.subclasses():
            if hierarchy > highest_hierarchy and cls.is_type(path=path, hint=hint):
                best_cls = cls

        if best_cls is not None:
            logger.debug(f"Found best Entry class '{best_cls}' for path: {path}")
            return best_cls
        else:
            return None

    @property
    def is_stale(self) -> bool:
        """Determine whether the data is stale and should be reloaded from self.path."""

        # Setup logger
        if __debug__:

            def state(value, reason):
                logger.debug(f"{self.__class__.__name__}.is_state={value}. {reason}")
                return value

        else:
            state = lambda s: s

        # Evaluate the state
        if not hasattr(self, "_data"):
            return True

        elif self.path is None:
            return state(False, "No path was specified")

        elif not self.path.exists():
            return state(False, "The file path does not exist")

        elif self.path.exists() and (self._data_mtime is None or self._data is None):
            return state(True, "A file path exists, but is not yet loaded")

        elif self._data_mtime < self.path.stat().st_mtime:
            return state(True, "The data mtime is older than the file mtime")

        else:
            return state(False, "The data mtime is as new as the file's mtime")

    def reset_mtime(self):
        """Update the mtime of the loaded data (self._data_mtime) to equal that of
        the file (self.path)"""
        if self.path is not None:
            self._data_mtime = self.path.stat().st_mtime

    @property
    def is_unsaved(self) -> bool:
        """Determine whether the given entry has changed and not been saved.

        By definition, entries without a path aren't saved.
        Otherwise, see if the hash of the loaded data matches the current has. If it
        doesn't the the contents of the data have changed.
        """
        # Setup logger
        if __debug__:

            def state(value, reason):
                logger.debug(f"{self.__class__.__name__}.is_unsaved={value}. {reason}")
                return value

        else:
            state = lambda s: s

        # Evaluate the state
        if getattr(self, "path", None) is None:
            return state(True, "No path was specified")
        elif self.hash != self._loaded_hash:
            return state(True, "Data hash is not equal to the loaded file hash")
        else:
            return False

    @property
    def hash(self) -> str:
        """The hash for the current data to determine when the data has changed since
        it was loaded.

        Returns
        -------
        hash
            - Empty string, if a hash could not be calculated
            - A hex hash (sha256) of the data
        """
        if getattr(self, "_data", None) is None:
            return ""
        elif isinstance(self._data, str):
            return sha256(self._data.encode(self.text_encoding)).hexdigest()
        elif isinstance(self._data, bytes):
            return sha256(self._data).hexdigest()
        else:
            return sha256(pickle.dumps(self._data)).hexdigest()

    def reset_hash(self):
        """Reset the loaded hash to the new contents of self.data.

        This function is needed when data is freshly loaded from a file, or when
        the data has been freshly saved to the file
        """
        self._loaded_hash = self.hash  # Reset the loaded hash

    @property
    def data(self) -> T:
        """Return the data (or an iterator) of the data.

        Subclasses are responsible for load the data and calling this parent
        property."""
        if self.is_stale:
            self.load()
        return self._data

    @data.setter
    def data(self, value):
        """Set the data with the given value"""
        self._data = value

    @property
    def shape(self) -> t.Tuple[int, ...]:
        """Return the shape of the data--i.e. the length along each data array
        dimension."""
        data = self.data

        if hasattr(data, "shape"):
            return data.shape()
        elif hasattr(data, "__len__"):
            return (len(data),)
        else:
            return ()

    def default_data(self):
        """A factory method to return a new instance of self.data"""
        return None

    def pre_load(self, *args, **kwargs):
        """Before loading data, perform actions, like setting a default, if needed."""
        if not hasattr(self, "_data"):
            self._data = self.default_data()

    def post_load(self):
        """After successfully loading data, perform actions, like resetting the
        hash and mtime,"""
        self.reset_hash()
        self.reset_mtime()

    def load(self, *args, **kwargs):
        """Load and return the data (self._data) or return a default data instance,
        if the data cannot be loaded from a file.
        """
        # Perform check
        self.pre_load(*args, **kwargs)

        # Reset flags
        self.post_load(*args, **kwargs)

    def pre_save(self, overwrite: bool = False, *args, **kwargs):
        """Before saving data, perform actions like checking whether a path exists
        and whether.

        Parameters
        ----------
        overwrite
            Whether to overwrite unsaved changes

        Raises
        ------
        MissingPath
            Raised if trying to save but the path could not be found.
        UnsavedChanges
            Raised if the destination file exists and its contents are newer
            than those in this entry's data.
        """
        if getattr(self, "path", None) is None:
            raise MissingPath(
                f"Could not save entry of type "
                f"'{self.__class__.__name__}' because no path is specified."
            )
        if not overwrite and hasattr(self, "_data") and self.is_stale:
            raise FileChanged(f"Cannot overwrite the file at path '{self.path}'")

    def post_save(self, *args, **kwargs):
        """After successfully saving data, perform actions like resetting the cached
        hash and stored mtime"""
        self.reset_hash()
        self.reset_mtime()

    def save(self, overwrite: bool = False, *args, **kwargs):
        """Save the data to self.path.

        Parameters
        ----------
        overwrite
            Whether to overwrite unsaved changes

        Raises
        ------
        MissingPath
            Raised if trying to save but the path could not be found.
        UnsavedChanges
            Raised if the destination file exists and its contents are newer
            than those in this entry's data.
        """
        # Perform checks and raise exceptions
        self.pre_save(overwrite=overwrite, *args, **kwargs)

        # Resets flags
        self.post_save(*args, **kwargs)
