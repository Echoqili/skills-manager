"""用户选择、精确详情与打包完整性的回归测试，文件均位于临时目录。"""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'web'))
import app as web


class PackageFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.tmp.name)
        self.skills = []
        for ns in ('design', 'qa-testing'):
            directory = self.root / ns / 'guide'
            directory.mkdir(parents=True)
            (directory / 'SKILL.md').write_text(f'# {ns}', encoding='utf-8')
            self.skills.append({'name': 'guide', 'namespace': ns, 'category': ns, 'path': str(directory)})
        self.patches = [
            patch.object(web, 'PROJECT_ROOT', self.root),
            patch.object(web, 'get_current_user', return_value={'id': 1, 'is_admin': True}),
            patch.object(web, 'has_permission', return_value=True),
            patch.object(web, 'build_skills_cache', side_effect=lambda: (self.skills, {}, {'guide': self.skills[-1]})),
            patch.object(web, 'get_skill_dir', side_effect=lambda s: Path(s['path'])),
        ]
        for p in self.patches: p.start()
        self.client = web.app.test_client()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def post(self, skills):
        return self.client.post('/api/package', json={'skills': skills})

    def test_missing_selection_rejected(self):
        self.assertEqual(self.post(['missing']).status_code, 404)

    def test_ambiguous_name_rejected(self):
        self.assertEqual(self.post(['guide']).status_code, 409)

    def test_exact_selection(self):
        response = self.post(['design/guide'])
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['count'], 1)
        with zipfile.ZipFile(self.root / 'packages' / data['filename']) as archive:
            self.assertEqual(archive.read('guide/SKILL.md'), b'# design')

    def test_multiple_implementations_do_not_collide(self):
        response = self.post(['design/guide', 'qa-testing/guide'])
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(self.root / 'packages' / response.get_json()['filename']) as archive:
            self.assertEqual(len(set(archive.namelist())), 2)

    def test_generated_folder_does_not_collide_with_real_name(self):
        directory = self.root / 'other'
        directory.mkdir()
        (directory / 'SKILL.md').write_text('# Other', encoding='utf-8')
        self.skills.append({'name': 'guide--1-design', 'namespace': 'other', 'category': 'other', 'path': str(directory)})
        response = self.post(['design/guide', 'qa-testing/guide', 'other/guide--1-design'])
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(self.root / 'packages' / response.get_json()['filename']) as archive:
            self.assertEqual(len(set(archive.namelist())), 3)

    def test_duplicate_input_and_unique_output(self):
        first = self.post(['design/guide', 'design/guide']).get_json()
        second = self.post(['design/guide']).get_json()
        self.assertEqual(first['count'], 1)
        self.assertNotEqual(first['filename'], second['filename'])

    def test_reference_file_uses_exact_identifier(self):
        for skill in self.skills:
            refs = Path(skill['path']) / 'references'
            refs.mkdir()
            (refs / 'guide.md').write_text(skill['namespace'], encoding='utf-8')
        response = self.client.get('/api/skill/guide/file', query_string={'id': 'design/guide', 'path': 'references/guide.md'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['content'], 'design')

    def test_invalid_input(self):
        for value in ('guide', {'name': 'guide'}, [None], [3], []):
            self.assertEqual(self.post(value).status_code, 400, value)

    def test_missing_directory_rejected(self):
        self.skills[0]['path'] = str(self.root / 'gone')
        self.assertEqual(self.post(['design/guide']).status_code, 409)

    def test_partial_selection_is_not_success(self):
        self.assertEqual(self.post(['design/guide', 'missing']).status_code, 404)

    def test_details_exact_and_ambiguous(self):
        exact = self.client.get('/api/skill/guide', query_string={'id': 'design/guide'})
        self.assertEqual(exact.status_code, 200)
        self.assertEqual(exact.get_json()['path'], self.skills[0]['path'])
        self.assertEqual(self.client.get('/api/skill/guide').status_code, 409)

    def test_pagination_input(self):
        for query in ({'page': 0}, {'per_page': -1}):
            self.assertEqual(self.client.get('/api/skills/all', query_string=query).status_code, 400)


if __name__ == '__main__': unittest.main()
