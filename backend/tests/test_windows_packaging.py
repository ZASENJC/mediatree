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
        self.assertIn("<WindowsPackageType>None</WindowsPackageType>", project)
        self.assertIn("<WindowsAppSDKSelfContained>true</WindowsAppSDKSelfContained>", project)
        self.assertIn("Microsoft.WindowsAppSDK", project)
        self.assertIn("Microsoft.Web.WebView2", project)
        self.assertIn("server\\**\\*", project)
        self.assertIn("mpv\\**\\*", project)
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
        self.assertIn('$ServerDist = Join-Path $Root "dist/windows/server"', script)
        self.assertIn('$ServerWork = Join-Path $Root "build/windows/mediatree-server"', script)
        self.assertIn("Remove-Item $ServerSource -Recurse -Force", script)
        self.assertIn("Remove-Item $ServerWork -Recurse -Force", script)
        self.assertIn("$MpvArchiveUrl", script)
        self.assertIn("py7zr", script)
        self.assertIn("mpv.exe", script)
        self.assertIn("$MsixVersion", script)
        self.assertIn("docs/assets/logo.png", script)
        self.assertIn("$OriginalManifest", script)
        self.assertIn("function Resolve-WindowsKitTool", script)
        self.assertIn("function Resolve-7ZipTool", script)
        self.assertIn("function Resolve-MSBuild", script)
        self.assertIn("function New-ExpandedAppxManifest", script)
        self.assertIn("function New-AppInstallerFile", script)
        self.assertIn("function New-TestSigningCertificate", script)
        self.assertIn("7zr.exe", script)
        self.assertIn("$SevenZipUrl", script)
        self.assertIn("/t:Publish", script)
        self.assertIn("WindowsAppSDKSelfContained=true", script)
        self.assertIn("WindowsPackageType=None", script)
        self.assertIn("SelfContained=true", script)
        self.assertIn("PublishSingleFile=false", script)
        self.assertIn("makeappx.exe", script)
        self.assertIn("signtool.exe", script)
        self.assertIn("MediaTree-Windows-$Version.msix", script)
        self.assertIn("MediaTree-Windows-$Version.appinstaller", script)
        self.assertIn("MediaTree-Windows-$Version.cer", script)
        self.assertIn("MediaTree-Windows-$Version-portable.zip", script)
        self.assertIn('".zip"', script)
        self.assertIn('".cer"', script)
        self.assertIn("Windows.FullTrustApplication", script)
        self.assertIn("ProcessorArchitecture", script)
        self.assertIn("MSIX package was not generated", script)
        self.assertIn("App installer file was not generated", script)
        self.assertIn("Portable package was not generated", script)
        self.assertNotIn("GenerateAppxPackageOnBuild=true", script)

    def test_windows_shell_embeds_bundled_mpv_and_exposes_webview_bridge(self):
        bridge = (ROOT / "windows" / "MediaTree.Windows" / "Services" / "WindowsBridge.cs").read_text(encoding="utf-8")
        backend_service = (ROOT / "windows" / "MediaTree.Windows" / "Services" / "BackendProcessService.cs").read_text(encoding="utf-8")
        player = (ROOT / "windows" / "MediaTree.Windows" / "MpvPlayerWindow.xaml.cs").read_text(encoding="utf-8")
        main_window = (ROOT / "windows" / "MediaTree.Windows" / "MainWindow.xaml.cs").read_text(encoding="utf-8")
        main_window_xaml = (ROOT / "windows" / "MediaTree.Windows" / "MainWindow.xaml").read_text(encoding="utf-8")
        frontend_bridge = (ROOT / "frontend" / "src" / "windowsBridge.ts").read_text(encoding="utf-8")
        video_player = (ROOT / "frontend" / "src" / "components" / "VideoPlayer.tsx").read_text(encoding="utf-8")
        login_page = (ROOT / "frontend" / "src" / "pages" / "Login.tsx").read_text(encoding="utf-8")

        self.assertIn("OpenMpv", bridge)
        self.assertIn("MpvPlayerWindow", bridge)
        self.assertIn("mpv.exe", player)
        self.assertIn("File.Exists(AppPaths.MpvExe)", player)
        self.assertIn("FileName = AppPaths.MpvExe", player)
        self.assertIn("WorkingDirectory = AppPaths.MpvDirectory", player)
        self.assertIn("--wid=", player)
        self.assertNotIn('FileName = "mpv"', player)
        self.assertNotIn('FileName = "mpv.exe"', player)
        self.assertNotIn("WebView2", main_window_xaml)
        self.assertNotIn("InitializeComponent()", main_window)
        self.assertNotIn("ProgressRing", main_window)
        self.assertNotIn("AppWindow.GetFromWindowId", main_window)
        self.assertIn("BuildContent()", main_window)
        self.assertIn("ShowAndBringToFront()", main_window)
        self.assertIn("WindowNative.GetWindowHandle(this)", main_window)
        self.assertIn("DispatcherQueue.TryEnqueue", main_window)
        self.assertIn("WEBVIEW2_USER_DATA_FOLDER", main_window)
        self.assertIn("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", main_window)
        self.assertIn("AppPaths.WebView2Directory", main_window)
        self.assertIn("--disable-gpu --disable-gpu-compositing", main_window)
        self.assertIn("EnsureCoreWebView2Async().AsTask()", main_window)
        self.assertIn("Task.WhenAny", main_window)
        self.assertIn("LogPageStateWithDelayAsync", main_window)
        self.assertIn("after-10s", main_window)
        self.assertIn("MEDIATREE_WINDOWS_DIAGNOSTICS", main_window)
        self.assertIn("CapturePreviewAsync", main_window)
        self.assertIn("webview-preview-", main_window)
        self.assertNotIn("bodyText", main_window)
        self.assertIn("ShowStartupFailure", main_window)
        self.assertIn("new TextBlock", main_window)
        self.assertIn("new WebView2", main_window)
        self.assertIn("_browserHost.Children.Insert", main_window)
        self.assertIn("WebMessageReceived", main_window)
        self.assertNotIn("AddHostObjectToScript", main_window)
        self.assertIn("pickFolder", main_window)
        self.assertIn("Task.Run(() => PipeToFileAsync", backend_service)
        self.assertNotIn("reader.EndOfStream", backend_service)
        self.assertIn("openMpv", frontend_bridge)
        self.assertIn("postMessage", frontend_bridge)
        self.assertIn("isWindowsShell", video_player)
        self.assertIn("Windows 内嵌 MPV 启动失败", video_player)
        self.assertIn("openMpv(localPlaybackUrl)", video_player)
        self.assertLess(video_player.index("if (windowsShell)"), video_player.index("mpv://play/"))
        self.assertIn("MediaTree auth status check timed out", login_page)
        self.assertIn("finishChecking", login_page)
        self.assertIn("window.setTimeout", login_page)

    def test_windows_release_workflow_builds_only_when_base_update_required_or_manual(self):
        workflow = WINDOWS_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("requires_windows_base_update", workflow)
        self.assertIn("workflow_dispatch", workflow)
        self.assertIn("packaging/windows/build-windows.ps1", workflow)
        self.assertIn("steps.metadata.outputs.requires_windows_base_update == 'true'", workflow)
        self.assertIn("softprops/action-gh-release", workflow)
        self.assertIn('".zip"', workflow)


if __name__ == "__main__":
    unittest.main()
