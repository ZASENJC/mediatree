using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public sealed class UpdateService
{
    private readonly MediaTreeApiClient _api;

    public UpdateService(MediaTreeApiClient api)
    {
        _api = api;
    }

    public Task<VersionInfoDto> GetVersionAsync(CancellationToken cancellationToken = default)
        => _api.GetVersionAsync(cancellationToken);

    public Task<UpdateCheckResultDto> CheckForUpdatesAsync(CancellationToken cancellationToken = default)
        => _api.CheckForUpdatesAsync(cancellationToken);

    public Task<UpdateStatusDto> GetStatusAsync(CancellationToken cancellationToken = default)
        => _api.GetUpdateStatusAsync(cancellationToken);

    public Task<UpdateActionResultDto> PerformUpdateAsync(string version, string mode = "app-package", CancellationToken cancellationToken = default)
        => _api.PerformUpdateAsync(version, mode, cancellationToken);

    public Task<UpdateActionResultDto> RollbackAsync(CancellationToken cancellationToken = default)
        => _api.RollbackUpdateAsync(cancellationToken);

    public Task<ChangelogDto> GetChangelogAsync(string version, CancellationToken cancellationToken = default)
        => _api.GetChangelogAsync(version, cancellationToken);
}
