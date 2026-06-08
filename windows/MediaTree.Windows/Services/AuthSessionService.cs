using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public sealed class AuthSessionService
{
    private const string LocalUsername = "mediatree-windows";
    private readonly MediaTreeApiClient _api;

    public AuthSessionService(MediaTreeApiClient api)
    {
        _api = api;
    }

    public async Task<AuthSessionResult> EnsureLocalSessionAsync(CancellationToken cancellationToken = default)
    {
        var status = await _api.GetAuthStatusAsync(cancellationToken);
        var stored = LoadStoredCredentials();

        if (!status.AuthConfigured)
        {
            var password = GenerateSecret();
            var response = await _api.SetupAuthAsync(LocalUsername, password, cancellationToken);
            _api.SetBearerToken(response.Token);
            SaveStoredCredentials(LocalUsername, password);
            return new AuthSessionResult(AuthSessionState.CreatedLocalAccount, "已创建 Windows 本机会话。");
        }

        if (stored is not null)
        {
            try
            {
                var response = await _api.LoginAsync(stored.Username, stored.Password, cancellationToken);
                _api.SetBearerToken(response.Token);
                return new AuthSessionResult(AuthSessionState.Ready, "已恢复 Windows 本机会话。");
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, "Stored Windows session could not be restored.");
                ClearStoredCredentials();
            }
        }

        return new AuthSessionResult(AuthSessionState.NeedsUserLogin, "需要输入现有管理员账号接管本机会话。");
    }

    public async Task<AuthSessionResult> LoginAndPersistAsync(string username, string password, CancellationToken cancellationToken = default)
    {
        var response = await _api.LoginAsync(username, password, cancellationToken);
        _api.SetBearerToken(response.Token);
        SaveStoredCredentials(username, password);
        return new AuthSessionResult(AuthSessionState.Ready, "已保存 Windows 本机会话。");
    }

    private static string GenerateSecret()
    {
        var bytes = RandomNumberGenerator.GetBytes(32);
        return Convert.ToBase64String(bytes);
    }

    private static StoredCredentials? LoadStoredCredentials()
    {
        try
        {
            if (!File.Exists(AppPaths.WindowsSessionFile))
            {
                return null;
            }

            var envelope = JsonSerializer.Deserialize<CredentialEnvelope>(File.ReadAllText(AppPaths.WindowsSessionFile, Encoding.UTF8));
            if (envelope is null || string.IsNullOrWhiteSpace(envelope.Payload))
            {
                return null;
            }

            var protectedBytes = Convert.FromBase64String(envelope.Payload);
            var bytes = ProtectedData.Unprotect(protectedBytes, null, DataProtectionScope.CurrentUser);
            return JsonSerializer.Deserialize<StoredCredentials>(Encoding.UTF8.GetString(bytes));
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load Windows DPAPI session.");
            return null;
        }
    }

    private static void SaveStoredCredentials(string username, string password)
    {
        Directory.CreateDirectory(AppPaths.WindowsStateDirectory);
        var bytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(new StoredCredentials(username, password)));
        var protectedBytes = ProtectedData.Protect(bytes, null, DataProtectionScope.CurrentUser);
        var envelope = new CredentialEnvelope(Convert.ToBase64String(protectedBytes));
        File.WriteAllText(AppPaths.WindowsSessionFile, JsonSerializer.Serialize(envelope), Encoding.UTF8);
    }

    private static void ClearStoredCredentials()
    {
        try
        {
            if (File.Exists(AppPaths.WindowsSessionFile))
            {
                File.Delete(AppPaths.WindowsSessionFile);
            }
        }
        catch
        {
            // Ignore credential cleanup failures.
        }
    }

    private sealed record StoredCredentials(string Username, string Password);

    private sealed record CredentialEnvelope(string Payload);
}

