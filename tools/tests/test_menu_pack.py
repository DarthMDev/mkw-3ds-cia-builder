import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_menu_pack import verify_menu_pack


class MenuPackTests(unittest.TestCase):
    def test_changed_label_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            name = b'textures/ui_text_422.t3x\0'
            source = root / name[:-1].decode()
            source.parent.mkdir()
            source.write_bytes(b'Don-Chan')
            offset = 24 + len(name)
            (root / 'menu.pak').write_bytes(
                b'MPK1' + struct.pack('<II', 1, len(name)) +
                struct.pack('<III', 0, offset, 8) + name + b'Don-Chan')
            self.assertEqual(verify_menu_pack(root), 1)
            source.write_bytes(b'Wario (Hiker)')
            with self.assertRaisesRegex(ValueError, 'menu.pak is stale'):
                verify_menu_pack(root)

    def test_out_of_bounds_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'menu.pak').write_bytes(
                b'MPK1' + struct.pack('<II', 1, 2) +
                struct.pack('<III', 0, 999, 8) + b'x\0')
            with self.assertRaisesRegex(ValueError, 'Invalid menu.pak entry'):
                verify_menu_pack(root)


if __name__ == '__main__':
    unittest.main()
