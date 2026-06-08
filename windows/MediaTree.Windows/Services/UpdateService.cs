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
}

