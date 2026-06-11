using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public sealed partial class MediaTreeApiClient
{
    public async Task<AuthStatusDto> GetAuthStatusAsync(CancellationToken cancellationToken = default)
        => await GetAsync<AuthStatusDto>("/auth/status", cancellationToken);

    public async Task<AuthResponseDto> LoginAsync(string username, string password, CancellationToken cancellationToken = default)
        => await PostJsonAsync<AuthResponseDto>("/auth/login", new { username, password }, cancellationToken);

    public async Task<AuthResponseDto> SetupAuthAsync(string username, string password, CancellationToken cancellationToken = default)
        => await PostJsonAsync<AuthResponseDto>("/auth/setup", new { username, password }, cancellationToken);

    public async Task ChangePasswordAsync(
        string oldUsername,
        string oldPassword,
        string newUsername,
        string newPassword,
        CancellationToken cancellationToken = default)
        => await PostJsonAsync<JsonElement>("/auth/change-password", new
        {
            old_username = oldUsername,
            old_password = oldPassword,
            new_username = newUsername,
            new_password = newPassword,
        }, cancellationToken);
}
