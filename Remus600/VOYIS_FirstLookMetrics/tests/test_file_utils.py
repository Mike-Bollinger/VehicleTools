import unittest
from src.utils.file_utils import list_files, is_image_file

class TestFileUtils(unittest.TestCase):

    def test_list_files(self):
        # Assuming a test directory structure is set up for this test
        test_directory = 'test_images'
        expected_files = ['image1.jpg', 'image2.png']
        actual_files = list_files(test_directory)
        self.assertEqual(sorted(actual_files), sorted(expected_files))

    def test_is_image_file(self):
        self.assertTrue(is_image_file('image.jpg'))
        self.assertTrue(is_image_file('photo.png'))
        self.assertFalse(is_image_file('document.pdf'))
        self.assertFalse(is_image_file('archive.zip'))

if __name__ == '__main__':
    unittest.main()