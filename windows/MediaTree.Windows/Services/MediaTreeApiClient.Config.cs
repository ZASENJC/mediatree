using System.Collections.Generic;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public sealed partial class MediaTreeApiClient
{
    public async Task<ConfigDto> GetConfigAsync(CancellationToken cancellationToken = default)
        => await GetAsync<ConfigDto>("/config", cancellationToken);

    public async Task SaveConfigAsync(IEnumerable<string> extraMediaRoots, CancellationToken cancellationToken = default)
        => await PostJsonAsync<JsonElement>("/config", new { extra_media_roots = extraMediaRoots }, cancellationToken);

    public async Task SaveTmdbConfigAsync(string accessToken, CancellationToken cancellationToken = default)
        => await PostJsonAsync<JsonElement>("/config", new { tmdb_access_token = NormalizeTmdbAccessToken(accessToken) }, cancellationToken);

    public async Task SaveGlobalConfigAsync(ConfigDto config, CancellationToken cancellationToken = default)
        => await PostJsonAsync<JsonElement>("/config", new
        {
            javdb_enabled = config.JavdbEnabled,
            tmdb_api_key = config.TmdbApiKey,
            tmdb_access_token = NormalizeTmdbAccessToken(config.TmdbAccessToken),
            update_check_enabled = config.UpdateCheckEnabled,
            update_check_interval_hours = config.UpdateCheckIntervalHours,
        }, cancellationToken);
}
