"""Tests for the Entry classes"""

import os
import csv

import pytest

from xamin.project import Entry, TextEntry, BinaryEntry, CsvEntry


@pytest.fixture(params=["text", "binary", "csvfile"])
def entry(request, tmp_path) -> TextEntry:
    # Create a test text document
    if request.param == "text":
        data = "This is my\ntest text file."
        test_file = tmp_path / "test.txt"
        test_file.write_text(data)
        return TextEntry(test_file)

    elif request.param == "binary":
        data = os.urandom(16)  # 16-bytes of binary
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(data)
        return BinaryEntry(test_file)

    elif request.param == "csvfile" or request.param == "tsvfile":
        data = [[str(i) for i in range(6)] for j in range(8)]
        if "csvfile":
            dialect = csv.get_dialect("excel")
            test_file = tmp_path / "test.csv"
        elif "tsvfile":
            dialect = csv.get_dialect("excel-tab")
            test_file = tmp_path / "test.tsv"
        else:
            raise AssertionError("Unknown dialect")

        with open(test_file, "w") as f:
            writer = csv.writer(f, dialect=dialect)
            writer.writerows(data)
        return CsvEntry(test_file)

    else:
        raise AssertionError("Unknown type")


def test_entry_suclasses():
    """Test the Entry.subclasses() static method"""
    subclasses = Entry.subclasses()

    assert (1, TextEntry) in subclasses
    assert (1, BinaryEntry) in subclasses
    assert (2, CsvEntry) in subclasses


def test_entry_depth():
    """Test the Entry.depth() baseclass method."""
    assert Entry.depth() == 0
    assert TextEntry.depth() == 1
    assert BinaryEntry.depth() == 1
    assert CsvEntry.depth() == 2


def test_entry_is_type(entry):
    """Test the Entry.is_type class method."""
    if isinstance(entry, TextEntry):
        assert TextEntry.is_type(entry.path)
        assert not BinaryEntry.is_type(entry.path)
    elif isinstance(entry, BinaryEntry):
        assert BinaryEntry.is_type(entry.path)
        assert not TextEntry.is_type(entry.path)


def test_entry_load(entry):
    """Test the Entry loading of a file"""
    assert len(entry.data) > 0

    if isinstance(entry, CsvEntry):
        assert isinstance(entry.data, list)
        assert entry.shape == (len(entry.data), len(entry.data[0]))
    elif isinstance(entry, TextEntry):
        assert isinstance(entry.data, str)
        assert entry.shape == (len(entry.data),)
    elif isinstance(entry, BinaryEntry):
        assert isinstance(entry.data, bytes)
        assert entry.shape == (len(entry.data),)


def test_entry_is_changed(entry):
    """Test the Entry is_changed property"""
    # Prepare extra data by type
    if isinstance(entry, CsvEntry):
        extra = [10, 11, 12, 13, 14, 15]
    elif isinstance(entry, TextEntry):
        extra = "some extra stuff"
    elif isinstance(entry, BinaryEntry):
        extra = b"some extra stuff"

    # Data should not be changed before the data method loads it
    assert not entry.is_changed

    # Get the original data
    original_data = entry.data
    assert not entry.is_changed

    # Modify it and change that the text_entry has changed
    entry.data = original_data + extra
    assert entry.is_changed

    # Reset it and the is_changed flag should change
    entry.data = original_data
    assert not entry.is_changed


def test_entry_save(entry):
    """Test the Entry save method"""
    # Prepare extra data by type
    if isinstance(entry, CsvEntry):
        extra = [10, 11, 12, 13, 14, 15]
    elif isinstance(entry, TextEntry):
        extra = "some extra stuff"
    elif isinstance(entry, BinaryEntry):
        extra = b"some extra stuff"

    # Get the current mtime of the file to test when it is modified
    start_mtime = entry.path.stat().st_mtime

    # Load the data without unsaved changes should not modify the file
    entry.save()
    assert entry.path.stat().st_mtime == start_mtime

    # Changing the data produces unsaved changes, which can be saved
    entry.data = entry.data + extra

    entry.save()
    assert entry.path.stat().st_mtime >= start_mtime
