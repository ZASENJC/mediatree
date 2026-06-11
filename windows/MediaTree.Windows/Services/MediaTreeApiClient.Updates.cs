using System;
using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public sealed partial class MediaTreeApiClient
{
    public async Task<VersionInfoDto> GetVersionAsync(CancellationToken cancellationToken = default)
        => await GetAsync<VersionInfoDto>("/version", cancellationToken);

    public async Task<UpdateCheckResultDto> CheckForUpdatesAsync(CancellationToken cancellationToken = default)
        => await GetAsync<UpdateCheckResultDto>("/update/check", cancellationToken);

    public async Task<UpdateStatusDto> GetUpdateStatusAsync(CancellationToken cancellationToken = default)
        => await GetAsync<UpdateStatusDto>("/update/status", cancellationToken);

    public async Task<UpdateActionResultDto> PerformUpdateAsync(string version, string mode = "app-package", CancellationToken cancellationToken = default)
        => await PostJsonAsync<UpdateActionResultDto>("/update/perform", new { version, mode }, cancellationToken);

    public async Task<UpdateActionResultDto> RollbackUpdateAsync(CancellationToken cancellationToken = default)
        => await PostJsonAsync<UpdateActionResultDto>("/update/rollback", new { }, cancellationToken);

    public async Task<ChangelogDto> GetChangelogAsync(string version, CancellationToken cancellationToken = default)
        => await GetAsync<ChangelogDto>($"/update/changelog?version={Uri.EscapeDataString(version)}", cancellationToken);
}
