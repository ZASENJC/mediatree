import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "release-tag.yml"


class ReleaseWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def _step_block(self, name: str) -> str:
        pattern = rf"(?ms)^      - name: {re.escape(name)}\n(?P<body>.*?)(?=^      - name: |\Z)"
        match = re.search(pattern, self.workflow)
        self.assertIsNotNone(match, f"missing workflow step: {name}")
        return match.group("body")

    def test_regular_app_package_release_pushes_only_latest_image(self):
        push = self._step_block("Push Docker image")

        self.assertIn("zasenjc/mediatree:latest", push)
        self.assertIn("RELEASE_REQUIRES_IMAGE_UPDATE", push)
        self.assertNotIn("zasenjc/mediatree:${{ steps.version.outputs.version }}", push)

    def test_full_image_release_pushes_version_tag_and_latest(self):
        versioned_push = self._step_block("Push versioned Docker image")

        self.assertIn("RELEASE_REQUIRES_IMAGE_UPDATE == 'true'", versioned_push)
        self.assertIn("zasenjc/mediatree:${{ steps.version.outputs.version }}", versioned_push)
        self.assertIn("zasenjc/mediatree:latest", versioned_push)

    def test_dockerhub_credentials_are_required_before_release_is_published(self):
        require = self._step_block("Require DockerHub credentials")
        update_tag_pos = self.workflow.index("- name: Update tag after validation")

        self.assertLess(self.workflow.index("- name: Require DockerHub credentials"), update_tag_pos)
        self.assertIn("DOCKERHUB_USERNAME_SET != 'true'", require)
        self.assertIn("DOCKERHUB_TOKEN_SET != 'true'", require)


if __name__ == "__main__":
    unittest.main()
