import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "release-tag.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
LOCAL_DOCKER_PUSH = ROOT / "scripts" / "push-docker-release.sh"
APP_PACKAGE_BUILDER = ROOT / "scripts" / "build-app-package.sh"
TELEGRAM_NOTIFY = ROOT / ".github" / "scripts" / "notify-telegram-release.sh"
DOCKERFILE = ROOT / "Dockerfile"


class ReleaseWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.ci_workflow = CI_WORKFLOW.read_text(encoding="utf-8")

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

    def test_release_workflow_is_manual_only(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("\n  push:", self.workflow)
        self.assertNotIn("\n    branches:\n      - main", self.workflow)

    def test_release_workflow_publishes_app_package_before_tag_and_release(self):
        app_package_pos = self.workflow.index("- name: Build app update package")
        update_tag_pos = self.workflow.index("- name: Update tag after validation")
        github_release_pos = self.workflow.index("- name: Update GitHub Release")

        self.assertLess(app_package_pos, update_tag_pos)
        self.assertLess(update_tag_pos, github_release_pos)

    def test_release_workflow_notifies_telegram_after_github_release(self):
        github_release_pos = self.workflow.index("- name: Update GitHub Release")
        telegram_pos = self.workflow.index("- name: Notify Telegram")
        notify_step = self._step_block("Notify Telegram")

        self.assertLess(github_release_pos, telegram_pos)
        self.assertIn("TG_BOT_TOKEN", notify_step)
        self.assertIn("TG_CHAT_ID", notify_step)
        self.assertIn("VERSION: ${{ steps.version.outputs.version }}", notify_step)
        self.assertIn("bash .github/scripts/notify-telegram-release.sh", notify_step)

    def test_telegram_notification_is_message_only(self):
        script = TELEGRAM_NOTIFY.read_text(encoding="utf-8")

        self.assertIn("sendMessage", script)
        self.assertNotIn("sendDocument", script)
        self.assertNotIn("document=@", script)
        self.assertNotIn("app_package.outputs.archive", script)
        self.assertNotIn("mediatree-app-$VERSION.tar.gz", script)

    def test_workflows_use_node24_compatible_action_versions(self):
        workflows = self.workflow + "\n" + self.ci_workflow

        expected = [
            "actions/checkout@v6",
            "actions/setup-node@v6",
            "actions/setup-python@v6",
            "softprops/action-gh-release@v3",
        ]
        old_versions = [
            "actions/checkout@v4",
            "actions/setup-node@v4",
            "actions/setup-python@v5",
            "softprops/action-gh-release@v2",
        ]

        for marker in expected:
            self.assertIn(marker, workflows)
        for marker in old_versions:
            self.assertNotIn(marker, workflows)

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
        metadata = (ROOT / ".github" / "release-metadata.json").read_text(encoding="utf-8")
        builder = APP_PACKAGE_BUILDER.read_text(encoding="utf-8")

        self.assertIn("requires_windows_base_update", builder)
        self.assertIn("windows_reason", builder)
        self.assertIn("RELEASE_REQUIRES_WINDOWS_BASE_UPDATE", self.workflow)
        self.assertIn("RELEASE_WINDOWS_UPDATE_REASON", self.workflow)
        self.assertIn("requires_windows_base_update", metadata)
        self.assertIn("windows_reason", metadata)

    def test_windows_full_update_versions_are_marked_in_metadata(self):
        metadata = json.loads((ROOT / ".github" / "release-metadata.json").read_text(encoding="utf-8"))
        version = metadata["versions"]["1.0.15"]

        self.assertIs(version.get("requires_windows_base_update"), True)
        self.assertIn("Windows", version.get("windows_reason", ""))

    def test_local_docker_push_script_exposes_size_tuning_build_args(self):
        script = LOCAL_DOCKER_PUSH.read_text(encoding="utf-8")

        self.assertIn("INCLUDE_FULL_CJK_FONTS", script)
        self.assertIn('--build-arg "INCLUDE_FULL_CJK_FONTS=$INCLUDE_FULL_CJK_FONTS"', script)
        self.assertIn("INCLUDE_EMOJI_FONT", script)
        self.assertIn('--build-arg "INCLUDE_EMOJI_FONT=$INCLUDE_EMOJI_FONT"', script)

    def test_docker_release_push_labels_latest_with_version_baseline(self):
        script = LOCAL_DOCKER_PUSH.read_text(encoding="utf-8")
        dockerfile = DOCKERFILE.read_text(encoding="utf-8")

        self.assertIn('--build-arg "MEDIATREE_VERSION=$VERSION"', script)
        self.assertIn("ARG MEDIATREE_VERSION=unknown", dockerfile)
        self.assertIn("org.opencontainers.image.version=$MEDIATREE_VERSION", dockerfile)

    def test_dockerfile_keeps_large_fonts_optional_and_avoids_base_gnupg(self):
        dockerfile = DOCKERFILE.read_text(encoding="utf-8")
        base_install = dockerfile.split("ARG INCLUDE_DOCKER_CLI", 1)[0]

        self.assertIn("ARG INCLUDE_FULL_CJK_FONTS=false", dockerfile)
        self.assertIn("ARG INCLUDE_EMOJI_FONT=false", dockerfile)
        self.assertIn("fonts-wqy-microhei", dockerfile)
        self.assertIn("fonts-noto-cjk", dockerfile)
        self.assertIn("fonts-noto-color-emoji", dockerfile)
        self.assertNotIn("gnupg", base_install)

    def test_dockerfile_copies_runtime_backend_only(self):
        dockerfile = DOCKERFILE.read_text(encoding="utf-8")

        self.assertIn("ENV PYTHONDONTWRITEBYTECODE=1", dockerfile)
        self.assertIn("COPY backend/app ./app", dockerfile)
        self.assertNotIn("COPY backend/ ./", dockerfile)

    def test_release_workflow_uses_shared_app_package_builder(self):
        self.assertIn("scripts/build-app-package.sh", self.workflow)
        self.assertNotIn('tar -czf "$ARCHIVE"', self.workflow)

    def test_app_package_builder_strips_bytecode_and_uses_max_compression(self):
        script = APP_PACKAGE_BUILDER.read_text(encoding="utf-8")

        self.assertIn("rm -rf", script)
        self.assertIn("__pycache__", script)
        self.assertIn("*.pyc", script)
        self.assertIn("compresslevel=9", script)
        self.assertIn("mtime=0", script)
        self.assertIn("sorted(pkg_dir.rglob", script)


if __name__ == "__main__":
    unittest.main()
