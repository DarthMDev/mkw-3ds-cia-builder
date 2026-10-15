import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from verify_pulsar_pack import verify_pulsar_pack


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PulsarPackTests(unittest.TestCase):
    def test_reference_manifest_alone_is_not_a_cooked_pack(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(ValueError, 'No cooked Retro Rewind pack'):
                verify_pulsar_pack(root)
            (root/'pulsar_manifest.json').write_bytes((TOOLS.parent/'pulsar_manifest.json').read_bytes())
            with self.assertRaisesRegex(ValueError, 'Missing Retro Rewind asset'):
                verify_pulsar_pack(root)

    def test_complete_pack_and_missing_model(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'Race/Course').mkdir(parents=True)
            (root/'models').mkdir()
            (root/'Race/Course/a.szs').write_bytes(b'archive')
            (root/'models/a.list').write_text('a_000\n')
            (root/'models/a_000.gmdl').write_bytes(b'model')
            track = dict(archive='Race/Course/a.szs', models='models/a.list', sky='')
            (root/'pulsar_manifest.json').write_text(json.dumps(dict(cups=[dict(tracks=[track])])))
            self.assertEqual(verify_pulsar_pack(root), (1, 1))
            (root/'models/a_000.gmdl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing Retro Rewind asset: models/a_000.gmdl'):
                verify_pulsar_pack(root)

    def test_empty_optional_sky_list_is_valid_but_missing_assets_are_not(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'models').mkdir()
            (root/'track.szs').write_bytes(b'archive')
            (root/'models/course.list').write_text('course_000\n')
            (root/'models/course_000.gmdl').write_bytes(b'model')
            sky = root/'models/sky.list'
            sky.write_text('')
            track = dict(archive='track.szs', models='models/course.list', sky='models/sky.list')
            (root/'pulsar_manifest.json').write_text(json.dumps(dict(cups=[dict(tracks=[track])])))
            self.assertEqual(verify_pulsar_pack(root), (1, 1))
            sky.write_text('missing_sky_000\n')
            with self.assertRaisesRegex(ValueError, 'Missing Retro Rewind asset: models/missing_sky_000.gmdl'):
                verify_pulsar_pack(root)
            sky.unlink()
            with self.assertRaisesRegex(ValueError, 'Missing Retro Rewind asset: models/sky.list'):
                verify_pulsar_pack(root)
            sky.write_text('')
            (root/'models/course.list').write_text('')
            with self.assertRaisesRegex(ValueError, 'Missing Retro Rewind asset: models/course.list'):
                verify_pulsar_pack(root)

    def test_cached_track_does_not_reference_empty_sky(self):
        importer = self.importer()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'models').mkdir()
            (root/'models/pulsar_track_171.list').write_text('course_000\n')
            (root/'models/pulsar_track_171_sky.list').write_text('')
            result = importer.convert_track(root/'unused.szs', root, 'pulsar_track_171')
            self.assertEqual(result['sky'], '')
            (root/'models/pulsar_track_171_sky.list').write_text('sky_000\n')
            result = importer.convert_track(root/'unused.szs', root, 'pulsar_track_171')
            self.assertEqual(result['sky'], 'models/pulsar_track_171_sky.list')

    def test_empty_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'pulsar_manifest.json').write_text('{"cups": []}')
            with self.assertRaisesRegex(ValueError, 'must contain cups'):
                verify_pulsar_pack(root)

    def test_rr_mode_stops_before_building_vanilla(self):
        builder = load_script('test_rr_builder', TOOLS/'release/build_cia.py')
        with tempfile.TemporaryDirectory() as folder, patch.object(builder, 'ROOT', Path(folder)), \
                patch.object(builder, 'stage_tools') as stage, \
                patch.object(sys, 'argv', ['build_cia.py', '--require-pack']):
            with self.assertRaisesRegex(SystemExit, 'No cooked Retro Rewind pack'):
                builder.main()
            stage.assert_not_called()

    def importer(self):
        # Keep the test independent of the disc tools and graphics dependencies.
        with patch.dict(sys.modules, {
            'unpack_szs': types.SimpleNamespace(unpack=Mock()),
            'cook_model': types.SimpleNamespace(cook=Mock()),
        }):
            return load_script('test_rr_importer', TOOLS/'import_pulsar_pack.py')

    def test_importer_executes_conversions_and_records_optional_sky(self):
        importer = self.importer()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pack = root/'pack'
            pack.mkdir()
            for name in ('a', 'b'):
                (pack/(name+'.szs')).write_bytes(name.encode())
            converter = Mock(return_value={'models': 'models/cooked.list', 'sky': ''})
            with patch.object(importer, 'convert_track', converter):
                importer.import_pack(pack, root/'out', jobs=2)
            self.assertEqual(converter.call_count, 2)
            data = json.loads((root/'out/pulsar_manifest.json').read_text())
            self.assertEqual([t['sky'] for c in data['cups'] for t in c['tracks']], ['', ''])

    def test_failed_conversion_does_not_publish_manifest(self):
        importer = self.importer()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pack = root/'pack'
            pack.mkdir()
            (pack/'a.szs').write_bytes(b'a')
            with patch.object(importer, 'convert_track', return_value={'models': '', 'sky': ''}):
                with self.assertRaisesRegex(ValueError, 'Track conversion failed'):
                    importer.import_pack(pack, root/'out')
            self.assertFalse((root/'out/pulsar_manifest.json').exists())

    def test_missing_track_does_not_publish_manifest(self):
        importer = self.importer()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pack = root/'pack'
            pack.mkdir()
            (pack/'pulsar_manifest.json').write_text(json.dumps(dict(cups=[dict(tracks=[dict(name='Missing')])])))
            with self.assertRaisesRegex(ValueError, 'Missing source track archive'):
                importer.import_pack(pack, root/'out')
            self.assertFalse((root/'out/pulsar_manifest.json').exists())

    def test_pack_skins_run_in_order_with_supplied_source(self):
        builder = load_script('test_skin_builder', TOOLS/'release/build_cia.py')
        with tempfile.TemporaryDirectory() as folder:
            pack = Path(folder)/'Retro Rewind (custom)'
            for name in ('Driver', 'AllKart', 'Sound'):
                (pack/'Character'/name).mkdir(parents=True)
            with patch.object(builder, 'run') as run:
                builder.stage_pack_skins(pack, 2)
            scripts = [call.args[0][1] for call in run.call_args_list]
            self.assertEqual(scripts, ['tools/cook_character_skins.py', 'tools/cook_garage_skins.py',
                                      'tools/cook_skin_vehicles.py', 'tools/cook_skin_menu_vehicles.py',
                                      'tools/cook_skin_audio.py'])
            for call in run.call_args_list:
                self.assertEqual(call.kwargs['env']['MKW_RR_PACK'], str(pack.resolve()))
                self.assertEqual(call.kwargs['env']['MKW_SKIN_JOBS'], '2')

    def test_track_only_pack_skips_skins(self):
        builder = load_script('test_track_only_builder', TOOLS/'release/build_cia.py')
        with tempfile.TemporaryDirectory() as folder, patch.object(builder, 'run') as run:
            builder.stage_pack_skins(Path(folder), 2)
            run.assert_not_called()

    def test_skin_failure_stops_build(self):
        import subprocess
        builder = load_script('test_skin_failure_builder', TOOLS/'release/build_cia.py')
        with tempfile.TemporaryDirectory() as folder:
            pack = Path(folder)
            (pack/'Character/Driver').mkdir(parents=True)
            with patch.object(builder, 'run', side_effect=subprocess.CalledProcessError(1, 'skin cooker')) as run:
                with self.assertRaises(subprocess.CalledProcessError):
                    builder.stage_pack_skins(pack, 2)
            self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
