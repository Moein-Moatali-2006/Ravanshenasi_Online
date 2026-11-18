import unittest

from app import create_app


class TestPageRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()

    def test_existing_pages_render(self):
        pages = (
            "/",
            "/about/",
            "/support/",
            "/register/",
            "/login/",
        )

        for path in pages:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

    def test_only_page_stylesheet_is_included(self):
        page_styles = {
            "/": "home.css",
            "/about/": "about.css",
            "/support/": "support.css",
            "/register/": "register.css",
            "/login/": "login.css",
        }

        for path, stylesheet in page_styles.items():
            with self.subTest(path=path):
                response = self.client.get(path)
                html = response.get_data(as_text=True)
                self.assertIn(f"css/{stylesheet}", html)

                for other_stylesheet in set(page_styles.values()) - {stylesheet}:
                    self.assertNotIn(f"css/{other_stylesheet}", html)

    def test_page_stylesheet_is_served(self):
        response = self.client.get("/static/css/home.css")

        self.assertEqual(response.status_code, 200)
        self.assertIn(".home-page", response.get_data(as_text=True))
        response.close()


if __name__ == "__main__":
    unittest.main()
