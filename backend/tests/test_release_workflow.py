import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "release-tag.yml"
LOCAL_DOCKER_PUSH = ROOT / "scripts" / "push-docker-release.sh"
DOCKERFILE = ROOT / "Dockerfile"


class ReleaseWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def _step_block(self, name: str) -> str:
        pattern = rf"(?ms)^      - name: {re.escape(name)}\n(?P<body>.*?)(?=^      - name: |\Z)"
        match = re.search(pattern, self.workflow)
        self.assertIsNotNone(match, f"missing workflow step: {name}")
        return match.group("body")

    def test_release_workflow_does_not_push_dockerhub_images(self):
        forbidden = [
            "docker/build-push-action",
            "docker/login-action",
            "docker/setup-buildx-action",
            "DOCKERHUB_USERNAME",
            "DOCKERHUB_TOKEN",
            "zasenjc/mediatree:latest",
            "docker buildx build",
        ]

        for marker in forbidden:
            self.assertNotIn(marker, self.workflow)

    def test_release_workflow_publishes_app_package_before_tag_and_release(self):
        app_package_pos = self.workflow.index("- name: Build app update package")
        update_tag_pos = self.workflow.index("- name: Update tag after validation")
        github_release_pos = self.workflow.index("- name: Update GitHub Release")

        self.assertLess(app_package_pos, update_tag_pos)
        self.assertLess(update_tag_pos, github_release_pos)

    def test_local_docker_push_script_handles_app_package_and_full_image_releases(self):
        script = LOCAL_DOCKER_PUSH.read_text(encoding="utf-8")

        self.assertIn(".github/release-metadata.json", script)
        self.assertIn("requires_image_update", script)
        self.assertIn("zasenjc/mediatree:latest", script)
        self.assertIn("zasenjc/mediatree:${VERSION}", script)
        self.assertIn("docker buildx build", script)
        self.assertIn("--platform", script)
        self.assertIn("linux/amd64,linux/arm64", script)

    def test_release_manifest_includes_windows_base_update_metadata(self):
        app_package = self._step_block("Build app update package")
        metadata = (ROOT / ".github" / "release-metadata.json").read_text(encoding="utf-8")

        self.assertIn("requires_windows_base_update", app_package)
        self.assertIn("windows_reason", app_package)
        self.assertIn("RELEASE_REQUIRES_WINDOWS_BASE_UPDATE", self.workflow)
        self.assertIn("RELEASE_WINDOWS_UPDATE_REASON", self.workflow)
        self.assertIn("requires_windows_base_update", metadata)
        self.assertIn("windows_reason", metadata)

    def test_docker_release_push_labels_latest_with_version_baseline(self):
        script = LOCAL_DOCKER_PUSH.read_text(encoding="utf-8")
        dockerfile = DOCKERFILE.read_text(encoding="utf-8")

        self.assertIn('--build-arg "MEDIATREE_VERSION=$VERSION"', script)
        self.assertIn("ARG MEDIATREE_VERSION=unknown", dockerfile)
        self.assertIn("org.opencontainers.image.version=$MEDIATREE_VERSION", dockerfile)


if __name__ == "__main__":
    unittest.main()
