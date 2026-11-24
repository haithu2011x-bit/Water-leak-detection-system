"""Tests for production-safe SQLite backups using isolated temp folders."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from tools.backup_sqlite import backup_database

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.source=self.base/'source.db'
        with closing(sqlite3.connect(self.source)) as con:
            con.execute("CREATE TABLE telemetry (id INTEGER PRIMARY KEY, flow_main REAL)")
            con.execute("INSERT INTO telemetry VALUES(1, 1.5)")
            con.commit()

    def test_consistent_copy_source_unchanged(self):
        dest=self.base/'copies'/'backup.db'
        before=self.source.read_bytes()
        result=backup_database(self.source,dest)
        self.assertTrue(dest.is_file())
        self.assertEqual(len(result["sha256"]),64)
        self.assertEqual(before,self.source.read_bytes())
        with closing(sqlite3.connect(dest)) as con:
            self.assertEqual(con.execute("SELECT flow_main FROM telemetry").fetchone()[0],1.5)

    def test_refuse_same_path_or_overwrite(self):
        with self.assertRaises(ValueError):
            backup_database(self.source,self.source)
        dest=self.base/'a.db'
        backup_database(self.source,dest)
        with self.assertRaises(FileExistsError):
            backup_database(self.source,dest)

    def test_no_source_does_not_create_db(self):
        source=self.base/'missing.db'
        with self.assertRaises(FileNotFoundError):
            backup_database(source,self.base/'b.db')
        self.assertFalse(source.exists())

if __name__=='__main__':
    unittest.main()
