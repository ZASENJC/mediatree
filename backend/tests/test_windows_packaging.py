import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WINDOWS_PROJECT = ROOT / "windows" / "MediaTree.Windows" / "MediaTree.Windows.csproj"
WINDOWS_MANIFEST = ROOT / "windows" / "MediaTree.Windows" / "Package.appxmanifest"
WINDOWS_WORKFLOW = ROOT / ".github" / "workflows" / "windows-release.yml"
WINDOWS_BUILD_SCRIPT = ROOT / "packaging" / "windows" / "build-windows.ps1"
PYINSTALLER_SPEC = ROOT / "packaging" / "windows" / "mediatree-server.spec"


class WindowsPackagingTest(unittest.TestCase):
    def test_winui_project_bundles_backend_server_and_webview2(self):
        project = WINDOWS_PROJECT.read_text(encoding="utf-8")

        self.assertIn("<UseWinUI>true</UseWinUI>", project)
        self.assertIn("Microsoft.WindowsAppSDK", project)
        self.assertIn("Microsoft.Web.WebView2", project)
        self.assertIn("server\\**\\*", project)
        self.assertIn("Package.appxmanifest", project)
        self.assertIn("<TargetFramework>net8.0-windows10.0.19041.0</TargetFramework>", project)

    def test_msix_manifest_declares_full_trust_desktop_app(self):
        manifest = WINDOWS_MANIFEST.read_text(encoding="utf-8")

        self.assertIn('Name="ZASENJC.MediaTree"', manifest)
        self.assertIn('Name="Windows.Desktop"', manifest)
        self.assertIn('Name="runFullTrust"', manifest)
        self.assertIn('Square150x150Logo="Assets\\Square150x150Logo.png"', manifest)

    def test_pyinstaller_spec_preserves_base_app_for_hot_updates(self):
        spec = PYINSTALLER_SPEC.read_text(encoding="utf-8")

        self.assertIn('"backend" / "app"', spec)
        self.assertIn('"base/app"', spec)
        self.assertIn('"frontend" / "dist"', spec)
        self.assertIn('"base/frontend/dist"', spec)
        self.assertIn('"backend" / "app" / "windows_entry.py"', spec)
        self.assertIn('name="mediatree-server"', spec)
        self.assertIn("collect_submodules", spec)
        self.assertIn("SPECPATH", spec)
        self.assertNotIn("__file__", spec)
        self.assertNotIn("ROOT = Path.cwd()", spec)
        self.assertNotIn('"app.main"', spec)

    def test_windows_build_script_runs_validation_before_packaging(self):
        script = WINDOWS_BUILD_SCRIPT.read_text(encoding="utf-8")

        self.assertLess(
            script.index("python -m pip install -r backend/requirements.txt"),
            script.index('python -m unittest discover -s tests -p "test_*.py"'),
        )
        self.assertIn("function Invoke-Native", script)
        self.assertIn("$FilePath = [string]$args[0]", script)
        self.assertNotIn("ValueFromRemainingArguments", script)
        self.assertIn("throw \"$FilePath failed with exit code $LASTEXITCODE\"", script)
        self.assertIn('python -m unittest discover -s tests -p "test_*.py"', script)
        self.assertIn("python -m compileall -q backend/app", script)
        self.assertIn("npm.cmd run build", script)
        self.assertIn("pyinstaller --noconfirm", script)
        self.assertIn("$MsixVersion", script)
        self.assertIn("docs/assets/logo.png", script)
        self.assertIn("$OriginalManifest", script)
        self.assertIn("function Resolve-MSBuild", script)
        self.assertIn("function Resolve-WindowsKitTool", script)
        self.assertIn("function New-ExpandedAppxManifest", script)
        self.assertIn("function New-AppInstallerFile", script)
        self.assertIn("function New-TestSigningCertificate", script)
        self.assertIn("vswhere.exe", script)
        self.assertIn("MSBuild.exe", script)
        self.assertIn("GenerateAppxPackageOnBuild=true", script)
        self.assertIn("AppxIntermediateExtension=.intermediate", script)
        self.assertIn("UapAppxPackageBuildMode=SideloadOnly", script)
        self.assertIn("makeappx.exe", script)
        self.assertIn("signtool.exe", script)
        self.assertIn("MediaTree-Windows-$Version.msix", script)
        self.assertIn("MediaTree-Windows-$Version.appinstaller", script)
        self.assertIn("MediaTree-Windows-$Version.cer", script)
        self.assertIn('".cer"', script)
        self.assertIn("Windows.FullTrustApplication", script)
        self.assertIn("ProcessorArchitecture", script)
        self.assertIn("MSIX package was not generated", script)
        self.assertIn("App installer file was not generated", script)
        self.assertNotIn("dotnet publish windows/MediaTree.Windows/MediaTree.Windows.csproj", script)

    def test_windows_release_workflow_builds_only_when_base_update_required_or_manual(self):
        workflow = WINDOWS_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("requires_windows_base_update", workflow)
        self.assertIn("workflow_dispatch", workflow)
        self.assertIn("packaging/windows/build-windows.ps1", workflow)
        self.assertIn("steps.metadata.outputs.requires_windows_base_update == 'true'", workflow)
        self.assertIn("softprops/action-gh-release", workflow)


if __name__ == "__main__":
    unittest.main()
